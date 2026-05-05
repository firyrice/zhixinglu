import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from app.data.letter_data import fetch_letter_data
from app.ai.llm_client import chat, chat_with_search
from app.ai.letter_prompts import (
    letter_opening_prompt, letter_stocks_prompt, letter_news_prompt,
    letter_market_prompt, letter_closing_prompt,
)
from app.report.letter_template import (
    letter_html_head, letter_opening_html, letter_data_cards_html,
    letter_stocks_html, letter_news_html, letter_market_html,
    letter_closing_html, letter_html_footer,
)


def _calc_portfolio_summary(holdings: list[dict], quotes: dict) -> dict:
    total_asset = 0
    total_cost = 0
    daily_pnl = 0
    for h in holdings:
        q = quotes.get(h["code"], {})
        price = q.get("price", 0)
        prev_close = q.get("prev_close", price)
        mv = price * h["shares"]
        cost = h["cost_price"] * h["shares"]
        total_asset += mv
        total_cost += cost
        daily_pnl += (price - prev_close) * h["shares"]
    total_pnl = total_asset - total_cost
    daily_pct = (daily_pnl / total_cost * 100) if total_cost > 0 else 0
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    return {
        "total_asset": total_asset, "total_cost": total_cost,
        "daily_pnl": daily_pnl, "daily_pct": daily_pct,
        "total_pnl": total_pnl, "total_pnl_pct": total_pnl_pct,
    }


def _build_stock_details_str(holdings, quotes, details):
    lines = []
    for h in holdings:
        q = quotes.get(h["code"], {})
        d = details.get(h["code"], {})
        price = q.get("price", 0)
        prev = q.get("prev_close", price)
        change_pct = ((price - prev) / prev * 100) if prev > 0 else 0
        pnl = (price - h["cost_price"]) * h["shares"]
        pnl_pct = ((price - h["cost_price"]) / h["cost_price"] * 100) if h["cost_price"] > 0 else 0
        lines.append(f"【{h['name']} {h['code']}】")
        lines.append(f"  今日涨跌: {change_pct:+.2f}%, 持仓盈亏: {pnl:+,.0f} ({pnl_pct:+.1f}%)")
        lines.append(f"  持仓: {h['shares']}股, 成本: ¥{h['cost_price']:.2f}, 现价: ¥{price:.2f}")
        if d.get("主力净流入") is not None:
            lines.append(f"  主力净流入: {d['主力净流入']/10000:.0f}万")
        vol_chg = d.get("成交量变化")
        if vol_chg is not None:
            lines.append(f"  成交量变化: {vol_chg:+.1f}%")
        for ma in ["MA5", "MA10", "MA20"]:
            if ma in d:
                lines.append(f"  {ma}: ¥{d[ma]:.2f}")
        lines.append("")
    return "\n".join(lines)


def _build_news_str(holdings, stock_news):
    lines = []
    for h in holdings:
        news = stock_news.get(h["code"])
        if news is None or (hasattr(news, 'empty') and news.empty):
            continue
        lines.append(f"【{h['name']}相关新闻】")
        if hasattr(news, 'iterrows'):
            for _, row in news.head(5).iterrows():
                title = row.get("新闻标题", "")
                date = row.get("发布时间", "")
                if title:
                    lines.append(f"  - [{date}] {title}")
        lines.append("")
    return "\n".join(lines) if lines else "今日无重要相关新闻"


def _build_market_str(market):
    lines = []
    for idx in ["上证指数", "深证成指", "创业板指", "沪深300"]:
        d = market.get(idx)
        if d:
            lines.append(f"{idx}: {d.get('最新价', 'N/A')} ({d.get('涨跌幅', 'N/A')}%), 成交额: {d.get('成交额', 'N/A')}")
    north = market.get("北向资金")
    if north:
        lines.append(f"北向资金净流入: {north.get('净流入', 'N/A')}亿")
    top = market.get("领涨板块", [])
    if top:
        lines.append("领涨板块: " + ", ".join(f"{b['板块名称']}({b['涨跌幅']}%)" for b in top[:3]))
    bottom = market.get("领跌板块", [])
    if bottom:
        lines.append("领跌板块: " + ", ".join(f"{b['板块名称']}({b['涨跌幅']}%)" for b in bottom[:3]))
    return "\n".join(lines) if lines else "市场数据暂不可用"


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                lines = lines[:i]
                break
        text = "\n".join(lines)
    return json.loads(text)


# PLACEHOLDER_GENERATOR_PART3


def _enrich_stocks_with_data(stocks_json: list[dict], holdings, quotes) -> list[dict]:
    """Fill in change_pct from real data if LLM got it wrong."""
    code_map = {}
    for h in holdings:
        q = quotes.get(h["code"], {})
        price = q.get("price", 0)
        prev = q.get("prev_close", price)
        change = ((price - prev) / prev * 100) if prev > 0 else 0
        code_map[h["code"]] = change
        code_map[h["name"]] = change

    for s in stocks_json:
        real_change = code_map.get(s.get("code")) or code_map.get(s.get("name"))
        if real_change is not None:
            s["change_pct"] = round(real_change, 2)
    return stocks_json


async def generate_letter(holdings: list[dict]) -> AsyncGenerator[str, None]:
    if not holdings:
        yield letter_html_head()
        yield '<div class="opening">你还没有添加持仓，请先在持仓页添加股票后再来。</div>'
        yield letter_html_footer()
        return

    date_str = datetime.now().strftime("%Y年%m月%d日")
    yield letter_html_head(date_str)

    data = await fetch_letter_data(holdings)
    quotes = data["quotes"]
    market = data["market_overview"]
    details = data["stock_details"]
    news = data["stock_news"]

    summary = _calc_portfolio_summary(holdings, quotes)
    hs300 = market.get("沪深300", {})
    hs300_chg = float(hs300.get("涨跌幅", 0) or 0)
    vs_hs300 = summary["daily_pct"] - hs300_chg

    portfolio_str = (
        f"今日盈亏: {summary['daily_pnl']:+,.0f} ({summary['daily_pct']:+.2f}%), "
        f"总资产: {summary['total_asset']:,.0f}, "
        f"持仓盈亏: {summary['total_pnl_pct']:+.2f}%, "
        f"跑赢沪深300: {vs_hs300:+.1f}%"
    )
    market_str = _build_market_str(market)

    # Opening
    try:
        opening = await asyncio.to_thread(chat, letter_opening_prompt(portfolio_str, market_str))
    except Exception:
        opening = "今天的市场又给了我们一些值得思考的信号。让我们一起来看看。"
    yield letter_opening_html(opening)

    # Data cards
    yield letter_data_cards_html(
        summary["daily_pnl"], summary["daily_pct"],
        summary["total_asset"], summary["total_pnl_pct"], vs_hs300
    )

    # Section 1: Stock analysis cards
    stock_details_str = _build_stock_details_str(holdings, quotes, details)
    try:
        raw = await asyncio.to_thread(
            chat, letter_stocks_prompt(portfolio_str, stock_details_str, market_str)
        )
        stocks_json = _parse_json(raw)
        stocks_json = _enrich_stocks_with_data(stocks_json, holdings, quotes)
    except Exception:
        stocks_json = []
        for h in holdings:
            q = quotes.get(h["code"], {})
            price = q.get("price", 0)
            prev = q.get("prev_close", price)
            change = ((price - prev) / prev * 100) if prev > 0 else 0
            stocks_json.append({
                "name": h["name"], "code": h["code"],
                "change_pct": round(change, 2),
                "reason": "分析暂时无法生成", "signals": [],
                "action": "持有", "action_score": 3, "risk": "",
            })
    yield letter_stocks_html(stocks_json)

    # Section 2: News
    news_str = _build_news_str(holdings, news)
    holdings_str = ", ".join(f"{h['name']}({h['code']})" for h in holdings)
    try:
        raw = await asyncio.to_thread(
            chat_with_search, letter_news_prompt(holdings_str, news_str)
        )
        news_json = _parse_json(raw)
    except Exception:
        news_json = []
    yield letter_news_html(news_json)

    # Section 3: Market temperature
    try:
        raw = await asyncio.to_thread(
            chat_with_search, letter_market_prompt(market_str, portfolio_str)
        )
        market_json = _parse_json(raw)
    except Exception:
        market_json = {
            "sentiment_score": 50, "sentiment_label": "中性",
            "summary": "市场数据暂不可用", "north_flow": "-",
            "hot_sectors": "-", "risk_sectors": "-",
        }
    yield letter_market_html(market_json)

    # Closing
    try:
        closing = await asyncio.to_thread(chat, letter_closing_prompt(portfolio_str))
    except Exception:
        closing = "记住，市场先生是来服务你的，不是来指导你的。明天见。"
    yield letter_closing_html(closing)
    yield letter_html_footer()

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from app.data.letter_data import fetch_letter_data
from app.ai.llm_client import chat, chat_with_search
from app.ai.letter_prompts import (
    letter_opening_prompt, letter_module1_prompt, letter_module2_prompt,
    letter_module3_prompt, letter_module4_prompt, letter_module5_prompt,
    letter_closing_prompt,
)
from app.report.letter_template import (
    letter_html_head, letter_opening_html, letter_module_html,
    letter_data_cards_html, letter_closing_html, letter_html_footer,
)


def _md(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="md-text letter-md">{escaped}</div>'


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


def _build_risk_str(holdings, quotes, summary):
    lines = []
    total = summary["total_asset"]
    sorted_h = sorted(holdings, key=lambda h: quotes.get(h["code"], {}).get("price", 0) * h["shares"], reverse=True)
    if total > 0:
        for h in sorted_h:
            mv = quotes.get(h["code"], {}).get("price", 0) * h["shares"]
            pct = mv / total * 100
            pnl_pct = ((quotes.get(h["code"], {}).get("price", 0) - h["cost_price"]) / h["cost_price"] * 100) if h["cost_price"] > 0 else 0
            lines.append(f"{h['name']}: 仓位{pct:.1f}%, 盈亏{pnl_pct:+.1f}%")
        top3_pct = sum(quotes.get(h["code"], {}).get("price", 0) * h["shares"] / total * 100 for h in sorted_h[:3])
        lines.append(f"前3大持仓占比: {top3_pct:.1f}%")
    return "\n".join(lines) if lines else "持仓数据不足"


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

    portfolio_str = f"今日盈亏: {summary['daily_pnl']:+,.0f} ({summary['daily_pct']:+.2f}%), 总资产: {summary['total_asset']:,.0f}, 持仓盈亏: {summary['total_pnl_pct']:+.2f}%, 跑赢沪深300: {vs_hs300:+.1f}%"
    market_str = _build_market_str(market)

    try:
        opening = await asyncio.to_thread(chat, letter_opening_prompt(portfolio_str, market_str))
    except Exception:
        opening = "今天的市场又给了我们一些值得思考的信号。让我们一起来看看。"
    yield letter_opening_html(opening)

    yield letter_data_cards_html(summary["daily_pnl"], summary["daily_pct"],
                                  summary["total_asset"], summary["total_pnl_pct"], vs_hs300)

    stock_details_str = _build_stock_details_str(holdings, quotes, details)
    try:
        m1 = await asyncio.to_thread(chat, letter_module1_prompt(portfolio_str, stock_details_str))
    except Exception:
        m1 = "个股点评暂时无法生成。"
    yield letter_module_html(1, "今日持仓全景", _md(m1))

    news_str = _build_news_str(holdings, news)
    holdings_str = ", ".join(f"{h['name']}({h['code']})" for h in holdings)
    try:
        m2 = await asyncio.to_thread(chat_with_search, letter_module2_prompt(holdings_str, news_str))
    except Exception:
        m2 = "热点情报暂时无法生成。"
    yield letter_module_html(2, "精选热点情报", _md(m2))

    try:
        m3 = await asyncio.to_thread(chat_with_search, letter_module3_prompt(market_str, holdings_str))
    except Exception:
        m3 = "市场研判暂时无法生成。"
    yield letter_module_html(3, "市场大势研判", _md(m3))

    risk_str = _build_risk_str(holdings, quotes, summary)
    try:
        m4 = await asyncio.to_thread(chat, letter_module4_prompt(risk_str))
    except Exception:
        m4 = "风险体检暂时无法生成。"
    yield letter_module_html(4, "组合风险体检", _md(m4))

    full_context = f"组合概况:\n{portfolio_str}\n\n个股详情:\n{stock_details_str}\n\n市场环境:\n{market_str}\n\n风险分析:\n{risk_str}"
    try:
        m5 = await asyncio.to_thread(chat, letter_module5_prompt(full_context))
    except Exception:
        m5 = "策略建议暂时无法生成。"
    yield letter_module_html(5, "策略建议", _md(m5))

    try:
        closing = await asyncio.to_thread(chat, letter_closing_prompt(portfolio_str))
    except Exception:
        closing = "记住，市场先生是来服务你的，不是来指导你的。保持耐心，我们的目标是长期复利。明天见。"
    yield letter_closing_html(closing)
    yield letter_html_footer()

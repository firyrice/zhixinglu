import asyncio
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

from app.data.portfolio_data import get_batch_quotes
from app.data.market_data import get_stock_kline
from app.data.news_data import get_stock_news


def get_market_overview() -> dict:
    result = {}
    try:
        spot = ak.stock_zh_index_spot_em()
        for idx_name in ["上证指数", "深证成指", "创业板指", "沪深300"]:
            row = spot[spot["名称"] == idx_name]
            if not row.empty:
                r = row.iloc[0]
                result[idx_name] = {
                    "最新价": r.get("最新价"),
                    "涨跌幅": r.get("涨跌幅"),
                    "成交额": r.get("成交额"),
                }
    except Exception:
        pass

    try:
        hsgt = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        if hsgt is not None and not hsgt.empty:
            latest = hsgt.iloc[-1]
            result["北向资金"] = {
                "日期": str(latest.get("date", latest.get("日期", ""))),
                "净流入": latest.get("value", latest.get("当日净流入", 0)),
            }
    except Exception:
        pass

    try:
        board = ak.stock_board_industry_name_em()
        if board is not None and not board.empty:
            board_sorted = board.sort_values("涨跌幅", ascending=False)
            result["领涨板块"] = board_sorted.head(5)[["板块名称", "涨跌幅"]].to_dict("records")
            result["领跌板块"] = board_sorted.tail(5)[["板块名称", "涨跌幅"]].to_dict("records")
    except Exception:
        pass

    return result


def get_stock_detail(symbol: str) -> dict:
    detail = {}
    try:
        fund = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith("6") else "sz")
        if fund is not None and not fund.empty:
            latest = fund.iloc[-1]
            detail["主力净流入"] = latest.get("主力净流入-净额", 0)
            detail["超大单净流入"] = latest.get("超大单净流入-净额", 0)
    except Exception:
        pass

    try:
        kline = get_stock_kline(symbol, 30)
        if kline is not None and not kline.empty:
            closes = kline["close"].tolist()
            volumes = kline["volume"].tolist() if "volume" in kline.columns else []
            detail["30日收盘价"] = closes
            detail["30日成交量"] = volumes
            if len(closes) >= 20:
                detail["MA20"] = sum(closes[-20:]) / 20
            if len(closes) >= 10:
                detail["MA10"] = sum(closes[-10:]) / 10
            if len(closes) >= 5:
                detail["MA5"] = sum(closes[-5:]) / 5
            if len(volumes) >= 2 and volumes[-2] > 0:
                detail["成交量变化"] = (volumes[-1] - volumes[-2]) / volumes[-2] * 100
    except Exception:
        pass

    return detail


async def fetch_letter_data(holdings: list[dict]) -> dict:
    codes = [h["code"] for h in holdings]

    quotes_task = asyncio.to_thread(get_batch_quotes, codes)
    market_task = asyncio.to_thread(get_market_overview)

    detail_tasks = {h["code"]: asyncio.to_thread(get_stock_detail, h["code"]) for h in holdings}
    news_tasks = {h["code"]: asyncio.to_thread(get_stock_news, h["code"]) for h in holdings}

    all_tasks = [quotes_task, market_task] + list(detail_tasks.values()) + list(news_tasks.values())
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    quotes = results[0] if not isinstance(results[0], Exception) else {}
    market_overview = results[1] if not isinstance(results[1], Exception) else {}

    stock_details = {}
    offset = 2
    for i, code in enumerate(detail_tasks.keys()):
        r = results[offset + i]
        stock_details[code] = r if not isinstance(r, Exception) else {}

    stock_news = {}
    offset2 = offset + len(detail_tasks)
    for i, code in enumerate(news_tasks.keys()):
        r = results[offset2 + i]
        stock_news[code] = r if not isinstance(r, Exception) else None

    return {
        "quotes": quotes,
        "market_overview": market_overview,
        "stock_details": stock_details,
        "stock_news": stock_news,
    }

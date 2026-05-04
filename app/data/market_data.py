import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

_kline_cache: dict[str, pd.DataFrame] = {}


def _get_kline_tx(symbol: str) -> pd.DataFrame:
    """获取A股K线数据（腾讯数据源）。"""
    if symbol in _kline_cache:
        return _kline_cache[symbol]

    prefix = "sh" if symbol.startswith("6") else "sz"
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist_tx(symbol=f"{prefix}{symbol}", start_date=start, end_date=end)
    df["date"] = pd.to_datetime(df["date"])
    _kline_cache[symbol] = df
    return df


def _get_kline_hk(symbol: str) -> pd.DataFrame:
    """获取港股K线数据。"""
    cache_key = f"hk_{symbol}"
    if cache_key in _kline_cache:
        return _kline_cache[cache_key]

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    df = ak.stock_hk_hist(symbol=symbol, period="daily", start_date=start, end_date=end, adjust="qfq")
    df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low", "成交量": "volume"})
    df["date"] = pd.to_datetime(df["date"])
    _kline_cache[cache_key] = df
    return df


def get_stock_kline(symbol: str, days: int = 30, market: str = "A") -> pd.DataFrame:
    """获取近N个交易日的K线数据。"""
    if market == "HK":
        df = _get_kline_hk(symbol)
    else:
        df = _get_kline_tx(symbol)
    return df.tail(days).reset_index(drop=True)


def get_realtime_quote(symbol: str, market: str = "A") -> dict:
    """获取股票最新行情。"""
    try:
        if market == "HK":
            df = _get_kline_hk(symbol)
        else:
            df = _get_kline_tx(symbol)
        if df.empty:
            return {}
        latest = df.iloc[-1]
        return {
            "最新价": float(latest["close"]),
            "开盘": float(latest["open"]),
            "最高": float(latest["high"]),
            "最低": float(latest["low"]),
            "成交量": float(latest.get("volume", latest.get("amount", 0))),
            "日期": str(latest["date"]),
        }
    except Exception:
        return {}

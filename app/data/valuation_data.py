import akshare as ak
import pandas as pd
from datetime import datetime


def get_valuation_history(symbol: str, market: str = "A") -> dict:
    """获取PE/PB历史数据。"""
    if market == "HK":
        return _get_hk_valuation(symbol)

    result = {}
    for indicator, key in [("市盈率(TTM)", "pe"), ("市净率", "pb")]:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period="全部")
            df["date"] = pd.to_datetime(df["date"])
            df = df.dropna(subset=["value"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["value"])
            result[key] = df
        except Exception:
            result[key] = pd.DataFrame()
    return result


def _get_hk_valuation(symbol: str) -> dict:
    """从 yfinance 获取港股当前 PE/PB 快照。"""
    from app.data.financial_data import _yf_info_safe
    info = _yf_info_safe(symbol)
    result = {}

    pe = info.get("trailingPE")
    if pe:
        result["pe"] = pd.DataFrame([{"date": datetime.now(), "value": float(pe)}])
    else:
        result["pe"] = pd.DataFrame()

    pb = info.get("priceToBook")
    if pb:
        result["pb"] = pd.DataFrame([{"date": datetime.now(), "value": float(pb)}])
    else:
        result["pb"] = pd.DataFrame()

    return result

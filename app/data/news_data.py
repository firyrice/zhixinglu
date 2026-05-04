import akshare as ak
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_stock_news(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取个股近期新闻。"""
    try:
        df = ak.stock_news_em(symbol=symbol)
        return df.head(30)
    except Exception:
        return pd.DataFrame()


def get_research_reports(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取个股近期研报。"""
    if market == "HK":
        return pd.DataFrame()
    try:
        df = ak.stock_research_report_em(symbol=symbol)
        return df.head(10)
    except Exception:
        return pd.DataFrame()


def get_stock_announcements(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取个股公告。"""
    if market == "HK":
        return pd.DataFrame()
    try:
        df = ak.stock_notice_report(symbol=symbol)
        return df.head(20)
    except Exception:
        return pd.DataFrame()


def get_profit_forecast(symbol: str, market: str = "A") -> dict:
    """获取个股盈利预测数据。"""
    if market == "HK":
        return _get_hk_forecast(symbol)

    result = {}

    try:
        result["eps"] = ak.stock_profit_forecast_ths(symbol=symbol, indicator="预测年报每股收益")
    except Exception:
        result["eps"] = pd.DataFrame()

    try:
        result["net_profit"] = ak.stock_profit_forecast_ths(symbol=symbol, indicator="预测年报净利润")
    except Exception:
        result["net_profit"] = pd.DataFrame()

    try:
        em_df = ak.stock_profit_forecast_em(symbol="")
        stock_row = em_df[em_df["代码"] == symbol]
        result["ratings"] = stock_row.iloc[0].to_dict() if not stock_row.empty else {}
    except Exception:
        result["ratings"] = {}

    return result


def _get_hk_forecast(symbol: str) -> dict:
    """从 yfinance 获取港股分析师数据。"""
    from app.data.financial_data import _get_yf_ticker, _yf_info_safe

    result = {"eps": pd.DataFrame(), "net_profit": pd.DataFrame(), "ratings": {}}

    try:
        ticker = _get_yf_ticker(symbol)
        recs = ticker.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[-1] if len(recs) > 0 else {}
            buy = int(latest.get("strongBuy", 0)) + int(latest.get("buy", 0))
            hold = int(latest.get("hold", 0))
            sell = int(latest.get("sell", 0)) + int(latest.get("strongSell", 0))
            result["ratings"] = {
                "机构投资评级(近六个月)-买入": buy,
                "机构投资评级(近六个月)-增持": 0,
                "机构投资评级(近六个月)-中性": hold,
                "机构投资评级(近六个月)-减持": 0,
                "机构投资评级(近六个月)-卖出": sell,
                "研报数": buy + hold + sell,
            }
    except Exception:
        pass

    try:
        info = _yf_info_safe(symbol)
        targets = {}
        for key in ["targetHighPrice", "targetLowPrice", "targetMeanPrice", "targetMedianPrice"]:
            if info.get(key):
                targets[key] = info[key]
        if targets:
            result["ratings"]["目标价_最高"] = targets.get("targetHighPrice", "")
            result["ratings"]["目标价_最低"] = targets.get("targetLowPrice", "")
            result["ratings"]["目标价_均值"] = targets.get("targetMeanPrice", "")
    except Exception:
        pass

    return result

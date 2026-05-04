import akshare as ak
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)

_yf_ticker_cache: dict = {}


def _to_yf_ticker(symbol: str) -> str:
    """港股代码转 yfinance ticker: '00700' -> '0700.HK'"""
    return symbol.lstrip("0") + ".HK" if symbol.lstrip("0") else symbol + ".HK"


def _get_yf_ticker(symbol: str):
    """获取 yfinance Ticker 对象，带缓存。"""
    if symbol not in _yf_ticker_cache:
        import yfinance as yf
        ticker_str = _to_yf_ticker(symbol)
        _yf_ticker_cache[symbol] = yf.Ticker(ticker_str)
    return _yf_ticker_cache[symbol]


def _yf_info_safe(symbol: str) -> dict:
    """安全获取 yfinance info，带重试。"""
    ticker = _get_yf_ticker(symbol)
    for attempt in range(3):
        try:
            return ticker.info
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
    return {}


def get_financial_summary(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取综合财务摘要。"""
    if market == "HK":
        return _get_hk_financial_summary(symbol)
    df = ak.stock_financial_abstract_ths(symbol=symbol)
    return df


def _get_hk_financial_summary(symbol: str) -> pd.DataFrame:
    """从 yfinance 构造港股财务摘要，格式兼容 A 股。优先用季报，回退到年报。"""
    info = _yf_info_safe(symbol)
    ticker = _get_yf_ticker(symbol)
    rows = []

    try:
        qstmt = ticker.quarterly_income_stmt
        stmt = ticker.income_stmt
        bs = ticker.balance_sheet

        use_quarterly = qstmt is not None and not qstmt.empty and len(qstmt.columns) >= 2
        source = qstmt if use_quarterly else stmt

        if source is not None and not source.empty:
            prev_revenues = {}
            for col in reversed(list(source.columns)):
                period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
                revenue = _safe_val(source, "Total Revenue", col)
                net_income = _safe_val(source, "Net Income", col)
                gross_profit = _safe_val(source, "Gross Profit", col)

                gross_margin = None
                if revenue and gross_profit and revenue > 0:
                    gross_margin = round(gross_profit / revenue * 100, 2)

                rev_growth = ""
                ni_growth = ""
                if use_quarterly:
                    yoy_key = col - pd.DateOffset(years=1) if hasattr(col, 'year') else None
                else:
                    yoy_key = None

                prev_rev = prev_revenues.get("revenue")
                prev_ni = prev_revenues.get("net_income")
                if not use_quarterly and prev_rev and revenue and prev_rev > 0:
                    rev_growth = f"{(revenue - prev_rev) / abs(prev_rev) * 100:.2f}"
                if not use_quarterly and prev_ni and net_income and prev_ni > 0:
                    ni_growth = f"{(net_income - prev_ni) / abs(prev_ni) * 100:.2f}"

                roe_val = ""
                if bs is not None and not bs.empty:
                    equity = _safe_val(bs, "Stockholders Equity", col)
                    if equity and net_income and equity > 0:
                        roe_val = f"{net_income / equity * 100:.2f}"

                row = {
                    "报告期": period,
                    "营业总收入": f"{revenue / 1e8:.2f}亿" if revenue else "",
                    "净利润": f"{net_income / 1e8:.2f}亿" if net_income else "",
                    "销售毛利率": f"{gross_margin}" if gross_margin is not None else "",
                    "净资产收益率": roe_val,
                    "营业总收入同比增长率": rev_growth,
                    "净利润同比增长率": ni_growth,
                }
                rows.append(row)
                prev_revenues = {"revenue": revenue, "net_income": net_income}
    except Exception:
        logger.exception("Failed to get HK financial summary")

    if not rows and info:
        roe = info.get("returnOnEquity")
        rev_growth = info.get("revenueGrowth")
        rows.append({
            "报告期": "最新",
            "营业总收入": f"{info.get('totalRevenue', 0) / 1e8:.2f}亿" if info.get("totalRevenue") else "",
            "净利润": f"{info.get('netIncomeToCommon', 0) / 1e8:.2f}亿" if info.get("netIncomeToCommon") else "",
            "销售毛利率": f"{info.get('grossMargins', 0) * 100:.2f}" if info.get("grossMargins") else "",
            "净资产收益率": f"{roe * 100:.2f}" if roe else "",
            "营业总收入同比增长率": f"{rev_growth * 100:.2f}" if rev_growth else "",
        })

    if rows and info:
        latest = rows[-1]
        if not latest.get("营业总收入同比增长率") and info.get("revenueGrowth"):
            latest["营业总收入同比增长率"] = f"{info['revenueGrowth'] * 100:.2f}"
        if not latest.get("净利润同比增长率") and info.get("earningsGrowth"):
            latest["净利润同比增长率"] = f"{info['earningsGrowth'] * 100:.2f}"
        if not latest.get("净资产收益率") and info.get("returnOnEquity"):
            latest["净资产收益率"] = f"{info['returnOnEquity'] * 100:.2f}"

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _safe_val(df, row_name, col):
    """安全获取 DataFrame 中的值。"""
    try:
        if row_name in df.index:
            v = df.at[row_name, col]
            if pd.notna(v):
                return float(v)
    except Exception:
        pass
    return None


def get_cash_flow_sheet(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取现金流量表数据。"""
    if market == "HK":
        return _get_hk_cashflow(symbol)
    df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
    return df


def _get_hk_cashflow(symbol: str) -> pd.DataFrame:
    """从 yfinance 获取港股现金流，列名转中文以兼容现有解析。"""
    ticker = _get_yf_ticker(symbol)
    try:
        cf = ticker.cashflow
        if cf is None or cf.empty:
            return pd.DataFrame()

        rows = []
        for col in cf.columns:
            period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            row = {"报告期": period}
            if "Operating Cash Flow" in cf.index:
                row["经营活动产生的现金流量净额"] = cf.at["Operating Cash Flow", col]
            if "Capital Expenditure" in cf.index:
                row["购建固定资产、无形资产和其他长期资产支付的现金"] = abs(cf.at["Capital Expenditure", col])
            if "Free Cash Flow" in cf.index:
                row["自由现金流"] = cf.at["Free Cash Flow", col]
            rows.append(row)

        rows.reverse()
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def get_profit_sheet(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取利润表数据。"""
    if market == "HK":
        return _get_hk_profit(symbol)
    df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
    return df


def _get_hk_profit(symbol: str) -> pd.DataFrame:
    """从 yfinance 获取港股利润表。"""
    ticker = _get_yf_ticker(symbol)
    try:
        stmt = ticker.income_stmt
        if stmt is None or stmt.empty:
            return pd.DataFrame()

        rows = []
        for col in stmt.columns:
            period = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            row = {"报告期": period}
            mapping = {
                "Total Revenue": "营业总收入",
                "Cost Of Revenue": "营业成本",
                "Gross Profit": "毛利润",
                "Operating Income": "营业利润",
                "Net Income": "净利润",
            }
            for en_key, cn_key in mapping.items():
                if en_key in stmt.index:
                    row[cn_key] = stmt.at[en_key, col]
            rows.append(row)

        rows.reverse()
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def get_dividend_yield(symbol: str, market: str = "A") -> pd.DataFrame:
    """获取个股历史分红率。"""
    if market == "HK":
        return _get_hk_dividend(symbol)

    try:
        df = ak.stock_fhps_detail_ths(symbol=symbol)
    except Exception:
        return pd.DataFrame()

    rows = []
    for _, row in df.iterrows():
        period = str(row.get("报告期", ""))
        rate = str(row.get("税前分红率", ""))
        if rate == "--" or rate.strip() == "":
            continue
        rate_val = rate.replace("%", "").strip()
        try:
            rate_num = float(rate_val)
        except ValueError:
            continue

        if "年报" in period:
            year = period.replace("年报", "").strip()
            rows.append({"报告期": f"{year}-12-31", "股息率": rate_num})
        elif "中报" in period:
            year = period.replace("中报", "").strip()
            rows.append({"报告期": f"{year}-06-30", "股息率": rate_num})

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _get_hk_dividend(symbol: str) -> pd.DataFrame:
    """从 yfinance 获取港股股息数据。"""
    info = _yf_info_safe(symbol)
    div_yield = info.get("dividendYield")
    if div_yield:
        return pd.DataFrame([{"报告期": "最新", "股息率": round(div_yield * 100, 2)}])
    return pd.DataFrame()


def get_stock_info(symbol: str, market: str = "A") -> dict:
    """获取个股基本信息。"""
    if market == "HK":
        return _get_hk_stock_info(symbol)

    info = {}
    try:
        df = get_financial_summary(symbol)
        if not df.empty:
            latest = df.iloc[-1]
            info["每股净资产"] = latest.get("每股净资产", "")
            info["净资产收益率"] = latest.get("净资产收益率", "")
            info["销售毛利率"] = latest.get("销售毛利率", "")
            info["营业总收入"] = latest.get("营业总收入", "")
            info["净利润"] = latest.get("净利润", "")
    except Exception:
        pass

    try:
        from app.data.market_data import get_realtime_quote
        quote = get_realtime_quote(symbol)
        if quote:
            price = quote.get("最新价", 0)
            shares = quote.get("流通股本", 0)
            if price and shares:
                info["总市值"] = price * shares
                info["最新价"] = price
    except Exception:
        pass

    return info


def _get_hk_stock_info(symbol: str) -> dict:
    """从 yfinance 获取港股基本信息。"""
    info_data = _yf_info_safe(symbol)
    if not info_data:
        return {}

    result = {}
    mc = info_data.get("marketCap")
    if mc:
        result["总市值"] = mc

    price = info_data.get("currentPrice") or info_data.get("regularMarketPrice")
    if price:
        result["最新价"] = price

    bv = info_data.get("bookValue")
    if bv:
        result["每股净资产"] = str(bv)

    roe = info_data.get("returnOnEquity")
    if roe:
        result["净资产收益率"] = f"{roe * 100:.2f}"

    gm = info_data.get("grossMargins")
    if gm:
        result["销售毛利率"] = f"{gm * 100:.2f}"

    rev = info_data.get("totalRevenue")
    if rev:
        result["营业总收入"] = f"{rev / 1e8:.2f}亿"

    ni = info_data.get("netIncomeToCommon")
    if ni:
        result["净利润"] = f"{ni / 1e8:.2f}亿"

    result["行业"] = info_data.get("industry", "")
    result["板块"] = info_data.get("sector", "")

    return result

import akshare as ak
import pandas as pd
import logging

logger = logging.getLogger(__name__)

_stock_list_cache: pd.DataFrame | None = None
_hk_stock_list_cache: pd.DataFrame | None = None


def _get_stock_list() -> pd.DataFrame:
    global _stock_list_cache
    if _stock_list_cache is None:
        _stock_list_cache = ak.stock_info_a_code_name()
    return _stock_list_cache


def _get_hk_stock_list() -> pd.DataFrame:
    global _hk_stock_list_cache
    if _hk_stock_list_cache is None:
        try:
            df = ak.stock_hk_spot_em()
            _hk_stock_list_cache = df[["代码", "名称"]].rename(columns={"代码": "code", "名称": "name"})
        except Exception:
            logger.exception("Failed to load HK stock list")
            _hk_stock_list_cache = pd.DataFrame(columns=["code", "name"])
    return _hk_stock_list_cache


def search_stock(query: str) -> list[dict]:
    """根据股票代码或名称模糊搜索，返回A股和港股匹配结果。"""
    query = query.strip()
    if not query:
        return []

    results = []

    df_a = _get_stock_list()
    if query.isdigit():
        exact = df_a[df_a["code"] == query]
        if not exact.empty:
            results.extend([{**r, "market": "A"} for r in exact.to_dict("records")])
        partial = df_a[(df_a["code"].str.contains(query)) & (~df_a["code"].isin(exact["code"]))]
        results.extend([{**r, "market": "A"} for r in partial.head(5).to_dict("records")])
    else:
        matched = df_a[df_a["name"].str.contains(query, na=False)]
        results.extend([{**r, "market": "A"} for r in matched.head(5).to_dict("records")])

    try:
        df_hk = _get_hk_stock_list()
        if not df_hk.empty:
            if query.isdigit():
                hk_exact = df_hk[df_hk["code"] == query]
                if not hk_exact.empty:
                    results.extend([{**r, "market": "HK"} for r in hk_exact.to_dict("records")])
                hk_partial = df_hk[(df_hk["code"].str.contains(query)) & (~df_hk["code"].isin(hk_exact["code"]))]
                results.extend([{**r, "market": "HK"} for r in hk_partial.head(5).to_dict("records")])
            else:
                hk_matched = df_hk[df_hk["name"].str.contains(query, na=False)]
                results.extend([{**r, "market": "HK"} for r in hk_matched.head(5).to_dict("records")])
    except Exception:
        logger.exception("HK stock search failed")

    return results[:10]

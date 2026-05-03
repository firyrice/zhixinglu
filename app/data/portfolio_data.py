import akshare as ak
import pandas as pd
import time
import re
import requests

_spot_cache = {"data": None, "ts": 0}
_SPOT_TTL = 60

_individual_cache = {}
_INDIVIDUAL_TTL = 300

_tencent_cache = {}
_TENCENT_TTL = 60

_profile_cache = {}
_PROFILE_TTL = 3600

_MAX_RETRIES = 2
_RETRY_DELAY = 0.5


def _retry(fn, *args, **kwargs):
    for i in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, ConnectionError, OSError):
            if i < _MAX_RETRIES - 1:
                time.sleep(_RETRY_DELAY * (i + 1))
    raise ConnectionError(f"{fn.__name__} failed after {_MAX_RETRIES} retries")


def _get_spot_data() -> pd.DataFrame:
    now = time.time()
    if _spot_cache["data"] is not None and (now - _spot_cache["ts"]) < _SPOT_TTL:
        return _spot_cache["data"]
    try:
        df = _retry(ak.stock_zh_a_spot_em)
        _spot_cache["data"] = df
        _spot_cache["ts"] = now
        return df
    except Exception:
        if _spot_cache["data"] is not None:
            return _spot_cache["data"]
        return pd.DataFrame()


def _tencent_prefix(symbol: str) -> str:
    return ("sh" if symbol.startswith("6") else "sz") + symbol


def _get_tencent_quotes(symbols: list[str]) -> dict:
    """通过腾讯财经 API 批量获取行情（价格、市值、PE）。"""
    now = time.time()
    uncached, result = [], {}
    for s in symbols:
        if s in _tencent_cache and (now - _tencent_cache[s]["ts"]) < _TENCENT_TTL:
            result[s] = _tencent_cache[s]["data"]
        else:
            uncached.append(s)
    if not uncached:
        return result

    codes = [_tencent_prefix(s) for s in uncached]
    try:
        resp = requests.get(
            "https://qt.gtimg.cn/q=" + ",".join(codes),
            timeout=10,
        )
        resp.encoding = "gbk"
        for line in resp.text.strip().split(";"):
            m = re.search(r'v_(s[hz]\d{6})="(.+)"', line)
            if not m:
                continue
            code = m.group(1)[2:]
            f = m.group(2).split("~")
            if len(f) < 50:
                continue
            price = float(f[3] or 0)
            prev_close = float(f[4] or 0)
            data = {
                "name": f[1],
                "price": price,
                "prev_close": prev_close,
                "change_pct": float(f[32] or 0),
                "total_mv": float(f[45] or 0) * 1e8,
                "pe_ttm": float(f[39] or 0),
                "dividend_yield": 0,
            }
            _tencent_cache[code] = {"data": data, "ts": now}
            result[code] = data
    except Exception:
        pass
    return result


def _get_individual_info(symbol: str) -> dict:
    """通过东方财富获取单股详情（含行业分类）。"""
    now = time.time()
    if symbol in _individual_cache and (now - _individual_cache[symbol]["ts"]) < _INDIVIDUAL_TTL:
        return _individual_cache[symbol]["data"]
    try:
        df = _retry(ak.stock_individual_info_em, symbol=symbol)
        info = {}
        for _, row in df.iterrows():
            info[row["item"]] = row["value"]
        data = {
            "name": str(info.get("股票简称", "")),
            "price": float(info.get("最新", 0) or 0),
            "total_mv": float(info.get("总市值", 0) or 0),
            "industry": str(info.get("行业", "未知")),
        }
        _individual_cache[symbol] = {"data": data, "ts": now}
        return data
    except Exception:
        if symbol in _individual_cache:
            return _individual_cache[symbol]["data"]
        return {}

def get_batch_quotes(symbols: list[str]) -> dict:
    """批量获取实时行情。优先东方财富，备选腾讯财经。"""
    df = _get_spot_data()
    result = {}
    missing = []

    for symbol in symbols:
        if not df.empty:
            row = df[df["代码"] == symbol]
            if not row.empty:
                r = row.iloc[0]
                result[symbol] = {
                    "name": str(r.get("名称", "")),
                    "price": float(r.get("最新价", 0) or 0),
                    "prev_close": float(r.get("昨收", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "total_mv": float(r.get("总市值", 0) or 0),
                    "pe_ttm": float(r.get("市盈率-动态", 0) or 0),
                    "dividend_yield": float(r.get("股息率", 0) or 0),
                }
                continue
        missing.append(symbol)

    if missing:
        tencent = _get_tencent_quotes(missing)
        result.update(tencent)
    return result


def get_stock_profiles(symbols: list[str]) -> dict:
    """获取股票元信息：行业、总市值、市值分类、PE、股息率。"""
    df = _get_spot_data()
    tencent = _get_tencent_quotes(symbols)
    result = {}

    for symbol in symbols:
        if symbol in _profile_cache and (time.time() - _profile_cache[symbol]["ts"]) < _PROFILE_TTL:
            result[symbol] = _profile_cache[symbol]["data"]
            continue

        em_info = _get_individual_info(symbol)
        tq = tencent.get(symbol, {})

        name = em_info.get("name") or tq.get("name", "")
        industry = em_info.get("industry", "未知") if em_info else "未知"
        total_mv = em_info.get("total_mv", 0) if em_info else tq.get("total_mv", 0)
        pe_ttm = tq.get("pe_ttm", 0)
        dividend_yield = 0.0

        if not df.empty:
            row = df[df["代码"] == symbol]
            if not row.empty:
                r = row.iloc[0]
                if not name:
                    name = str(r.get("名称", ""))
                if total_mv == 0:
                    total_mv = float(r.get("总市值", 0) or 0)
                pe_ttm = pe_ttm or float(r.get("市盈率-动态", 0) or 0)
                dividend_yield = float(r.get("股息率", 0) or 0)

        if not name and not total_mv:
            continue

        mv_billion = total_mv / 1e8
        if mv_billion >= 1000:
            cap_type = "大盘股"
        elif mv_billion >= 200:
            cap_type = "中盘股"
        else:
            cap_type = "小盘股"

        data = {
            "name": name,
            "industry": industry,
            "total_mv": total_mv,
            "cap_type": cap_type,
            "pe_ttm": pe_ttm,
            "dividend_yield": dividend_yield,
        }
        _profile_cache[symbol] = {"data": data, "ts": time.time()}
        result[symbol] = data
    return result

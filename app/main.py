import asyncio
import base64
import logging
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from app.data.stock_search import search_stock
from app.data.portfolio_data import get_batch_quotes, get_stock_profiles
from app.report.generator import generate_report
from app.ai.vision_client import parse_portfolio_screenshot

logger = logging.getLogger(__name__)

app = FastAPI(title="知行录 - 单股深度分析")

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/search")
async def api_search(q: str = ""):
    results = await asyncio.to_thread(search_stock, q)
    return JSONResponse(results)


@app.get("/api/report/{symbol}")
async def api_report(symbol: str):
    async def stream():
        async for chunk in generate_report(symbol):
            yield chunk
    return StreamingResponse(stream(), media_type="text/html; charset=utf-8")


@app.get("/api/quotes")
async def api_quotes(symbols: str = ""):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return JSONResponse({})
    try:
        result = await asyncio.to_thread(get_batch_quotes, symbol_list)
    except Exception:
        result = {}
    return JSONResponse(result)


@app.get("/api/stock-profiles")
async def api_stock_profiles(symbols: str = ""):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return JSONResponse({})
    try:
        result = await asyncio.to_thread(get_stock_profiles, symbol_list)
    except Exception:
        result = {}
    return JSONResponse(result)


@app.post("/api/parse-screenshot")
async def api_parse_screenshot(file: UploadFile = File(...)):
    """接收持仓截图，调用 VLM 解析并反查股票代码。"""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        return JSONResponse({"error": "文件过大，请上传10MB以内的图片"}, status_code=400)

    mime = file.content_type or "image/png"
    img_b64 = base64.b64encode(content).decode()

    try:
        raw_stocks = await asyncio.to_thread(parse_portfolio_screenshot, img_b64, mime)
    except Exception as e:
        logger.exception("VLM parse failed")
        return JSONResponse({"error": f"截图识别失败：{e}"}, status_code=500)

    if not raw_stocks:
        return JSONResponse({"error": "未能从截图中识别到持仓数据"}, status_code=400)

    results = []
    for item in raw_stocks:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        shares = item.get("shares")
        market_value = item.get("market_value")
        pnl = item.get("pnl")

        code = None
        try:
            matches = await asyncio.to_thread(search_stock, name)
            if matches:
                code = matches[0]["code"]
        except Exception:
            pass

        cost_price = None
        if shares and shares > 0 and market_value is not None and pnl is not None:
            cost_price = round((market_value - pnl) / shares, 4)

        results.append({
            "name": name,
            "code": code,
            "shares": shares,
            "cost_price": cost_price,
            "market_value": market_value,
            "pnl": pnl,
        })

    return JSONResponse({"stocks": results})

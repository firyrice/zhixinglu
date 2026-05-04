import asyncio
import base64
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from app.data.stock_search import search_stock
from app.data.portfolio_data import get_batch_quotes, get_stock_profiles
from app.report.generator import generate_report
from app.ai.vision_client import parse_portfolio_screenshot
from app.models.history import init_db, save_report, list_reports, get_report, delete_report
from app.models.letter import (
    init_letter_db, save_letter, list_letters, get_letter,
    get_latest_letter, mark_read, delete_letter,
)
from app.report.letter_generator import generate_letter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_letter_db()
    yield


app = FastAPI(title="知行录 - 单股深度分析", lifespan=lifespan)

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
    results = await asyncio.to_thread(search_stock, symbol)
    stock_code = results[0]["code"] if results else symbol
    stock_name = results[0]["name"] if results else symbol
    market = results[0].get("market", "A") if results else "A"

    async def stream():
        chunks = []
        async for chunk in generate_report(symbol):
            chunks.append(chunk)
            yield chunk
        full_html = "".join(chunks)
        try:
            await asyncio.to_thread(save_report, stock_code, stock_name, full_html, market)
        except Exception:
            logger.exception("Failed to save report to history")

    return StreamingResponse(stream(), media_type="text/html; charset=utf-8")


@app.get("/api/quotes")
async def api_quotes(symbols: str = "", market: str = "A"):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return JSONResponse({})
    try:
        result = await asyncio.to_thread(get_batch_quotes, symbol_list, market)
    except Exception:
        result = {}
    return JSONResponse(result)


@app.get("/api/stock-profiles")
async def api_stock_profiles(symbols: str = "", market: str = "A"):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return JSONResponse({})
    try:
        result = await asyncio.to_thread(get_stock_profiles, symbol_list, market)
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
        market = "A"
        try:
            matches = await asyncio.to_thread(search_stock, name)
            if matches:
                code = matches[0]["code"]
                market = matches[0].get("market", "A")
        except Exception:
            pass

        cost_price = None
        if shares and shares > 0 and market_value is not None and pnl is not None:
            cost_price = round((market_value - pnl) / shares, 4)

        results.append({
            "name": name,
            "code": code,
            "market": market,
            "shares": shares,
            "cost_price": cost_price,
            "market_value": market_value,
            "pnl": pnl,
        })

    return JSONResponse({"stocks": results})


@app.get("/api/history")
async def api_history():
    reports = await asyncio.to_thread(list_reports)
    return JSONResponse(reports)


@app.get("/api/history/{report_id}")
async def api_history_detail(report_id: int):
    report = await asyncio.to_thread(get_report, report_id)
    if not report:
        return JSONResponse({"error": "记录不存在"}, status_code=404)
    return HTMLResponse(report["html_content"])


@app.delete("/api/history/{report_id}")
async def api_history_delete(report_id: int):
    deleted = await asyncio.to_thread(delete_report, report_id)
    if not deleted:
        return JSONResponse({"error": "记录不存在"}, status_code=404)
    return JSONResponse({"ok": True})


@app.post("/api/letter/generate")
async def api_letter_generate(request: Request):
    body = await request.json()
    holdings = body.get("holdings", [])
    if not holdings:
        return JSONResponse({"error": "请先添加持仓"}, status_code=400)

    date_str = datetime.now().strftime("%Y-%m-%d")
    snapshot = json.dumps(holdings, ensure_ascii=False)

    async def stream():
        chunks = []
        async for chunk in generate_letter(holdings):
            chunks.append(chunk)
            yield chunk
        full_html = "".join(chunks)
        summary = ""
        m = re.search(r'class="opening">(.*?)</div>', full_html, re.DOTALL)
        if m:
            summary = m.group(1).strip()[:200]

        daily_return = 0.0
        stock_count = len(holdings)
        try:
            from app.data.portfolio_data import get_batch_quotes
            codes = [h["code"] for h in holdings]
            quotes = await asyncio.to_thread(get_batch_quotes, codes)
            total_cost = sum(h["cost_price"] * h["shares"] for h in holdings)
            daily_pnl = sum(
                (quotes.get(h["code"], {}).get("price", 0) - quotes.get(h["code"], {}).get("prev_close", 0)) * h["shares"]
                for h in holdings
            )
            if total_cost > 0:
                daily_return = daily_pnl / total_cost * 100
        except Exception:
            pass

        try:
            save_letter(date_str, full_html, summary, snapshot, daily_return, stock_count)
        except Exception:
            logger.exception("Failed to save letter")

    return StreamingResponse(stream(), media_type="text/html; charset=utf-8")


@app.get("/api/letters")
async def api_letters():
    letters = await asyncio.to_thread(list_letters)
    return JSONResponse(letters)


@app.get("/api/letter/latest")
async def api_letter_latest():
    letter = await asyncio.to_thread(get_latest_letter)
    if not letter:
        return JSONResponse(None)
    return JSONResponse(letter)


@app.get("/api/letter/{letter_id}")
async def api_letter_detail(letter_id: int):
    letter = await asyncio.to_thread(get_letter, letter_id)
    if not letter:
        return JSONResponse({"error": "来信不存在"}, status_code=404)
    return JSONResponse({
        "id": letter["id"], "date": letter["date"], "content": letter["content"],
        "is_read": letter["is_read"], "daily_return": letter["daily_return"],
        "stock_count": letter["stock_count"],
    })


@app.put("/api/letter/{letter_id}/read")
async def api_letter_read(letter_id: int):
    updated = await asyncio.to_thread(mark_read, letter_id)
    if not updated:
        return JSONResponse({"error": "来信不存在"}, status_code=404)
    return JSONResponse({"ok": True})


@app.delete("/api/letter/{letter_id}")
async def api_letter_delete(letter_id: int):
    deleted = await asyncio.to_thread(delete_letter, letter_id)
    if not deleted:
        return JSONResponse({"error": "来信不存在"}, status_code=404)
    return JSONResponse({"ok": True})

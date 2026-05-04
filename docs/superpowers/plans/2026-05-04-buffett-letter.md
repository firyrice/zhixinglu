# 巴菲特来信 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily "Buffett's Letter" feature that generates personalized investment analysis reports in Buffett's voice, based on the user's portfolio holdings.

**Architecture:** Server-side letter generation via LLM (reusing existing SSE streaming pattern from `generate_report`), stored in SQLite (same DB as history). Frontend adds 3 views: homepage letter section, letter detail page, and mailbox list page. Client-side portfolio data is sent to the backend at generation time.

**Tech Stack:** FastAPI (SSE streaming), SQLite, OpenAI SDK (via existing `llm_client.py`), akshare (market data), vanilla JS frontend (no build step)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app/models/letter.py` | SQLite CRUD for `buffett_letters` table |
| `app/data/letter_data.py` | Data aggregation: fetches all market/stock data needed for letter generation |
| `app/ai/letter_prompts.py` | 5 module prompts + opening/closing prompts in Buffett's voice |
| `app/report/letter_generator.py` | Async generator that orchestrates data fetch → LLM calls → HTML output |
| `app/report/letter_template.py` | HTML/CSS template functions for letter rendering |
| `app/main.py` (modify) | Register 6 new API endpoints |
| `app/static/index.html` (modify) | Add homepage letter section, new routes, new JS includes |
| `app/static/js/letter.js` | Letter detail page: streaming render, mark-as-read |
| `app/static/js/mailbox.js` | Mailbox list page: load, delete, navigate |

---

## Task 1: Database Model (`app/models/letter.py`)

**Files:**
- Create: `app/models/letter.py`
- Modify: `app/main.py` (import and call `init_letter_db` in lifespan)

- [ ] **Step 1: Create `app/models/letter.py`**

```python
import sqlite3
import os
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_letter_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffett_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '致我的合伙人',
            content TEXT NOT NULL,
            summary TEXT,
            portfolio_snapshot TEXT,
            daily_return REAL,
            stock_count INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_letter(date: str, content: str, summary: str, portfolio_snapshot: str,
                daily_return: float, stock_count: int) -> int:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM buffett_letters WHERE date = ?", (date,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE buffett_letters SET content=?, summary=?, portfolio_snapshot=?, daily_return=?, stock_count=?, is_read=0, created_at=? WHERE id=?",
            (content, summary, portfolio_snapshot, daily_return, stock_count, datetime.now().isoformat(), existing["id"])
        )
        conn.commit()
        row_id = existing["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO buffett_letters (date, content, summary, portfolio_snapshot, daily_return, stock_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date, content, summary, portfolio_snapshot, daily_return, stock_count, datetime.now().isoformat())
        )
        conn.commit()
        row_id = cursor.lastrowid
    conn.close()
    return row_id


def list_letters(limit: int = 50) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, date, title, summary, daily_return, stock_count, is_read, created_at FROM buffett_letters ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_letter(letter_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM buffett_letters WHERE id = ?", (letter_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_letter() -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, date, title, summary, daily_return, stock_count, is_read, created_at FROM buffett_letters ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_read(letter_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("UPDATE buffett_letters SET is_read = 1 WHERE id = ?", (letter_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_letter(letter_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM buffett_letters WHERE id = ?", (letter_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
```

- [ ] **Step 2: Add `init_letter_db()` to app lifespan in `app/main.py`**

Add import at top:
```python
from app.models.letter import init_letter_db
```

Modify the lifespan function:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_letter_db()
    yield
```

- [ ] **Step 3: Verify server starts without error**

Run: `python3 run.py`
Expected: Server starts, `buffett_letters` table created in `history.db`

- [ ] **Step 4: Commit**

```bash
git add app/models/letter.py app/main.py
git commit -m "feat(letter): add SQLite model for buffett_letters"
```

---

## Task 2: Data Aggregation (`app/data/letter_data.py`)

**Files:**
- Create: `app/data/letter_data.py`

This module fetches all market and stock data needed for the 5 letter modules. It reuses existing data functions from `portfolio_data.py`, `market_data.py`, and `news_data.py`.

- [ ] **Step 1: Create `app/data/letter_data.py`**

```python
import asyncio
import akshare as ak
import pandas as pd
from datetime import datetime

from app.data.portfolio_data import get_batch_quotes
from app.data.market_data import get_stock_kline
from app.data.news_data import get_stock_news


def get_market_overview() -> dict:
    """获取大盘概览数据：主要指数、成交额、北向资金。"""
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
    """获取单只股票的详细数据：资金流向、技术指标等。"""
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
    """聚合来信所需的全部数据。

    Args:
        holdings: 持仓列表，每项包含 code, name, shares, cost_price, market
    Returns:
        包含 quotes, market_overview, stock_details, stock_news 的字典
    """
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
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from app.data.letter_data import fetch_letter_data; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/data/letter_data.py
git commit -m "feat(letter): add data aggregation for letter generation"
```

---

## Task 3: AI Prompts (`app/ai/letter_prompts.py`)

**Files:**
- Create: `app/ai/letter_prompts.py`

- [ ] **Step 1: Create `app/ai/letter_prompts.py`**

```python
BUFFETT_SYSTEM = """你是沃伦·巴菲特，正在给你的合伙人写每日来信。

写作风格：
- 第一人称，称呼读者为"合伙人"或"亲爱的合伙人"
- 语言亲和、幽默、有智慧感，像朋友聊天
- 善用比喻和生活化的例子解释复杂概念
- 强调安全边际、护城河、长期复利等价值投资核心理念
- 对市场短期波动保持淡定，对基本面变化保持警觉
- 策略建议务实谨慎，绝不打鸡血，一切指向风险可控和长期可盈利
- 用中文写作，但保持巴菲特的思维方式和表达习惯
- 输出纯文本，用markdown格式，不要输出HTML标签"""


def letter_opening_prompt(portfolio_summary: str, market_summary: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请写一段来信的开场白（100-150字）。

今日组合表现：
{portfolio_summary}

今日市场概况：
{market_summary}

要求：
- 自然地引出今天的市场和组合情况
- 用巴菲特标志性的幽默和智慧开场
- 不要用"亲爱的合伙人"开头（信头已有称呼）
- 直接输出开场白文字"""}
    ]


def letter_module1_prompt(portfolio_summary: str, stock_details: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请逐一点评以下持仓股的今日表现。

组合总览：
{portfolio_summary}

各股详情：
{stock_details}

对每只股票，请包含：
1. 当日涨跌和成交量变化的简要数据
2. 资金动向（主力资金、北向资金如有）
3. 技术面关键信号（均线位置、支撑压力位）
4. 你的价值投资视角点评（这只股票的走势是否符合买入逻辑，短期波动是否值得担心）

用巴菲特的口吻，每只股票3-5句话。直接输出，不要加模块标题。"""}
    ]


def letter_module2_prompt(holdings_info: str, news_data: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请从以下新闻中精选3-5条与持仓最相关的高价值信息。

持仓股票：
{holdings_info}

相关新闻：
{news_data}

筛选标准：宁缺毋滥，只选被广泛讨论的、可能对股价有重大影响的信息。

对每条信息，请输出：
1. 影响等级：重大 或 关注
2. 关联股票
3. 信息标题和来源
4. 你的解读：分析该信息对股价的潜在影响，给出价值投资视角的判断

如果没有值得关注的信息，就说"今天没有什么值得大惊小怪的消息"。直接输出，不要加模块标题。"""}
    ]


def letter_module3_prompt(market_data: str, holdings_sectors: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请从价值投资视角解读今日市场大势。

市场数据：
{market_data}

持仓相关板块：
{holdings_sectors}

请覆盖：
1. 大盘走势和成交额变化
2. 板块轮动（重点关注与持仓相关的板块）
3. 北向资金动向
4. 重要政策或外围因素（如有）

用巴菲特的视角解读，不要罗列数据，要有观点和判断。3-5段话。直接输出，不要加模块标题。"""}
    ]


def letter_module4_prompt(portfolio_analysis: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请对以下投资组合进行风险体检。

组合分析数据：
{portfolio_analysis}

请从以下维度评估：
1. 仓位集中度：单股最大仓位是否过高（>30%预警），前3大持仓占比
2. 行业暴露：是否过度集中在某个行业
3. 个股止损预警：亏损超过15%的个股需要特别关注
4. 整体风险评估：组合是否健康，有什么需要改善的

用巴菲特的口吻，像一个关心合伙人的老朋友一样指出问题。务实、不回避问题，但也不制造恐慌。直接输出，不要加模块标题。"""}
    ]


def letter_module5_prompt(full_context: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""基于以下完整分析，给出具体的操作建议。

完整分析上下文：
{full_context}

对每只持仓股，给出：
1. 操作方向：持有 / 关注加仓 / 考虑减仓
2. 理由：简明扼要，1-2句话
3. 风险提示：该操作需要注意什么

要求：
- 务实、谨慎、具体
- 每条建议都要有明确的数据依据
- 风险可控是第一原则
- 不打鸡血，不制造恐慌

直接输出，不要加模块标题。"""}
    ]


def letter_closing_prompt(key_points: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""请写一段来信的结尾寄语（50-80字）。

今日要点回顾：
{key_points}

要求：
- 用巴菲特标志性的价值投资哲学金句收尾
- 给合伙人信心和耐心
- 简短有力，余味悠长
- 直接输出结尾文字"""}
    ]
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from app.ai.letter_prompts import BUFFETT_SYSTEM; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/ai/letter_prompts.py
git commit -m "feat(letter): add Buffett-voice prompts for 5 letter modules"
```

---

## Task 4: HTML Template (`app/report/letter_template.py`)

**Files:**
- Create: `app/report/letter_template.py`

- [ ] **Step 1: Create `app/report/letter_template.py`**

```python
from datetime import datetime


def letter_html_head(date_str: str = "") -> str:
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>巴菲特来信 · {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Noto+Sans+SC:wght@300;400;500&family=IBM+Plex+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #FAF7F2; --card: #FFFFFF; --module-bg: #f8f5f0;
  --green: #2C3E2D; --gold: #C9A961; --up: #D97757; --down: #7A9B6E;
  --text: #2A2A2A; --text-sec: #6B6B6B; --border: #e0d8cc;
  --font-serif: 'Noto Serif SC', serif;
  --font-sans: 'Noto Sans SC', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:var(--font-sans); line-height:1.8; }}
.letter-container {{ max-width:720px; margin:0 auto; padding:32px 48px; }}
@media (max-width:768px) {{ .letter-container {{ padding:20px 16px; }} }}
.letter-header {{ text-align:center; margin-bottom:28px; }}
.letter-header .label {{ font-size:12px; color:var(--gold); letter-spacing:3px; margin-bottom:8px; }}
.letter-header h1 {{ font-size:24px; color:var(--green); font-family:var(--font-serif); }}
@media (max-width:768px) {{ .letter-header h1 {{ font-size:20px; }} }}
.letter-header .divider {{ width:40px; height:2px; background:var(--gold); margin:12px auto; }}
.letter-date {{ font-size:13px; color:var(--text-sec); margin-top:8px; }}
.opening {{ font-family:var(--font-serif); font-size:15px; font-style:italic; padding:0 16px; margin-bottom:28px; color:var(--text); }}
@media (max-width:768px) {{ .opening {{ font-size:14px; padding:0; }} }}
.module-title {{ display:flex; align-items:center; gap:8px; margin-bottom:16px; margin-top:32px; }}
.module-title .bar {{ width:4px; height:20px; background:var(--gold); border-radius:2px; }}
.module-title h2 {{ font-size:16px; font-family:var(--font-serif); color:var(--green); font-weight:bold; }}
@media (max-width:768px) {{ .module-title h2 {{ font-size:15px; }} .module-title .bar {{ width:3px; height:16px; }} }}
.module-sep {{ text-align:center; margin:24px 0; color:var(--border); letter-spacing:8px; }}
.data-cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }}
@media (max-width:768px) {{ .data-cards {{ grid-template-columns:repeat(2,1fr); gap:8px; }} }}
.data-card {{ background:var(--card); border-radius:8px; padding:12px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
@media (max-width:768px) {{ .data-card {{ padding:10px; }} }}
.data-card .label {{ font-size:11px; color:var(--text-sec); }}
@media (max-width:768px) {{ .data-card .label {{ font-size:10px; }} }}
.data-card .value {{ font-size:18px; font-weight:bold; font-family:var(--font-mono); }}
@media (max-width:768px) {{ .data-card .value {{ font-size:16px; }} }}
.data-card .value.up {{ color:var(--up); }}
.data-card .value.down {{ color:var(--down); }}
.stock-card {{ background:var(--card); border-radius:8px; padding:16px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
@media (max-width:768px) {{ .stock-card {{ padding:12px; }} }}
.stock-card .header {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }}
.stock-card .name {{ font-weight:bold; color:var(--green); font-size:14px; }}
.stock-card .change {{ font-family:var(--font-mono); font-size:13px; }}
.stock-card .meta {{ font-size:13px; color:var(--text-sec); margin-bottom:8px; }}
@media (max-width:768px) {{ .stock-card .meta {{ font-size:12px; }} }}
.stock-card .comment {{ font-family:var(--font-serif); font-style:italic; font-size:14px; color:var(--text); line-height:1.6; }}
@media (max-width:768px) {{ .stock-card .comment {{ font-size:13px; }} }}
.news-card {{ background:var(--module-bg); border-radius:8px; padding:16px; margin-bottom:12px; }}
@media (max-width:768px) {{ .news-card {{ padding:12px; }} }}
.news-card .level {{ font-size:11px; color:#fff; padding:2px 8px; border-radius:4px; }}
.news-card .level.major {{ background:var(--up); }}
.news-card .level.watch {{ background:var(--gold); }}
.news-card .title {{ font-size:15px; font-weight:bold; color:var(--green); margin:8px 0 6px; }}
@media (max-width:768px) {{ .news-card .title {{ font-size:14px; }} }}
.news-card .source {{ font-size:14px; color:var(--text); margin-bottom:8px; }}
@media (max-width:768px) {{ .news-card .source {{ font-size:13px; }} }}
.news-card .interpret {{ font-size:14px; color:var(--text); padding:12px; background:#e8e4dc; border-radius:6px; font-style:italic; }}
@media (max-width:768px) {{ .news-card .interpret {{ font-size:13px; padding:10px; }} }}
.strategy-card {{ background:var(--card); border-radius:8px; padding:16px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
@media (max-width:768px) {{ .strategy-card {{ padding:12px; }} }}
.strategy-card.hold {{ border-left:3px solid var(--down); }}
.strategy-card.buy {{ border-left:3px solid var(--gold); }}
.strategy-card.sell {{ border-left:3px solid var(--up); }}
.strategy-tag {{ font-size:12px; color:#fff; padding:2px 10px; border-radius:4px; font-weight:bold; }}
@media (max-width:768px) {{ .strategy-tag {{ font-size:10px; padding:1px 6px; }} }}
.strategy-tag.hold {{ background:var(--down); }}
.strategy-tag.buy {{ background:var(--gold); }}
.strategy-tag.sell {{ background:var(--up); }}
.risk-note {{ font-size:13px; color:var(--text-sec); margin-top:6px; padding:6px 8px; background:var(--module-bg); border-radius:4px; }}
@media (max-width:768px) {{ .risk-note {{ font-size:12px; }} }}
.closing {{ border-top:1px solid var(--border); padding-top:24px; margin-top:32px; }}
.closing .words {{ font-family:var(--font-serif); font-size:15px; font-style:italic; line-height:1.8; padding:0 16px; }}
@media (max-width:768px) {{ .closing .words {{ font-size:14px; padding:0; }} }}
.closing .signature {{ text-align:right; color:var(--text-sec); font-size:14px; margin-top:16px; font-family:var(--font-serif); }}
.disclaimer {{ margin-top:24px; padding:12px; background:var(--module-bg); border-radius:6px; font-size:12px; color:#999; text-align:center; }}
.md-text {{ white-space:pre-wrap; }}
.md-text p {{ margin-bottom:12px; }}
</style>
</head>
<body>
<div class="letter-container">
  <div class="letter-header">
    <div class="label">BUFFETT\'S LETTER</div>
    <h1>致我的合伙人</h1>
    <div class="divider"></div>
    <div class="letter-date">{date_str} · 收盘总结</div>
  </div>
'''


def letter_opening_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="opening">{escaped}</div>\n'


def letter_module_html(number: int, title: str, content: str) -> str:
    return f'''<div class="module-title"><div class="bar"></div><h2>{title}</h2></div>
{content}
<div class="module-sep">· · ·</div>
'''


def letter_data_cards_html(daily_pnl: float, daily_pct: float, total_asset: float,
                           total_pnl_pct: float, vs_hs300: float) -> str:
    pnl_cls = "up" if daily_pnl >= 0 else "down"
    pnl_sign = "+" if daily_pnl >= 0 else ""
    total_cls = "up" if total_pnl_pct >= 0 else "down"
    total_sign = "+" if total_pnl_pct >= 0 else ""
    vs_cls = "up" if vs_hs300 >= 0 else "down"
    vs_sign = "+" if vs_hs300 >= 0 else ""
    return f'''<div class="data-cards">
  <div class="data-card"><div class="label">今日盈亏</div><div class="value {pnl_cls}">{pnl_sign}{daily_pnl:,.0f}</div><div class="label" style="color:var(--{pnl_cls})">{pnl_sign}{daily_pct:.2f}%</div></div>
  <div class="data-card"><div class="label">总资产</div><div class="value">{total_asset:,.0f}</div></div>
  <div class="data-card"><div class="label">持仓盈亏</div><div class="value {total_cls}">{total_sign}{total_pnl_pct:.2f}%</div></div>
  <div class="data-card"><div class="label">vs 沪深300</div><div class="value {vs_cls}">{vs_sign}{vs_hs300:.1f}%</div></div>
</div>'''


def letter_closing_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<div class="closing">
  <div class="words">{escaped}</div>
  <div class="signature">— 你的投资伙伴，沃伦</div>
</div>
<div class="disclaimer">以上内容由AI生成，仅供参考，不构成投资建议。投资有风险，决策需谨慎。</div>
'''


def letter_html_footer() -> str:
    return '</div>\n</body>\n</html>'
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from app.report.letter_template import letter_html_head; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/report/letter_template.py
git commit -m "feat(letter): add HTML/CSS template for letter rendering"
```

---

## Task 5: Letter Generator (`app/report/letter_generator.py`)

**Files:**
- Create: `app/report/letter_generator.py`

This is the core orchestrator — an async generator that fetches data, calls LLM for each module, and yields HTML chunks for streaming. Follows the same pattern as `app/report/generator.py`.

- [ ] **Step 1: Create `app/report/letter_generator.py`**

```python
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
    return f'<div class="md-text">{escaped}</div>'


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


def _build_stock_details_str(holdings: list[dict], quotes: dict, details: dict) -> str:
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


def _build_news_str(holdings: list[dict], stock_news: dict) -> str:
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


def _build_market_str(market: dict) -> str:
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


def _build_risk_str(holdings: list[dict], quotes: dict, summary: dict) -> str:
    lines = []
    sorted_h = sorted(holdings, key=lambda h: quotes.get(h["code"], {}).get("price", 0) * h["shares"], reverse=True)
    total = summary["total_asset"]
    if total > 0:
        for i, h in enumerate(sorted_h):
            mv = quotes.get(h["code"], {}).get("price", 0) * h["shares"]
            pct = mv / total * 100
            pnl_pct = ((quotes.get(h["code"], {}).get("price", 0) - h["cost_price"]) / h["cost_price"] * 100) if h["cost_price"] > 0 else 0
            lines.append(f"{h['name']}: 仓位{pct:.1f}%, 盈亏{pnl_pct:+.1f}%")
        top3_pct = sum(quotes.get(h["code"], {}).get("price", 0) * h["shares"] / total * 100 for h in sorted_h[:3])
        lines.append(f"前3大持仓占比: {top3_pct:.1f}%")
    sectors = {}
    for h in holdings:
        sector = h.get("sector", "未知")
        mv = quotes.get(h["code"], {}).get("price", 0) * h["shares"]
        sectors[sector] = sectors.get(sector, 0) + mv
    if sectors and total > 0:
        lines.append("行业分布: " + ", ".join(f"{k}({v/total*100:.0f}%)" for k, v in sorted(sectors.items(), key=lambda x: -x[1])))
    return "\n".join(lines) if lines else "持仓数据不足，无法进行风险分析"


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
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from app.report.letter_generator import generate_letter; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/report/letter_generator.py
git commit -m "feat(letter): add letter generator with 5-module streaming output"
```

---

## Task 6: API Endpoints (`app/main.py`)

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add imports at top of `app/main.py`**

Add after existing imports:
```python
from app.models.letter import (
    init_letter_db, save_letter, list_letters, get_letter,
    get_latest_letter, mark_read, delete_letter,
)
from app.report.letter_generator import generate_letter
```

- [ ] **Step 2: Add the 6 letter API endpoints**

Add after the existing `/api/history/{report_id}` DELETE endpoint:

```python
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
        if full_html:
            import re
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
            daily_pnl = sum((quotes.get(h["code"], {}).get("price", 0) - quotes.get(h["code"], {}).get("prev_close", 0)) * h["shares"] for h in holdings)
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
    return JSONResponse({"id": letter["id"], "date": letter["date"], "content": letter["content"],
                         "is_read": letter["is_read"], "daily_return": letter["daily_return"],
                         "stock_count": letter["stock_count"]})


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
```

- [ ] **Step 3: Add missing imports at top of `app/main.py`**

Add `json` and `datetime` imports if not already present:
```python
import json
from datetime import datetime
```

- [ ] **Step 4: Verify server starts**

Run: `python3 run.py`
Expected: Server starts without errors, new endpoints registered

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat(letter): add 6 API endpoints for letter CRUD and generation"
```

---

## Task 7: Frontend — Letter Detail Page (`app/static/js/letter.js`)

**Files:**
- Create: `app/static/js/letter.js`

- [ ] **Step 1: Create `app/static/js/letter.js`**

```javascript
const Letter = {
  async render(id) {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div style="max-width:720px;margin:0 auto;padding:20px 16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/')">← 返回</span>
          <span class="text-secondary text-sm" id="letter-date"></span>
        </div>
        <div id="letter-content"><p class="text-secondary text-sm">加载中...</p></div>
      </div>`;

    if (id === 'generate') {
      this._generate();
    } else {
      this._loadExisting(id);
    }
  },

  async _generate() {
    const holdings = Store.getHeldStocks();
    if (!holdings.length) {
      document.getElementById('letter-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">请先在持仓页添加股票</p>';
      return;
    }

    const payload = holdings.map(s => ({
      code: s.code, name: s.name, shares: s.shares,
      cost_price: s.cost_price, market: s.market || 'A'
    }));

    document.getElementById('letter-date').textContent = '正在撰写...';
    const contentEl = document.getElementById('letter-content');
    contentEl.innerHTML = '';

    try {
      const resp = await fetch('/api/letter/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings: payload })
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let html = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        html += decoder.decode(value, { stream: true });
        contentEl.innerHTML = html;
      }

      document.getElementById('letter-date').textContent =
        new Date().toLocaleDateString('zh-CN');

      // Re-render home letter section on next visit
      if (typeof renderMarkdown === 'function') {
        contentEl.querySelectorAll('.md-text').forEach(el => renderMarkdown(el));
      }
    } catch (e) {
      contentEl.innerHTML = '<p class="text-secondary">生成失败，请重试</p>';
    }
  },

  async _loadExisting(id) {
    try {
      const resp = await fetch('/api/letter/' + id);
      if (!resp.ok) throw new Error('not found');
      const data = await resp.json();

      document.getElementById('letter-date').textContent = data.date;
      document.getElementById('letter-content').innerHTML = data.content;

      if (!data.is_read) {
        fetch('/api/letter/' + id + '/read', { method: 'PUT' });
      }
    } catch {
      document.getElementById('letter-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">来信不存在</p>';
    }
  }
};
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/letter.js
git commit -m "feat(letter): add letter detail page with streaming render"
```

---

## Task 8: Frontend — Mailbox Page (`app/static/js/mailbox.js`)

**Files:**
- Create: `app/static/js/mailbox.js`

- [ ] **Step 1: Create `app/static/js/mailbox.js`**

```javascript
const Mailbox = {
  async render() {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div style="max-width:600px;margin:0 auto;padding:40px 24px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
          <div>
            <h1 class="serif" style="font-size:20px;color:var(--accent-green);margin:0;">信箱</h1>
            <p class="text-secondary text-sm" id="mailbox-stats"></p>
          </div>
          <span style="color:var(--accent-gold);cursor:pointer;font-size:13px;" onclick="Router.navigate('/')">← 返回首页</span>
        </div>
        <div id="mailbox-list"><p class="text-secondary text-sm">加载中...</p></div>
      </div>`;
    this._loadList();
  },

  async _loadList() {
    try {
      const resp = await fetch('/api/letters');
      const letters = await resp.json();
      const listEl = document.getElementById('mailbox-list');
      const statsEl = document.getElementById('mailbox-stats');

      if (!letters.length) {
        listEl.innerHTML = '<p class="text-secondary" style="text-align:center;margin-top:60px;">还没有来信</p>';
        statsEl.textContent = '';
        return;
      }

      const unread = letters.filter(l => !l.is_read).length;
      statsEl.textContent = `共 ${letters.length} 封 · ${unread} 封未读`;

      listEl.innerHTML = letters.map(l => {
        const isUnread = !l.is_read;
        const retPct = l.daily_return != null ? (l.daily_return >= 0 ? '+' : '') + l.daily_return.toFixed(2) + '%' : '';
        const retCls = l.daily_return >= 0 ? 'text-up' : 'text-down';
        return `
          <div style="background:#fff;border-radius:${isUnread ? '10' : '8'}px;padding:${isUnread ? '18px 20px' : '14px 16px'};margin-bottom:${isUnread ? '10' : '8'}px;
            box-shadow:0 ${isUnread ? '2px 8px' : '1px 3px'} rgba(0,0,0,${isUnread ? '0.06' : '0.04'});
            cursor:pointer;${isUnread ? 'border-left:4px solid var(--accent-gold);' : 'opacity:0.85;'}
            display:flex;align-items:flex-start;justify-content:space-between;transition:box-shadow 0.2s;"
            onmouseover="this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)'"
            onmouseout="this.style.boxShadow='0 ${isUnread ? '2px 8px' : '1px 3px'} rgba(0,0,0,${isUnread ? '0.06' : '0.04'})'"
            onclick="Router.navigate('/letter/${l.id}')">
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                ${isUnread ? '<div style="width:6px;height:6px;background:var(--accent-gold);border-radius:50%;"></div>' : ''}
                <span style="font-size:${isUnread ? '15' : '14'}px;${isUnread ? 'font-weight:bold;' : ''}color:var(--accent-green);font-family:var(--font-serif);">致我的合伙人</span>
                ${isUnread ? '<span style="font-size:10px;color:var(--accent-gold);background:#faf3e6;padding:1px 4px;border-radius:2px;">未读</span>' : ''}
              </div>
              <div class="text-secondary" style="font-size:12px;line-height:1.4;margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                ${l.summary || ''}
              </div>
              <div style="display:flex;gap:8px;font-size:11px;color:#999;">
                <span>${l.date}</span>
                <span>·</span>
                <span>${l.stock_count || 0}只持仓股</span>
                ${retPct ? `<span>·</span><span class="${retCls}">${retPct}</span>` : ''}
              </div>
            </div>
            <button onclick="event.stopPropagation();Mailbox.deleteLetter(${l.id})" title="删除"
              style="border:none;background:none;cursor:pointer;padding:6px;opacity:0.3;transition:opacity 0.2s;margin-left:8px;"
              onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='0.3'">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D97757" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>`;
      }).join('');
    } catch {
      document.getElementById('mailbox-list').innerHTML = '<p class="text-secondary">加载失败</p>';
    }
  },

  async deleteLetter(id) {
    if (!confirm('确定删除这封来信？')) return;
    await fetch('/api/letter/' + id, { method: 'DELETE' });
    this._loadList();
  }
};
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/mailbox.js
git commit -m "feat(letter): add mailbox list page"
```

---

## Task 9: Frontend — Homepage Integration & Routes (`app/static/index.html`)

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add JS includes**

In `index.html`, add before the closing `</head>` or after existing script includes (after `<script src="/static/js/charts.js"></script>`):

```html
<script src="/static/js/letter.js"></script>
<script src="/static/js/mailbox.js"></script>
```

- [ ] **Step 2: Add homepage letter section to `renderHome()`**

In the `renderHome()` function, add a letter section variable before the `app.innerHTML` assignment. Insert `${letterSection}` into the template right after the search hint `<p>` and before `${entryCard}`:

```javascript
  let letterSection = `
    <div id="home-letter-section" style="width:100%;margin:24px 0 16px;">
      <div id="letter-card-container" style="text-align:left;">
        <div style="border:2px dashed var(--border);border-radius:12px;padding:24px;text-align:center;">
          <div style="font-size:36px;margin-bottom:8px;opacity:0.3;">✉</div>
          <div style="font-size:15px;color:var(--accent-green);font-weight:bold;margin-bottom:4px;">还没有今日来信</div>
          <div class="text-secondary text-sm" style="margin-bottom:16px;">收盘后点击生成，巴菲特会为你写一封专属分析</div>
          <button class="btn btn-gold" onclick="Router.navigate('/letter/generate')"
            style="background:var(--accent-green);color:var(--bg-primary);padding:10px 24px;border-radius:8px;font-size:14px;font-weight:bold;border:none;cursor:pointer;"
            id="generate-letter-btn">生成今日来信</button>
          <div style="margin-top:12px;">
            <span style="font-size:12px;color:var(--accent-gold);cursor:pointer;" onclick="Router.navigate('/mailbox')">查看历史来信 →</span>
          </div>
        </div>
      </div>
    </div>`;
```

Then add a call to load the latest letter status after `if (hasStocks) loadHomeSummary();`:

```javascript
  loadHomeLetterStatus();
```

- [ ] **Step 3: Add `loadHomeLetterStatus()` function**

Add this function in the `<script>` section:

```javascript
async function loadHomeLetterStatus() {
  const container = document.getElementById('letter-card-container');
  if (!container) return;
  try {
    const resp = await fetch('/api/letter/latest');
    const letter = await resp.json();
    if (!letter) return; // keep empty state

    const today = new Date().toISOString().slice(0, 10);
    const isToday = letter.date === today;
    const isUnread = !letter.is_read;

    if (isToday && isUnread) {
      const retPct = letter.daily_return != null ? (letter.daily_return >= 0 ? '+' : '') + letter.daily_return.toFixed(2) + '%' : '';
      container.innerHTML = `
        <div style="background:linear-gradient(135deg,#2C3E2D 0%,#3a5240 100%);border-radius:12px;padding:24px;color:#FAF7F2;position:relative;overflow:hidden;cursor:pointer;text-align:left;"
          onclick="Router.navigate('/letter/${letter.id}')">
          <div style="position:absolute;right:-20px;top:-20px;font-size:120px;opacity:0.06;">✉</div>
          <div style="font-size:12px;color:#C9A961;letter-spacing:2px;margin-bottom:8px;">巴菲特来信 · 今日</div>
          <div class="serif" style="font-size:18px;font-weight:bold;margin-bottom:8px;">致我的合伙人</div>
          <div style="font-size:14px;opacity:0.8;margin-bottom:16px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
            ${letter.summary || ''}
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;gap:12px;font-size:13px;opacity:0.7;">
              <span>${letter.date}</span><span>·</span><span>${letter.stock_count || 0}只持仓股</span>
            </div>
            <div style="background:#C9A961;color:#2C3E2D;padding:6px 16px;border-radius:6px;font-size:13px;font-weight:bold;">阅读来信 →</div>
          </div>
        </div>`;
    } else if (isToday) {
      // Today's letter exists but already read — show generate button with "重新生成" option
      const btn = document.getElementById('generate-letter-btn');
      if (btn) btn.textContent = '重新生成今日来信';
    }
  } catch { /* keep empty state */ }
}
```

- [ ] **Step 4: Register new routes**

Add before `Router.start();`:

```javascript
Router.register('/letter/:id', (params) => Letter.render(params.id));
Router.register('/mailbox', () => Mailbox.render());
```

- [ ] **Step 5: Update router to support parameterized routes**

Check `app/static/js/router.js` — if it doesn't support `:id` params, update the `Router.start()` / route matching to handle `/letter/123` and `/letter/generate`. The simplest approach: in the route handler, parse the hash manually:

```javascript
Router.register('/letter', () => {
  const hash = window.location.hash;
  const parts = hash.replace('#/letter/', '').split('/');
  const id = parts[0];
  Letter.render(id);
});
```

- [ ] **Step 6: Verify the full flow in browser**

Run: `python3 run.py`
Open: `http://localhost:5001`
Expected:
1. Homepage shows letter section with "生成今日来信" button
2. Click button → navigates to letter detail, streams content
3. After generation, return to home → shows unread notification card
4. Click "查看历史来信" → mailbox list page
5. Mobile viewport (375px) renders correctly

- [ ] **Step 7: Commit**

```bash
git add app/static/index.html app/static/js/letter.js app/static/js/mailbox.js
git commit -m "feat(letter): integrate letter section into homepage, add routes"
```

---

## Task 10: End-to-End Verification

- [ ] **Step 1: Start server and test full flow**

```bash
python3 run.py
```

Open `http://localhost:5001` in browser. Test:
1. Add at least 2 stocks in portfolio if not already present
2. Return to homepage, click "生成今日来信"
3. Verify streaming render works (content appears progressively)
4. Verify letter is saved (check `/api/letters` returns it)
5. Return to homepage — verify unread notification card appears
6. Click notification → letter detail loads, marked as read
7. Navigate to mailbox → letter shows as read
8. Delete letter from mailbox → confirm dialog → removed
9. Test mobile viewport (Chrome DevTools, 375px width)

- [ ] **Step 2: Test edge cases**

1. No holdings → generate button disabled/shows hint
2. Generate twice same day → overwrites previous letter
3. Refresh during generation → partial content visible

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Buffett's Letter feature (功能3)"
```

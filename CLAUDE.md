# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

知行录 (zhixinglu) — AI-powered Chinese A-share stock analysis and portfolio tracking tool for retail investors. A FastAPI web app that fetches market data via akshare, runs it through LLM analysis modules, and streams HTML reports to the browser. Also provides a client-side portfolio tracker with VLM-powered screenshot import, and a daily "Buffett's Letter" portfolio digest.

## Commands

```bash
pip install -r requirements.txt    # Install dependencies
python3 run.py                     # Dev server at http://0.0.0.0:5001 (hot reload)
```

No test framework or linter is configured.

## Environment

Requires a `.env` file (see `.env.example`):

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_BASE_URL` | OpenAI-compatible API endpoint for report generation | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key for LLM | (required) |
| `LLM_MODEL` | Model name | `claude-4.6-sonnet` |
| `VLM_BASE_URL` | Vision model endpoint for screenshot parsing | falls back to `LLM_BASE_URL` |
| `VLM_API_KEY` | API key for VLM | falls back to `LLM_API_KEY` |
| `VLM_MODEL` | Vision model name | `gemini-3.1-pro` |

Config loaded in `app/config.py` via python-dotenv. Both LLM and VLM use the OpenAI SDK.

## Architecture

**Entry point**: `run.py` → `app/main.py` (FastAPI + uvicorn)

### Three features, different data strategies

1. **Stock analysis reports** — server-side. Data fetched from akshare, processed through LLM, streamed as HTML. Reports saved to SQLite (`app/data/history.db`) via `app/models/history.py`.
2. **Portfolio tracking** — client-side. Holdings stored in `localStorage` (via `store.js`). Server only provides real-time quotes and stock profiles; no server-side portfolio state.
3. **Buffett's Letter (daily digest)** — hybrid. Client sends holdings to server, server fetches market data + news, LLM generates structured JSON analysis, server renders HTML cards and streams back. Letters saved to SQLite via `app/models/letter.py`. Same-day regeneration overwrites the previous letter.
4. **Trade Diagnosis (交易诊断)** — hybrid. User inputs trade intent (stock + direction + shares) via structured form, client sends trade intent + holdings to server, server fetches target stock data + portfolio data + market data in parallel, LLM generates 5 analysis dimensions (value, position, timing, market, conclusion) as structured JSON, rendered to HTML cards and streamed back. Supports follow-up chat. Saved to SQLite via `app/models/diagnosis.py`.

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/search?q=` | Stock symbol/name search |
| `GET` | `/api/report/{symbol}` | Stream HTML report (also saves to history DB) |
| `GET` | `/api/quotes?symbols=` | Batch real-time quotes (comma-separated codes) |
| `GET` | `/api/stock-profiles?symbols=` | Stock metadata: industry, cap size, PE, dividend yield |
| `POST` | `/api/parse-screenshot` | Upload broker screenshot → VLM extracts holdings |
| `GET` | `/api/history` | List saved reports |
| `GET/DELETE` | `/api/history/{id}` | Get/delete a saved report |
| `POST` | `/api/letter/generate` | Generate daily letter (body: `{holdings: [...]}`) — streams HTML |
| `GET` | `/api/letters` | List saved letters |
| `GET` | `/api/letter/latest` | Get most recent letter metadata |
| `GET` | `/api/letter/{id}` | Get letter detail (full HTML content) |
| `PUT` | `/api/letter/{id}/read` | Mark letter as read |
| `DELETE` | `/api/letter/{id}` | Delete a letter |
| `POST` | `/api/diagnosis/generate` | Generate trade diagnosis (body: `{trade_intent, holdings}`) — streams HTML |
| `POST` | `/api/diagnosis/chat` | Follow-up chat on diagnosis (body: `{diagnosis_id, message, history}`) — streams text |
| `GET` | `/api/diagnosis/history` | List saved diagnoses |
| `GET` | `/api/diagnosis/{id}` | Get diagnosis detail (HTML + chat history) |
| `DELETE` | `/api/diagnosis/{id}` | Delete a diagnosis |

### Backend layers

| Layer | Path | Role |
|-------|------|------|
| Data | `app/data/` | akshare wrappers. `portfolio_data.py` has dual-source quotes (东方财富 primary, 腾讯财经 fallback) with in-memory TTL caches. `market_data.py` caches K-line data. `letter_data.py` aggregates market overview, stock details, and news for the daily letter. |
| AI | `app/ai/` | `llm_client.py` wraps OpenAI SDK (chat, chat_with_search, chat_stream). `vision_client.py` wraps VLM for screenshot parsing. `prompts.py` has 10 Chinese system prompts for stock reports. `letter_prompts.py` has prompts for the daily letter (Buffett persona for opening/closing, analyst persona for structured JSON modules). `diagnosis_prompts.py` has prompts for trade diagnosis (5 analysis dimensions + conclusion + chat). `dcf_model.py` for two-stage DCF. `valuation_models.py` runs 5 classic methods via the `valueinvest` library. |
| Report | `app/report/` | `generator.py` orchestrates 10 modules as an async generator yielding HTML chunks. `letter_generator.py` orchestrates 3 analysis sections (stock cards, news, market temperature) as an async generator — LLM outputs structured JSON, generator parses and renders to HTML cards. `diagnosis_generator.py` orchestrates 5 analysis dimensions for trade diagnosis. `html_template.py` for report CSS/HTML. `letter_template.py` for letter CSS and card components. `diagnosis_template.py` for diagnosis CSS and card components. `chart_config.py` for ECharts configs. |
| Models | `app/models/` | `history.py` — SQLite CRUD for analysis report history. `letter.py` — SQLite CRUD for Buffett letters (one per day, upsert on same date). `diagnosis.py` — SQLite CRUD for trade diagnoses (with chat history). DB auto-initialized on app startup via lifespan handler. |

### Frontend (SPA)

`app/static/index.html` — vanilla HTML/JS, no build step.

| File | Role |
|------|------|
| `js/router.js` | Hash-based router (`#/`, `#/portfolio`, `#/letter/{id}`, `#/mailbox`, `#/diagnosis`, `#/diagnosis/{id}`, `#/diagnosis/history`) |
| `js/store.js` | Portfolio state in `localStorage` with quote caching (1hr TTL) |
| `js/portfolio.js` | Portfolio dashboard: holdings table, P&L, sector/cap/valuation pie charts |
| `js/add-stock.js` | Add stock dialog with search |
| `js/import-screenshot.js` | Screenshot upload → VLM parse → batch import |
| `js/charts.js` | ECharts rendering for report charts |
| `js/letter.js` | Letter generation (streaming) and display; renders both new card format and legacy markdown |
| `js/mailbox.js` | Letter history list with read/unread status |
| `js/diagnosis.js` | Trade diagnosis: form input, streaming report, follow-up chat, history list |

## Key Patterns

- All akshare calls are blocking and wrapped in `asyncio.to_thread()`.
- LLM/VLM calls use the OpenAI SDK pointed at configured base URLs. `chat_with_search` tries web search tool first, falls back to plain chat.
- Report generation is a single async generator; each of 10 modules yields an HTML chunk for progressive rendering.
- Letter generation uses structured JSON output from LLM: prompts request JSON arrays/objects, `_parse_json()` handles code-fence stripping, fallback renders basic cards on parse failure. The generator enriches LLM output with real market data (e.g. correcting `change_pct` from actual quotes).
- Portfolio data uses a dual-source strategy: 东方财富 `stock_zh_a_spot_em` for batch quotes, 腾讯财经 HTTP API as fallback. Both have in-memory TTL caches.
- `valuation_models.py` bridges akshare data formats to the `valueinvest` library's `SimpleNamespace`-based API.
- Prompts are in Chinese, written for retail investors ("人话版").
- Trade diagnosis follows the same async generator pattern as letter generation: parallel data fetch → sequential LLM calls per dimension → stream HTML cards. Supports follow-up chat with full diagnosis context as system prompt.

## Product Documents

PRD and design specs in `PRD/`:
- `功能1_单股深度分析.md`, `功能2_持仓追踪.md`, `功能3_决策日志.md`, `功能4_交易诊断.md` — feature specs
- `设计规范_UI_UX.md` — UI/UX design system
- `项目思考.md` — product strategy, competitive analysis, and commercialization roadmap
- `项目规划.md` — project planning

Design docs in `docs/superpowers/specs/`:
- `2026-05-04-trade-diagnosis-design.md` — trade diagnosis feature design (product + technical)

## Data Sources

Stock data is fetched via [akshare](https://github.com/akfamily/akshare):
- Documentation: https://akshare.akfamily.xyz/data/stock/stock.html


## Language
请用中文来和我交互，包括回答问题，提问问题等

## Claude Code 行为配置

- 所有 subagent（子代理）调用必须使用 `model: "opus"` 参数，不要使用 haiku 或 sonnet 模型（API 网关不支持这些模型）

写入超过300行的文件的时候，记得分批写入（每次写入不超过300行），避免一次写入太多报错 "Write failed"
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

知行录 (zhixinglu) — AI-powered Chinese A-share stock analysis and portfolio tracking tool for retail investors. A FastAPI web app that fetches market data via akshare, runs it through LLM analysis modules, and streams HTML reports to the browser. Also provides a client-side portfolio tracker with VLM-powered screenshot import.

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

### Two features, different data strategies

1. **Stock analysis reports** — server-side. Data fetched from akshare, processed through LLM, streamed as HTML. Reports saved to SQLite (`app/data/history.db`) via `app/models/history.py`.
2. **Portfolio tracking** — client-side. Holdings stored in `localStorage` (via `store.js`). Server only provides real-time quotes and stock profiles; no server-side portfolio state.

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

### Backend layers

| Layer | Path | Role |
|-------|------|------|
| Data | `app/data/` | akshare wrappers. `portfolio_data.py` has dual-source quotes (东方财富 primary, 腾讯财经 fallback) with in-memory TTL caches. `market_data.py` caches K-line data. |
| AI | `app/ai/` | `llm_client.py` wraps OpenAI SDK (chat, chat_with_search, chat_stream). `vision_client.py` wraps VLM for screenshot parsing. `prompts.py` has 10 Chinese system prompts. `dcf_model.py` for two-stage DCF. `valuation_models.py` runs 5 classic methods via the `valueinvest` library. |
| Report | `app/report/` | `generator.py` orchestrates 10 modules as an async generator yielding HTML chunks. `html_template.py` for CSS/HTML. `chart_config.py` for ECharts configs. |
| Models | `app/models/` | `history.py` — SQLite CRUD for analysis report history. DB auto-initialized on app startup via lifespan handler. |

### Frontend (SPA)

`app/static/index.html` — vanilla HTML/JS, no build step.

| File | Role |
|------|------|
| `js/router.js` | Hash-based router (`#/`, `#/portfolio`) |
| `js/store.js` | Portfolio state in `localStorage` with quote caching (1hr TTL) |
| `js/portfolio.js` | Portfolio dashboard: holdings table, P&L, sector/cap/valuation pie charts |
| `js/add-stock.js` | Add stock dialog with search |
| `js/import-screenshot.js` | Screenshot upload → VLM parse → batch import |
| `js/charts.js` | ECharts rendering for report charts |

## Key Patterns

- All akshare calls are blocking and wrapped in `asyncio.to_thread()`.
- LLM/VLM calls use the OpenAI SDK pointed at configured base URLs. `chat_with_search` tries web search tool first, falls back to plain chat.
- Report generation is a single async generator; each of 10 modules yields an HTML chunk for progressive rendering.
- Portfolio data uses a dual-source strategy: 东方财富 `stock_zh_a_spot_em` for batch quotes, 腾讯财经 HTTP API as fallback. Both have in-memory TTL caches.
- `valuation_models.py` bridges akshare data formats to the `valueinvest` library's `SimpleNamespace`-based API.
- Prompts are in Chinese, written for retail investors ("人话版").

## Product Documents

PRD and design specs in `PRD/`:
- `知行录_产品需求文档_v1.0.md` — master PRD
- `功能1_单股深度分析.md` through `功能6_个人投资Agent.md` — feature specs
- `设计规范_UI_UX.md` — UI/UX design system

## Data Sources

Stock data is fetched via [akshare](https://github.com/akfamily/akshare):
- Documentation: https://akshare.akfamily.xyz/data/stock/stock.html

请用中文来和我交互，包括回答问题，提问问题等

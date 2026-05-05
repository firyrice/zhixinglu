# 交易诊断功能设计文档

## Context

用户在做出交易决策前，缺少一个系统性的"第二意见"。现有功能中，单股深度分析关注单只股票的全面分析，巴菲特来信关注每日持仓回顾，但都不针对"我即将做的这笔交易"给出诊断。交易诊断填补这个空白：用户输入交易意图，系统结合持仓、市场、估值等多维度数据，给出结构化的诊断意见。

## 1. 产品功能定义

### 1.1 核心定位

交易诊断是用户做出交易决策前的"第二意见"。用户有了交易想法（买入/卖出/加仓/减仓），在执行前来这里获得系统性的分析意见。不替用户做决策，而是帮用户看到自己可能忽略的维度。

### 1.2 用户流程

```
首页独立入口 "交易诊断"
    ↓
结构化表单：选择股票 + 交易方向 + 数量/金额 + 目标价格(可选) + 交易理由(可选)
    ↓
系统获取 Context：用户持仓(localStorage) + 最新巴菲特来信(DB) + 实时行情
    ↓
流式生成诊断报告（5个分析维度的卡片 + 综合结论）
    ↓
报告底部：追问对话框
    ↓
报告自动保存到 SQLite，可在"诊断记录"中回看
```

### 1.3 交易输入表单

| 字段 | 类型 | 说明 | 必填 |
|------|------|------|------|
| 股票 | 搜索选择 | 复用现有搜索接口，支持代码/名称 | 是 |
| 交易方向 | 单选 | 买入 / 卖出 / 加仓 / 减仓 | 是 |
| 数量（股） | 数字 | 100的整数倍 | 是 |
| 目标价格 | 数字 | 用户期望的买入/卖出价格，默认当前价 | 否 |
| 交易理由 | 文本 | 用户简述为什么想做这笔交易（限200字） | 否 |

如果用户选择的是已持有的股票，表单自动填充当前持仓信息（持仓数量、成本价），交易方向自动切换为"加仓"或"减仓"。

### 1.4 诊断报告的5个分析维度 + 综合结论

1. **交易概览卡片** — 交易摘要 + 当前持仓状态 + 交易后的组合变化预览（纯数据计算，不需要LLM）
2. **股票价值诊断** — 核心财务指标摘要、估值水平（PE/PB分位）、DCF参考价、近期研报观点。底部提供"查看完整分析报告"按钮（按需触发完整10模块报告）
3. **仓位与组合管理** — 交易后的仓位占比变化、行业集中度、与现有持仓的相关性、是否过度集中
4. **买入/卖出时机** — 技术面信号（均线、成交量、支撑/压力位）、近期走势分析、短期催化剂/风险事件
5. **大盘与市场环境** — 市场温度、北向资金、板块轮动、宏观风险提示
6. **综合诊断结论** — 综合前5个维度，用一段话总结这笔交易的合理性，指出最大的风险点和最值得关注的信号。不给"买/不买"的建议，而是"如果你决定做这笔交易，需要注意X、Y、Z"

### 1.5 追问对话

报告生成完毕后，底部出现对话输入框。用户可以追问，比如：
- "如果我把目标价降到XX元呢？"
- "这只股票和我持仓的XX有什么关联？"
- "最近有什么利空消息？"

追问对话的 context 包含完整的诊断报告内容 + 用户持仓 + 市场数据。追问对话历史保存到诊断记录中。

## 2. 交互与UI设计

### 2.1 入口设计

**首页**：新增入口卡片，位于巴菲特来信卡片下方。卡片文案："交易诊断 — 交易前听听第二意见"。

**持仓页**：个股展开详情中增加"诊断这笔交易"按钮，点击后跳转到 `#/diagnosis` 并自动填充该股票信息。

### 2.2 路由

| 路由 | 页面 |
|------|------|
| `#/diagnosis` | 交易输入表单 |
| `#/diagnosis/generate` | 诊断报告生成中（流式渲染） |
| `#/diagnosis/{id}` | 查看已保存的诊断记录 |
| `#/diagnosis/history` | 诊断记录列表 |

### 2.3 视觉风格

完全复用现有设计规范：
- 米白背景 `#FAF7F2`，深墨绿标题 `#2C3E2D`
- 卡片白底圆角，低饱和度涨跌色（涨 `#D97757`，跌 `#7A9B6E`）
- 宋体标题 + 黑体正文 + 等宽数字
- 信号标签复用巴菲特来信的 `signal-tag` 样式
- 诊断卡片复用 `.stock-card` 样式，左侧彩色边框表示维度

### 2.4 页面布局

**交易输入页**：居中单列，最大宽度600px。顶部返回按钮 + 标题，下方结构化表单，底部"开始诊断"按钮。

**诊断报告页**：居中单列，最大宽度720px（同巴菲特来信）。顶部交易概览数据卡片，中间5个分析维度卡片逐个流式渲染，底部综合结论 + 追问对话区域。

**诊断记录列表**：居中单列，每条记录一个卡片，显示交易方向标签 + 股票名称 + 数量 + 日期 + 摘要。

## 3. 技术架构

### 3.1 后端新增文件

| 文件 | 职责 |
|------|------|
| `app/ai/diagnosis_prompts.py` | 5个分析维度的 prompt 模板 + 综合结论 prompt + 追问对话 system prompt |
| `app/data/diagnosis_data.py` | 诊断数据聚合，复用现有数据模块 |
| `app/report/diagnosis_generator.py` | 诊断报告 async generator（流式HTML），模式同 `letter_generator.py` |
| `app/report/diagnosis_template.py` | 诊断报告 HTML/CSS 模板组件 |
| `app/models/diagnosis.py` | SQLite CRUD |

### 3.2 前端新增文件

| 文件 | 职责 |
|------|------|
| `app/static/js/diagnosis.js` | 表单输入 + 流式报告渲染 + 追问对话 |
| `app/static/css/diagnosis.css` | 诊断页面样式 |

### 3.3 API 端点

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/diagnosis/generate` | 生成诊断报告（StreamingResponse） |
| `POST` | `/api/diagnosis/chat` | 追问对话（StreamingResponse） |
| `GET` | `/api/diagnosis/history` | 诊断记录列表 |
| `GET` | `/api/diagnosis/{id}` | 诊断详情（含HTML内容和对话历史） |
| `DELETE` | `/api/diagnosis/{id}` | 删除诊断记录 |

### 3.4 数据库

```sql
CREATE TABLE IF NOT EXISTS diagnosis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    stock_name TEXT NOT NULL,
    direction TEXT NOT NULL,       -- buy/sell/add/reduce
    shares INTEGER NOT NULL,
    target_price REAL,
    reason TEXT,
    content TEXT NOT NULL,         -- 完整HTML报告
    summary TEXT,                  -- 综合诊断摘要
    holdings_snapshot TEXT,        -- 诊断时的持仓快照(JSON)
    chat_history TEXT,             -- 追问对话历史(JSON)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.5 数据聚合 (`diagnosis_data.py`)

并行获取以下数据（`asyncio.gather`）：

1. 目标股票实时行情 — `get_batch_quotes`
2. 目标股票基本面 — `get_financial_summary`, `get_valuation_history`, `get_research_reports`, `get_profit_forecast`
3. 目标股票技术面 — `get_stock_kline(symbol, 30)`, `get_stock_detail`
4. 目标股票新闻 — `get_stock_news`
5. 用户持仓行情 — `get_batch_quotes(all_holding_codes)`
6. 用户持仓 profiles — `get_stock_profiles(all_holding_codes)`
7. 大盘数据 — `get_market_overview`
8. 最新巴菲特来信 — `get_latest_letter()` 从DB读取

### 3.6 诊断报告生成 (`diagnosis_generator.py`)

```python
async def generate_diagnosis(trade_intent, holdings, letter_context) -> AsyncGenerator[str, None]:
    data = await fetch_diagnosis_data(trade_intent, holdings)
    yield diagnosis_html_head(...)

    # 卡片1: 交易概览（纯计算）
    yield diagnosis_overview_html(trade_intent, holdings, data)

    # 卡片2: 股票价值诊断（LLM）
    raw = await asyncio.to_thread(chat, value_diagnosis_prompt(...))
    value_json = _parse_json(raw)
    yield diagnosis_value_html(value_json, data)

    # 卡片3: 仓位与组合管理（LLM）
    raw = await asyncio.to_thread(chat, position_diagnosis_prompt(...))
    position_json = _parse_json(raw)
    yield diagnosis_position_html(position_json)

    # 卡片4: 交易时机（LLM + web search）
    raw = await asyncio.to_thread(chat_with_search, timing_diagnosis_prompt(...))
    timing_json = _parse_json(raw)
    yield diagnosis_timing_html(timing_json, data)

    # 卡片5: 市场环境（LLM + web search）
    raw = await asyncio.to_thread(chat_with_search, market_diagnosis_prompt(...))
    market_json = _parse_json(raw)
    yield diagnosis_market_html(market_json)

    # 综合结论（LLM，context = 前5个维度的分析结果）
    conclusion = await asyncio.to_thread(chat, conclusion_prompt(all_analysis))
    yield diagnosis_conclusion_html(conclusion)

    yield diagnosis_html_footer()
```

### 3.7 追问对话

`POST /api/diagnosis/chat` 接收 `{diagnosis_id, message, history}`。

System prompt 包含：诊断报告的纯文本摘要 + 用户持仓数据 + 市场数据。使用 `chat_with_search` 支持实时信息查询。流式输出 markdown 文本。

对话历史在前端维护，每次追问时完整发送。对话结束后（用户离开页面或手动保存），将对话历史更新到数据库的 `chat_history` 字段。

### 3.8 复用策略

| 现有模块 | 复用方式 |
|---------|---------|
| `letter_template.py` 卡片CSS | 复用 `.stock-card`, `.signal-tag`, `.market-temp` 等 |
| `letter_data.py` → `get_market_overview` | 直接调用 |
| `letter_data.py` → `get_stock_detail` | 直接调用 |
| `portfolio_data.py` → `get_batch_quotes` | 直接调用 |
| `portfolio_data.py` → `get_stock_profiles` | 直接调用 |
| `financial_data.py` → `get_financial_summary`, `get_valuation_history` | 直接调用 |
| `news_data.py` → `get_stock_news`, `get_research_reports` | 直接调用 |
| `letter_generator.py` → `_parse_json`, `_calc_portfolio_summary` | 直接复用 |
| `letter_prompts.py` → `ANALYST_SYSTEM` | 复用 analyst 人设 |
| `store.js` 持仓数据 | 前端传入 |
| `add-stock.js` 搜索逻辑 | 复用搜索组件 |

## 4. 验证方案

### 4.1 功能测试

1. **表单输入**：验证股票搜索、方向选择、数量校验（100整数倍）、已持有股票自动填充
2. **诊断生成**：验证流式渲染正常、5个维度卡片都能生成、综合结论正确引用前面的分析
3. **追问对话**：验证对话能正确引用诊断报告 context、流式输出正常
4. **历史记录**：验证保存、列表展示、详情回看、删除
5. **按需触发完整报告**：验证"查看完整分析报告"按钮能正确跳转到单股分析

### 4.2 边界情况

- 用户无持仓时发起诊断（仅分析目标股票，跳过仓位管理维度）
- 卖出数量超过持仓数量（表单校验拦截）
- 目标股票停牌（提示用户）
- LLM 返回非法 JSON（fallback 渲染基础卡片）
- 网络中断（前端错误提示 + 重试按钮）

### 4.3 端到端测试

1. 启动 dev server (`python3 run.py`)
2. 添加几只持仓股票
3. 生成一封巴菲特来信
4. 进入交易诊断，输入"买入500股宁德时代"
5. 验证诊断报告完整生成
6. 追问"如果降到200元呢"
7. 返回首页，进入诊断记录，验证回看正常

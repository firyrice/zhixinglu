# 交易诊断报告优化设计

日期：2026-05-05

## 概述

对交易诊断报告进行5项功能优化：加载进度条、复用个股分析报告作为 context、新增板块环境模块、信心指数星级、预设追问问题 hints。

## 当前架构

交易诊断是一个流式 HTML 生成管道：

```
前端 POST trade_intent + holdings
  → 后端并行获取数据（akshare + 行情）
  → 串行 LLM 调用（价值 → 仓位 → 择时 → 市场 → 结论）
  → 每个维度生成 JSON → 渲染 HTML 卡片 → yield 给前端
  → 前端逐步显示卡片
  → 流结束后启用追问聊天
```

当前问题：
- 加载时只有一个简单动画，用户不知道进展到哪一步
- 各维度 LLM 缺少完整个股分析的 context，判断深度有限
- 缺少行业/板块维度的分析
- 结论缺少量化的信心指标
- 追问聊天没有引导，用户不知道问什么

## 新流程

```
前端 POST trade_intent + holdings
  → [新] 查询/生成个股分析报告（2天缓存）
  → 并行获取诊断数据（akshare + 行情）
  → 串行 LLM 调用：
      价值诊断（含报告摘要 context）
      → 仓位诊断（含报告摘要 context）
      → 择时诊断（含报告摘要 context）
      → 市场诊断
      → [新] 板块环境（chat_with_search）
      → [改] 综合判断（JSON 输出：结论 + 信心指数 + 预设问题）
  → 前端逐步显示卡片 + 进度条更新
  → 流结束后显示 hint 标签 + 启用追问聊天
```

---

## 功能1：加载进度条

### 后端协议

在每个阶段开始前，yield 一个 HTML 注释作为进度标记：

```html
<!-- PROGRESS:loading_report -->    加载分析报告
<!-- PROGRESS:fetching_data -->     获取市场数据
<!-- PROGRESS:value -->             价值诊断
<!-- PROGRESS:position -->          仓位诊断
<!-- PROGRESS:timing -->            择时诊断
<!-- PROGRESS:market -->            市场诊断
<!-- PROGRESS:sector -->            板块环境
<!-- PROGRESS:conclusion -->        综合判断
```

标记格式固定为 `<!-- PROGRESS:{step_id} -->`，前端通过正则匹配提取。

### 前端进度组件

替换当前的简单进度条，改为步骤列表式进度指示器：

```
┌─────────────────────────────────────┐
│  交易诊断生成中                       │
│                                     │
│  ✓ 加载分析报告                      │
│  ✓ 获取市场数据                      │
│  ● 价值诊断...                      │
│  ○ 仓位诊断                         │
│  ○ 择时诊断                         │
│  ○ 市场诊断                         │
│  ○ 板块环境                         │
│  ○ 综合判断                         │
└─────────────────────────────────────┘
```

三种状态：
- `completed`：✓ 绿色对勾
- `active`：● 带旋转动画的圆点
- `pending`：○ 灰色空心圆

行为：
- 初始显示全部步骤为 pending
- 收到 PROGRESS 标记时更新对应步骤状态
- 第一张诊断卡片出现后，进度组件收起为页面顶部的细进度条（显示当前步骤文字 + 进度百分比）
- 全部完成后进度条消失

### 修改文件

- `app/report/diagnosis_generator.py`：在每个阶段前 yield progress 标记
- `app/static/js/diagnosis.js`：`renderGenerating()` 中解析 progress 标记，渲染进度组件

---

## 功能2：复用个股分析报告

### 查询逻辑

在 `diagnosis_generator.py` 的 `generate_diagnosis()` 开头新增：

1. 查询 `history` 表：
   ```sql
   SELECT id, content, created_at FROM history
   WHERE stock_code = ? AND created_at > datetime('now', '-2 days')
   ORDER BY created_at DESC LIMIT 1
   ```
2. 如果命中缓存 → 直接提取摘要
3. 如果未命中 → 调用 `generate_report()` 生成完整报告，通过 `save_report()` 保存到 history 表，再提取摘要

### 报告生成集成

- 复用 `app/report/generator.py` 中的 `generate_report(symbol)` 异步生成器
- 需要消费整个生成器收集完整 HTML（不流式输出给前端，只在后台完成）
- 保存逻辑复用 `app/models/history.py` 的 `save_report()` 函数
- 生成的报告正常出现在历史分析列表中

### 摘要提取

新增函数 `extract_report_summary(html_content) -> str`，位于 `diagnosis_generator.py`：

用正则从报告 HTML 中提取各模块的关键内容段落。目标输出约 500-800 字的结构化文本：

```
【估值分析】PE 15.2倍，低于行业均值20倍；PB 1.8倍，处于历史30%分位...
【技术面分析】短期均线多头排列，MACD金叉，5日成交量放大...
【基本面】营收增速12%，净利润率8.5%，ROE 15%...
【资金面】近5日主力净流入2.3亿，北向资金增持...
【机构观点】3家机构给出买入评级，目标价均值35元...
```

提取策略：匹配报告中各 section 的 `<div class="section">` 或 `<h2>` 标签后的前 2-3 段文字内容（strip HTML tags）。

### Prompt 注入

各维度 prompt 函数新增 `report_context: str = ""` 参数。当有报告摘要时，在 user message 末尾追加：

```
---
以下是该股票的完整分析报告摘要，供你参考：
{report_context}
```

注入到：价值诊断、仓位诊断、择时诊断（这三个维度最能从完整分析中受益）。市场诊断和板块环境不注入（它们关注的是宏观/行业层面）。

### 修改文件

- `app/report/diagnosis_generator.py`：新增报告查询/生成/摘要提取逻辑
- `app/ai/diagnosis_prompts.py`：各 prompt 函数增加 report_context 参数
- `app/models/history.py`：可能需要新增按 stock_code + 时间范围查询的函数

---

## 功能3：板块环境模块

### 数据获取

在 `app/data/diagnosis_data.py` 的 `fetch_diagnosis_data()` 中新增：

- `stock_board_industry_hist_em(symbol, period="日k", start_date, end_date)`：获取该股票所属行业板块近 20 个交易日的 K 线数据
- 需要先通过股票信息确定其所属行业板块名称

返回数据结构新增 `sector_data` 字段：
```python
{
    "industry_name": "半导体",        # 行业名称
    "industry_kline": [...],          # 近20日行业指数K线
    "industry_change_pct": -2.3,      # 近20日涨跌幅
}
```

### Prompt 设计

新增 `sector_diagnosis_prompt(stock_name, industry_name, industry_data, stock_info, trade_intent, report_context="")`：

- 使用 `chat_with_search`（需要搜索竞争对手信息）
- 输入：公司名称、行业名称、行业近期涨跌数据、公司主营业务描述
- 要求 LLM：
  1. 分析行业近期走势原因
  2. 判断行业整体估值水平
  3. 自行识别 3-5 个主要竞争对手
  4. 对比各竞争对手的核心优劣势
  5. 给出该公司在板块中的投资价值排名

输出 JSON 格式：
```json
{
  "industry_trend": "近期半导体板块受AI需求拉动上涨5.2%...",
  "industry_valuation": "板块平均PE 45倍，处于历史70%分位",
  "competitors": [
    {
      "name": "竞争对手A",
      "ticker": "000001",
      "advantage": "市占率第一，规模效应明显",
      "disadvantage": "增速放缓，估值偏高"
    }
  ],
  "target_rank": 2,
  "target_rank_total": 5,
  "rank_reason": "技术领先但规模不及龙头...",
  "sector_score": 4,
  "diagnosis": "从板块角度看，该公司处于行业第二梯队..."
}
```

### HTML 模板

新增 `diagnosis_sector_html(sector_json)` 在 `diagnosis_template.py`：

```
┌─────────────────────────────────────┐
│ 📊 板块环境                          │
├─────────────────────────────────────┤
│ 行业：半导体 | 近20日：+5.2%         │
│ 行业估值：PE 45x（历史70%分位）       │
├─────────────────────────────────────┤
│ 竞争对手对比                         │
│ ┌───────┬──────────┬──────────┐     │
│ │ 公司   │ 优势      │ 劣势     │     │
│ ├───────┼──────────┼──────────┤     │
│ │ 对手A  │ 市占率高   │ 增速慢   │     │
│ │ 对手B  │ 技术领先   │ 估值贵   │     │
│ └───────┴──────────┴──────────┘     │
├─────────────────────────────────────┤
│ 板块排名：第2/5名                    │
│ 诊断：从板块角度看...                 │
└─────────────────────────────────────┘
```

### 修改文件

- `app/data/diagnosis_data.py`：新增板块数据获取
- `app/ai/diagnosis_prompts.py`：新增 `sector_diagnosis_prompt()`
- `app/report/diagnosis_generator.py`：在市场诊断后新增板块环境生成步骤
- `app/report/diagnosis_template.py`：新增 `diagnosis_sector_html()`

---

## 功能4：信心指数

### 结论 Prompt 改造

将结论从纯文本输出改为 JSON 输出。修改 `conclusion_prompt()`：

输出格式：
```json
{
  "conclusion": "综合来看，该笔交易具备较好的安全边际...",
  "key_points": [
    "估值处于历史低位，下行空间有限",
    "技术面短期超卖，存在反弹需求",
    "但行业景气度下行，需控制仓位"
  ],
  "confidence_score": 4,
  "confidence_reason": "估值和技术面共振，但行业逆风需要关注"
}
```

`confidence_score` 规则（写入 prompt）：
- 5星：多维度强烈支持，风险可控
- 4星：大部分维度支持，少量风险点
- 3星：支持和反对因素各半，需要权衡
- 2星：多数维度不支持，风险较大
- 1星：强烈不建议，多维度风险

### HTML 模板改造

修改 `diagnosis_conclusion_html()`，接收 JSON 对象而非纯文本：

```
┌─────────────────────────────────────┐
│ 🎯 综合判断                          │
├─────────────────────────────────────┤
│                                     │
│   信心指数：★★★★☆  高信心            │
│   （估值和技术面共振，但行业逆风）     │
│                                     │
├─────────────────────────────────────┤
│ 综合来看，该笔交易具备较好的安全边际...│
│                                     │
│ • 估值处于历史低位，下行空间有限       │
│ • 技术面短期超卖，存在反弹需求        │
│ • 但行业景气度下行，需控制仓位        │
└─────────────────────────────────────┘
```

星级颜色：
- 4-5星：`#10b981`（绿色）标签"高信心"
- 3星：`#f59e0b`（橙色）标签"中等信心"
- 1-2星：`#ef4444`（红色）标签"低信心"

### 修改文件

- `app/ai/diagnosis_prompts.py`：改造 `conclusion_prompt()` 输出格式
- `app/report/diagnosis_generator.py`：解析结论 JSON
- `app/report/diagnosis_template.py`：改造 `diagnosis_conclusion_html()`

---

## 功能5：预设追问 Hints

### 生成方式

在结论 JSON 中增加 `suggested_questions` 字段：

```json
{
  "conclusion": "...",
  "confidence_score": 4,
  "confidence_reason": "...",
  "key_points": ["...", "...", "..."],
  "suggested_questions": [
    "如果大盘继续下跌，这个位置还值得加仓吗？",
    "目前的仓位比例是否需要调整？",
    "有没有更好的同行业替代标的？"
  ]
}
```

Prompt 中对 `suggested_questions` 的要求：
- 必须与本次具体交易高度相关（包含股票名称或具体数据）
- 从用户视角出发：看完分析后最可能想追问的问题
- 覆盖不同角度：风险、操作建议、替代方案

### 前端渲染

在聊天容器顶部（输入框上方）渲染 hint 标签：

```
┌─────────────────────────────────────┐
│ 💡 你可能想问：                       │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 如果大盘继续下跌，还值得加仓吗？  │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 目前的仓位比例是否需要调整？      │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 有没有更好的同行业替代标的？      │ │
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│ [输入框]                    [发送]   │
└─────────────────────────────────────┘
```

交互行为：
- 点击 hint → 立即作为用户消息发送（等同于手动输入并点击发送）
- 发送后 hints 区域消失
- hints 仅在首次进入聊天时显示，用户手动发送消息后也消失

### 数据传递

后端在流式输出结论卡片 HTML 后，额外 yield 一个隐藏的 data 标记：

```html
<!-- HINTS:["问题1","问题2","问题3"] -->
```

前端解析此标记，提取问题数组渲染为 hints。

### 修改文件

- `app/ai/diagnosis_prompts.py`：结论 prompt 增加 suggested_questions 要求
- `app/report/diagnosis_generator.py`：解析并 yield hints 标记
- `app/static/js/diagnosis.js`：解析 hints 标记，渲染可点击标签
- `app/static/css/diagnosis.css`：hints 样式

---

## 文件修改清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `app/report/diagnosis_generator.py` | 重构 | 新增报告查询/生成、摘要提取、进度标记、板块环境步骤、结论JSON解析 |
| `app/ai/diagnosis_prompts.py` | 修改 | 各prompt增加report_context、新增sector_prompt、改造conclusion_prompt |
| `app/report/diagnosis_template.py` | 修改 | 新增sector_html、改造conclusion_html（星级+结构化） |
| `app/data/diagnosis_data.py` | 修改 | 新增板块数据获取 |
| `app/models/history.py` | 修改 | 新增按stock_code+时间查询函数 |
| `app/static/js/diagnosis.js` | 重构 | 进度组件、hints解析渲染、点击交互 |
| `app/static/css/diagnosis.css` | 修改 | 进度条样式、hints样式、星级样式 |

## 风险与注意事项

1. **耗时增加**：无缓存时需先生成完整个股报告（约60-90秒），加上诊断本身（约30-40秒），总耗时可能达2分钟。进度条是关键的体验缓解措施。
2. **Token 消耗**：报告摘要注入会增加每个维度约 500-800 tokens 的输入，板块环境新增一次 LLM 调用。整体 token 消耗增加约 40%。
3. **板块数据可用性**：akshare 的行业板块接口偶尔不稳定，需要做好 fallback（板块数据获取失败时跳过板块环境模块或使用纯搜索模式）。
4. **结论 JSON 解析**：从纯文本改为 JSON 输出，需要做好 parse 失败的 fallback（降级为纯文本展示，不显示星级和 hints）。

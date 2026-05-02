# 知行录

AI 驱动的中国 A 股单股深度分析报告生成器，面向个人投资者。

输入一只股票代码或名称，自动生成一份包含 10 个维度的深度分析报告——从公司业务、商业模式、财务健康、估值分析到交易参考，用"人话"帮你看懂一只股票。

## 功能特性

报告包含 10 个分析模块，逐步流式渲染到浏览器：

| 模块 | 内容 |
|------|------|
| 这家公司在做什么 | 公司业务概览，AI 生成的通俗介绍 |
| 它怎么赚钱 | 商业模式与盈利结构分析 |
| 财务体检 | 营收、利润、毛利率、ROE 等指标趋势 + DCF 估值（可交互调参） |
| 估值坐标 | 5 种经典估值方法汇总表 + PE/PB 历史分位数 |
| 最新研报 | 券商研报摘要 + 分析师盈利预测 |
| 市场分歧 | 多空观点梳理，结合新闻与研报 |
| 股价走势分析 | 近 90 日 K 线图 + AI 走势解读 |
| 财报附录 | 最新财报公告索引 |
| 交易参考 | 基于数据的买卖参考框架 |
| 延展问题 | AI 生成的深度思考问题 |

### 估值分析

- **DCF 两阶段模型**：10 年预测期，支持浏览器内拖动滑块实时调整 WACC、增长率等参数
- **估值汇总表**：自动计算格雷厄姆数、DDM（戈登增长）、GARP、反向 DCF、格雷厄姆公式 5 种经典估值
- **历史分位**：PE(TTM) 和 PB 的 5 年历史百分位仪表盘

## 快速开始

### 环境要求

- Python >= 3.11
- 一个 OpenAI 兼容的 LLM API（OpenAI、Anthropic、DeepSeek、本地模型等均可）

### 安装

```bash
git clone https://github.com/firyrice/zhixinglu.git
cd zhixinglu
pip install -r requirements.txt
```

### 配置 API Key

复制示例配置文件并填入你的 API 信息：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 支持任何 OpenAI 兼容的 API 端点
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

**常见配置示例：**

| 服务商 | LLM_BASE_URL | LLM_MODEL |
|--------|-------------|-----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Anthropic (兼容层) | `https://api.anthropic.com/v1` | `claude-sonnet-4-6` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| 本地 Ollama | `http://localhost:11434/v1` | `qwen2.5:72b` |

> 项目通过 OpenAI SDK 调用 LLM，因此任何兼容 OpenAI API 格式的服务都可以使用。

### 启动

```bash
python3 run.py
```

打开浏览器访问 http://localhost:5001，输入股票代码或名称即可生成报告。

## 项目架构

```
zhixinglu/
├── run.py                  # 入口，启动 uvicorn
├── app/
│   ├── main.py             # FastAPI 应用，定义 API 路由
│   ├── config.py           # 环境变量配置
│   ├── ai/
│   │   ├── llm_client.py   # LLM 调用封装（OpenAI SDK）
│   │   ├── prompts.py      # 10 个分析模块的中文 prompt
│   │   ├── dcf_model.py    # DCF 两阶段估值模型
│   │   └── valuation_models.py  # 5 种经典估值方法
│   ├── data/
│   │   ├── financial_data.py    # 财务数据（利润表、现金流、分红）
│   │   ├── market_data.py       # 行情数据（K线、实时报价）
│   │   ├── valuation_data.py    # 估值历史（PE/PB）
│   │   ├── news_data.py         # 新闻、研报、公告
│   │   └── stock_search.py      # 股票搜索
│   ├── report/
│   │   ├── generator.py     # 报告生成器（10 模块编排）
│   │   ├── html_template.py # HTML/CSS 模板
│   │   └── chart_config.py  # ECharts 图表配置
│   └── static/
│       └── index.html       # 前端页面
├── PRD/                     # 产品需求文档
├── requirements.txt
└── .env.example
```

**数据流：** 用户搜索股票 → 选择 → 服务端并发获取 11 个数据源（akshare） → 10 个分析模块顺序执行，每个调用 LLM → HTML 分块流式返回浏览器渐进渲染。

## 技术栈

- **后端**：FastAPI + uvicorn
- **数据源**：[akshare](https://github.com/akfamily/akshare)（A 股行情、财务、研报等）
- **估值模型**：[valueinvest](https://github.com/wangzhe3224/valueinvest)（经典估值方法库）
- **LLM**：OpenAI SDK（兼容任意 OpenAI API 格式的服务）
- **前端**：原生 HTML/JS + [ECharts](https://echarts.apache.org/) 图表
- **无数据库**：所有数据按需实时获取

## 免责声明

本工具生成的分析报告仅供学习和参考，不构成任何投资建议。股市有风险，投资需谨慎，请结合自身情况独立判断。

## License

MIT

BUFFETT_SYSTEM = """你是沃伦·巴菲特，正在给你的合伙人写每日来信的开场白和结尾寄语。

写作风格：
- 第一人称，称呼读者为"合伙人"
- 语言亲和、幽默、有智慧感
- 善用比喻解释复杂概念
- 对市场短期波动保持淡定
- 用中文写作，保持巴菲特的思维方式
- 输出纯文本，不用markdown"""

ANALYST_SYSTEM = """你是一位专业的价值投资分析师。输出必须是合法JSON，不要包含任何其他文字。"""


def letter_opening_prompt(portfolio_summary: str, market_summary: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""写一段来信开场白（50-80字）。

组合表现：{portfolio_summary}
市场概况：{market_summary}

要求：自然引出今天的情况，巴菲特式的幽默开场。不要用"亲爱的合伙人"开头。直接输出纯文本。"""}
    ]


def letter_stocks_prompt(portfolio_summary: str, stock_details: str, market_summary: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""分析以下持仓股今日表现，输出JSON数组。

组合总览：{portfolio_summary}
市场环境：{market_summary}

各股详情：
{stock_details}

输出格式（严格JSON数组）：
[
  {{
    "name": "股票名称",
    "code": "股票代码",
    "change_pct": 1.23,
    "reason": "一句话解释今日涨跌的核心原因（20-40字）",
    "signals": ["主力流入", "放量"],
    "action": "持有",
    "action_score": 3,
    "risk": "一句话风险提示（15-25字）"
  }}
]

字段说明：
- reason：必须解释"为什么"涨跌，不要只描述涨跌幅度
- signals：从以下标签中选取1-3个最相关的：主力流入、主力流出、放量、缩量、突破MA20、跌破MA20、超买、超卖、创新高、创新低、板块联动
- action：持有/关注加仓/考虑减仓，三选一
- action_score：1-5分，1=强烈减仓，3=持有，5=强烈加仓
- risk：具体风险点，带数字

直接输出JSON数组，不要任何其他文字。"""}
    ]


def letter_news_prompt(holdings_info: str, news_data: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""从以下新闻中精选与持仓最相关的高价值信息（最多3条），输出JSON数组。

持仓：{holdings_info}

新闻：
{news_data}

输出格式（严格JSON数组）：
[
  {{
    "title": "新闻标题（精简到15-25字）",
    "impact": "利好",
    "stocks": ["关联股票名称"],
    "summary": "一句话解读对股价的影响（20-35字）"
  }}
]

字段说明：
- impact：利好/利空/中性，三选一
- stocks：受影响的持仓股名称列表
- summary：必须说清楚"对股价意味着什么"

宁缺毋滥，没有重要新闻就输出空数组 []。直接输出JSON数组。"""}
    ]


def letter_market_prompt(market_data: str, portfolio_summary: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""解读今日市场大势，输出JSON对象。

市场数据：
{market_data}

组合概况：{portfolio_summary}

输出格式（严格JSON对象）：
{{
  "sentiment_score": 65,
  "sentiment_label": "偏暖",
  "summary": "一句话总结今日市场（25-40字）",
  "north_flow": "北向资金净流入/流出描述",
  "hot_sectors": "今日领涨板块（最多3个）",
  "risk_sectors": "今日领跌板块（最多3个）"
}}

字段说明：
- sentiment_score：0-100，0=极度恐慌，50=中性，100=极度贪婪
- sentiment_label：恐慌/偏冷/中性/偏暖/贪婪，五选一
- summary：一句话，数据说话，不要空泛描述

直接输出JSON对象。"""}
    ]


def letter_closing_prompt(key_points: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""写一段结尾寄语（30-50字）。

今日要点：{key_points}

用巴菲特标志性的价值投资哲学金句收尾，简短有力。直接输出纯文本。"""}
    ]

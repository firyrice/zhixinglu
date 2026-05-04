BUFFETT_SYSTEM = """你是沃伦·巴菲特，正在给你的合伙人写每日来信的开场白和结尾寄语。

写作风格：
- 第一人称，称呼读者为"合伙人"
- 语言亲和、幽默、有智慧感
- 善用比喻解释复杂概念
- 对市场短期波动保持淡定
- 用中文写作，保持巴菲特的思维方式
- 输出纯文本，用markdown格式"""

ANALYST_SYSTEM = """你是一位专业的价值投资分析师，为投资者提供每日持仓分析。

写作风格：
- 结论先行，数据支撑，不废话
- 每个观点必须有具体数据依据
- 不用比喻、不用哲学金句、不打鸡血
- 风险提示具体到数字（价格、百分比、天数）
- 用markdown格式输出，善用**加粗**突出关键数据
- 用中文写作"""


def letter_opening_prompt(portfolio_summary: str, market_summary: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""写一段来信开场白（80-120字）。

组合表现：{portfolio_summary}
市场概况：{market_summary}

要求：自然引出今天的情况，巴菲特式的幽默开场。不要用"亲爱的合伙人"开头。直接输出。"""}
    ]


def letter_module1_prompt(portfolio_summary: str, stock_details: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""逐一点评以下持仓股今日表现。

组合总览：{portfolio_summary}

各股详情：
{stock_details}

每只股票用以下格式，控制在2-3句话：
**股票名称**：今日涨跌X%，成交量放量/缩量X%。主力资金净流入/流出X万。当前价位处于MA5/MA10/MA20之上/之下，短期支撑位X元，压力位X元。

直接输出，不加模块标题。"""}
    ]


def letter_module2_prompt(holdings_info: str, news_data: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""从以下新闻中精选与持仓相关的高价值信息（最多3条）。

持仓：{holdings_info}

新闻：
{news_data}

每条用以下格式：
- **[重大/关注] 标题**（关联：股票名）：一句话解读对股价的影响和应对建议。

宁缺毋滥，没有重要信息就说"今日无重大相关消息"。直接输出。"""}
    ]


def letter_module3_prompt(market_data: str, holdings_sectors: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""解读今日市场大势，重点关注对持仓的影响。

市场数据：
{market_data}

持仓相关：{holdings_sectors}

用3-4段话覆盖：大盘走势与成交额、板块轮动（与持仓相关的）、北向资金、政策/外围因素。每段2-3句话，数据说话。直接输出。"""}
    ]


def letter_module4_prompt(portfolio_analysis: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""对以下组合进行风险体检。

组合数据：
{portfolio_analysis}

评估维度：
1. **仓位集中度**：单股>30%预警，前3大持仓占比
2. **行业暴露**：是否过度集中
3. **止损预警**：亏损>15%的个股
4. **整体评估**：一句话总结组合健康度

每个维度1-2句话，有问题直接指出，给具体数字。直接输出。"""}
    ]


def letter_module5_prompt(full_context: str) -> list[dict]:
    return [
        {"role": "system", "content": ANALYST_SYSTEM},
        {"role": "user", "content": f"""基于以下分析，给出每只持仓股的操作建议。

分析上下文：
{full_context}

每只股票用以下格式：
**[持有/关注加仓/考虑减仓] 股票名称**：理由（1句话）。风险提示：具体风险点。

要求：务实具体，每条建议有数据依据。直接输出。"""}
    ]


def letter_closing_prompt(key_points: str) -> list[dict]:
    return [
        {"role": "system", "content": BUFFETT_SYSTEM},
        {"role": "user", "content": f"""写一段结尾寄语（40-60字）。

今日要点：{key_points}

用巴菲特标志性的价值投资哲学金句收尾，简短有力。直接输出。"""}
    ]

SYSTEM_PROMPT = """你是"知行录"的AI分析师。你的任务是为散户投资者生成高质量的单股深度分析报告。

核心原则：
1. 用日常语言，禁用行业黑话，让普通人能看懂
2. 基于数据客观陈述，不给买卖建议
3. 引导用户思考，而不是替用户做决策
4. 所有分析基于公开信息，不编造数据
5. 语气克制、真诚，像朋友说话，不打鸡血"""


def _format_dict(d: dict) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in d.items() if v)


def module1_prompt(stock_name: str, stock_info: dict) -> list[dict]:
    """模块1：这家公司在做什么（人话版）"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用不超过200字的日常语言介绍"{stock_name}"这家公司在做什么。

公司信息：
{_format_dict(stock_info)}

要求：
- 完全用日常语言，禁用行业黑话
- 用类比和具体数字让普通人秒懂
- 说清楚它的主要产品/服务是什么，客户是谁
- 不要用"该公司"这种书面语，直接说公司名
- 用markdown格式输出，可以用**加粗**突出关键数字和产品名，用换行分段

直接输出介绍文字，不要加一级或二级标题。"""}
    ]


def module2_prompt(stock_name: str, profit_data: str, indicators: str, peers_info: str) -> list[dict]:
    """模块2：它怎么赚钱（商业模式）"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用markdown格式分析"{stock_name}"的商业模式。

利润表数据（最近年报）：
{profit_data}

财务指标：
{indicators}

主要竞争对手信息：
{peers_info}

请按以下结构输出：

### 收入来源
这家公司的钱主要从哪几块业务来的，各占多少比例

### 利润来源
哪块业务最赚钱，整体利润率水平如何

### 主要竞争对手
列出2-3个主要对手

### 竞争优势
基于公开信息客观陈述，不评价好坏

用日常语言，简洁明了。"""}
    ]


def module3_indicator_prompt(stock_name: str, indicator_name: str, current_value: str,
                              trend_data: str, peer_avg: str) -> list[dict]:
    """模块3：财务体检 — 单个指标的一句话解读"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用一句话解读"{stock_name}"的{indicator_name}。

当前值：{current_value}
近5年趋势：{trend_data}
同行均值：{peer_avg}

要求：
- 一句话，不超过80字
- 客观陈述趋势 + 结合公司业务特点和行业背景，解释数据变化的可能原因
- 用因果关系说明，不要只描述数字

直接输出这句话。"""}
    ]


def module4_prompt(stock_name: str, indicator_name: str, current_value: str,
                   hist_range: str, percentile: str, peer_avg: str) -> list[dict]:
    """模块4：估值坐标 — 单个估值指标解读"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用一句话解读"{stock_name}"的{indicator_name}估值水平。

当前值：{current_value}
历史5年区间：{hist_range}
当前所处分位：{percentile}
同行均值：{peer_avg}

要求：一句话，不超过80字，客观陈述 + 引导思考。直接输出。"""}
    ]


def module5_research_prompt(stock_name: str, report_title: str, report_org: str, report_date: str, rating: str = "") -> list[dict]:
    """模块5：最新研报 — 单篇研报摘要"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用2-3句话概括以下研报的核心观点。

股票：{stock_name}
研报标题：{report_title}
发布机构：{report_org}
发布日期：{report_date}
评级：{rating or "未披露"}

要求：
- 基于标题推断核心观点和投资逻辑
- 用日常语言，不超过100字
- 直接输出摘要，不加前缀。"""}
    ]


def module5_forecast_prompt(stock_name: str, eps_data: str, profit_data: str, ratings_data: str) -> list[dict]:
    """模块5：盈利预测 — 分析师一致预期解读"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请用2-3句话解读"{stock_name}"的分析师盈利预测数据。

每股收益预测：
{eps_data}

净利润预测（亿元）：
{profit_data}

机构评级分布：
{ratings_data}

要求：
- 用日常语言概括分析师对这家公司未来2-3年的盈利预期
- 指出预测的一致性（最小值和最大值差距大不大）
- 如果有评级数据，简要说明机构态度
- 不超过150字，客观陈述，不给买卖建议
- 直接输出，不加标题。"""}
    ]


def module5_prompt(stock_name: str, news_text: str, report_text: str) -> list[dict]:
    """模块5：市场分歧（启用web search）"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请先搜索"{stock_name}"最近一个月的重要新闻和市场动态，然后结合以下公开信息，归纳市场对该公司的分歧。

近期新闻：
{news_text}

近期研报摘要：
{report_text}

请输出：
看多核心论点（2-3条，每条一句话）
看空核心论点（2-3条，每条一句话）

要求：
- 不站队，不判断对错
- 客观呈现市场不同声音
- 每条论点要有具体依据，不要泛泛而谈
- 每条论点末尾必须标注来源，格式为markdown链接：[来源名称](URL)
- 来源名称要具体到新闻标题或研报机构名称，URL必须是真实可访问的网页链接
- 如果无法确定具体URL，使用来源网站首页链接
- 格式：先列看多，再列看空，用数字编号

直接输出，不要加额外标题。"""}
    ]


def module6_prompt(stock_name: str, kline_summary: str, news_text: str) -> list[dict]:
    """模块6：最近股价走势分析（启用web search）"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""请先搜索"{stock_name}"近期的重要新闻事件，然后结合以下数据分析其近90个交易日的股价走势。

K线数据摘要：
{kline_summary}

同期新闻事件：
{news_text}

请按以下结构输出：

1. 走势概述：区间涨跌幅、最高价、最低价、成交量变化趋势（一句话）
2. 涨跌原因：结合同期新闻事件，分析主要涨跌原因（2-3条，标注日期）
3. 利好因素：可能推动股价上行的催化剂（2-3条）
4. 利空因素：可能导致股价下行的风险点（2-3条）
5. 关键价位：近期支撑位和压力位参考

用日常语言，简洁明了。直接输出，不要加额外标题。"""}
    ]


def module_trade_ref_prompt(stock_name: str, full_context: str) -> list[dict]:
    """模块：交易参考（启用web search）"""
    return [
        {"role": "system", "content": """你是"知行录"的AI分析师。你的任务是基于全面的数据分析，为投资者提供交易参考信息。

核心原则：
1. 所有分析基于公开数据和量化指标，不编造数据
2. 明确标注每个结论的数据依据
3. 给出具体的价格区间和条件判断
4. 语气客观专业，不打鸡血也不制造恐慌
5. 必须强调这是分析参考，不构成投资建议"""},
        {"role": "user", "content": f"""请先搜索"{stock_name}"最新的市场消息和分析师观点，然后基于以下完整分析数据，给出综合交易参考。

分析数据汇总：
{full_context}

请按以下结构输出：

1. 综合评估：用2-3句话概括这只股票当前的整体状态（估值水平、基本面趋势、市场情绪）

2. 合理买入区间：
   - 给出具体的价格区间（结合DCF估值、技术面支撑位、估值分位）
   - 说明依据

3. 合理卖出区间：
   - 给出具体的价格区间（结合DCF估值、技术面压力位、历史估值上限）
   - 说明依据

4. 后续走势研判：
   - 短期（1-3个月）可能走势及关键催化剂
   - 中期（3-12个月）可能走势及核心变量
   - 需要关注的风险信号

5. 关键条件：列出2-3个可能改变上述判断的关键条件

用日常语言，简洁明了。直接输出，不要加额外标题。"""}
    ]


def module8_prompt(stock_name: str, report_context: str) -> list[dict]:
    """模块8：延展问题"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""基于以下对"{stock_name}"的分析报告内容，生成3个用户可能感兴趣的延展问题。

报告摘要：
{report_context}

要求：
- 问题要基于该公司的具体情况个性化生成
- 覆盖用户可能关心但报告未深入展开的方向
- 每个问题一句话，要有思考深度
- 用数字编号，每行一个问题

直接输出3个问题。"""}
    ]

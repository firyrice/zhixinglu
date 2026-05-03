import openai
import json
import re
import logging
from app.config import VLM_BASE_URL, VLM_API_KEY, VLM_MODEL

logger = logging.getLogger(__name__)

_vlm_client: openai.OpenAI | None = None

PARSE_PROMPT = """你是一个股票持仓截图识别助手。请仔细分析这张券商App的持仓截图，提取所有股票、基金、港股的持仓信息。

对于每一只股票/基金，请提取以下字段：
1. name: 股票/基金名称（如"贵州茅台"、"港股互联网ETF"、"小米集团"）
2. shares: 持仓数量（股/份），纯数字
3. market_value: 持仓市值（元），纯数字
4. pnl: 持仓盈亏金额（元），盈利为正数，亏损为负数

请严格以 JSON 数组格式返回，不要包含任何其他文字、解释或 markdown 标记：
[{"name":"贵州茅台","shares":800,"market_value":74414.34,"pnl":3940.00}, ...]

注意事项：
- 包含截图中所有板块的持仓：普通股票、场内基金、港股通等
- 数量和金额只保留数字，不要带单位符号
- 亏损的盈亏金额用负数表示
- 港股通的金额已经是人民币计价，直接提取即可
- 如果某个字段在截图中无法识别，设为 null
- 不要遗漏任何一只股票或基金"""


def _get_vlm_client() -> openai.OpenAI:
    global _vlm_client
    if _vlm_client is None:
        _vlm_client = openai.OpenAI(base_url=VLM_BASE_URL, api_key=VLM_API_KEY)
    return _vlm_client


def parse_portfolio_screenshot(image_base64: str, mime_type: str = "image/png") -> list[dict]:
    """调用 VLM 解析持仓截图，返回识别到的持仓列表。"""
    client = _get_vlm_client()
    data_url = f"data:{mime_type};base64,{image_base64}"

    resp = client.chat.completions.create(
        model=VLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PARSE_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.1,
    )

    raw = resp.choices[0].message.content or ""
    return _extract_json(raw)


def _extract_json(text: str) -> list[dict]:
    """从 VLM 响应中提取 JSON 数组。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse VLM response: %s", text[:500])
    return []

from datetime import datetime

LETTER_CSS = '''
<style>
.letter-container { max-width:720px; margin:0 auto; padding:32px 24px; }
.letter-header { text-align:center; margin-bottom:28px; }
.letter-header .label { font-size:12px; color:var(--accent-gold, #C9A961); letter-spacing:3px; margin-bottom:8px; }
.letter-header h1 { font-size:24px; color:var(--accent-green, #2C3E2D); font-family:var(--font-serif, 'Noto Serif SC', serif); }
.letter-header .divider { width:40px; height:2px; background:var(--accent-gold, #C9A961); margin:12px auto; }
.letter-date { font-size:13px; color:var(--text-secondary, #6B6B6B); margin-top:8px; }
.opening { font-family:var(--font-serif, 'Noto Serif SC', serif); font-size:15px; font-style:italic; padding:0 16px; margin-bottom:28px; color:var(--text-primary, #2A2A2A); line-height:1.8; }

.data-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:24px; }
.data-card { background:#fff; border-radius:8px; padding:12px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.data-card .label { font-size:11px; color:var(--text-secondary, #6B6B6B); }
.data-card .value { font-size:18px; font-weight:bold; font-family:var(--font-mono, 'IBM Plex Mono', monospace); }
.data-card .value.up { color:var(--up-color, #D97757); }
.data-card .value.down { color:var(--down-color, #7A9B6E); }

.section-title { display:flex; align-items:center; gap:8px; margin:28px 0 16px; }
.section-title .bar { width:4px; height:20px; background:var(--accent-gold, #C9A961); border-radius:2px; }
.section-title h2 { font-size:16px; font-family:var(--font-serif, 'Noto Serif SC', serif); color:var(--accent-green, #2C3E2D); font-weight:bold; margin:0; }

.stock-card { background:#fff; border-radius:10px; padding:16px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.05); border-left:4px solid var(--border, #e0d8cc); }
.stock-card.up { border-left-color:var(--up-color, #D97757); }
.stock-card.down { border-left-color:var(--down-color, #7A9B6E); }
.stock-card-header { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px; }
.stock-card-name { font-size:15px; font-weight:bold; color:var(--accent-green, #2C3E2D); }
.stock-card-change { font-size:18px; font-weight:bold; font-family:var(--font-mono, 'IBM Plex Mono', monospace); }
.stock-card-change.up { color:var(--up-color, #D97757); }
.stock-card-change.down { color:var(--down-color, #7A9B6E); }
.stock-card-reason { font-size:14px; color:var(--text-primary, #2A2A2A); line-height:1.6; margin-bottom:8px; }
.stock-card-signals { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
.signal-tag { font-size:11px; padding:2px 8px; border-radius:10px; background:#f0ebe3; color:var(--text-secondary, #6B6B6B); }
.signal-tag.positive { background:#e8f5e3; color:#4a7c3f; }
.signal-tag.negative { background:#fde8e4; color:#c0513f; }
.stock-card-footer { display:flex; align-items:center; justify-content:space-between; }
.action-badge { font-size:12px; font-weight:bold; padding:3px 10px; border-radius:4px; }
.action-badge.hold { background:#f0ebe3; color:#8b7355; }
.action-badge.buy { background:#e8f5e3; color:#4a7c3f; }
.action-badge.sell { background:#fde8e4; color:#c0513f; }
.confidence-bar { display:flex; gap:3px; align-items:center; }
.confidence-dot { width:8px; height:8px; border-radius:50%; background:#e0d8cc; }
.confidence-dot.filled { background:var(--accent-gold, #C9A961); }
.stock-card-risk { font-size:12px; color:var(--text-secondary, #6B6B6B); margin-top:6px; }

.news-item { display:flex; gap:10px; align-items:flex-start; padding:12px 0; border-bottom:1px solid #f0ebe3; }
.news-item:last-child { border-bottom:none; }
.news-impact { font-size:11px; font-weight:bold; padding:3px 8px; border-radius:4px; white-space:nowrap; flex-shrink:0; margin-top:2px; }
.news-impact.positive { background:#e8f5e3; color:#4a7c3f; }
.news-impact.negative { background:#fde8e4; color:#c0513f; }
.news-impact.neutral { background:#f0ebe3; color:#8b7355; }
.news-body { flex:1; min-width:0; }
.news-title { font-size:14px; font-weight:bold; color:var(--text-primary, #2A2A2A); margin-bottom:4px; }
.news-summary { font-size:13px; color:var(--text-secondary, #6B6B6B); line-height:1.5; }
.news-stocks { display:flex; gap:4px; margin-top:6px; flex-wrap:wrap; }
.news-stock-tag { font-size:11px; padding:1px 6px; border-radius:3px; background:#f5f0e8; color:var(--accent-green, #2C3E2D); }
.news-empty { text-align:center; padding:16px; color:var(--text-secondary, #6B6B6B); font-size:14px; }

.market-temp { background:#fff; border-radius:10px; padding:16px; box-shadow:0 1px 4px rgba(0,0,0,0.05); }
.temp-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.temp-score { font-size:28px; font-weight:bold; font-family:var(--font-mono, 'IBM Plex Mono', monospace); color:var(--accent-green, #2C3E2D); }
.temp-label { font-size:13px; padding:3px 10px; border-radius:10px; }
.temp-label.fear { background:#fde8e4; color:#c0513f; }
.temp-label.cool { background:#e3eef5; color:#3f6a8b; }
.temp-label.neutral { background:#f0ebe3; color:#8b7355; }
.temp-label.warm { background:#fdf3e4; color:#b8860b; }
.temp-label.greed { background:#fde8e4; color:#c0513f; }
.temp-bar { height:6px; background:#f0ebe3; border-radius:3px; overflow:hidden; margin-bottom:12px; }
.temp-bar-fill { height:100%; border-radius:3px; transition:width 0.5s ease; }
.temp-summary { font-size:14px; color:var(--text-primary, #2A2A2A); line-height:1.6; margin-bottom:12px; }
.temp-details { display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:13px; }
.temp-detail-item { display:flex; justify-content:space-between; padding:6px 10px; background:#faf7f2; border-radius:6px; }
.temp-detail-label { color:var(--text-secondary, #6B6B6B); }
.temp-detail-value { font-weight:bold; color:var(--text-primary, #2A2A2A); }

.closing { border-top:1px solid var(--border, #e0d8cc); padding-top:24px; margin-top:32px; }
.closing .words { font-family:var(--font-serif, 'Noto Serif SC', serif); font-size:15px; font-style:italic; line-height:1.8; padding:0 16px; }
.closing .signature { text-align:right; color:var(--text-secondary, #6B6B6B); font-size:14px; margin-top:16px; font-family:var(--font-serif, 'Noto Serif SC', serif); }
.disclaimer { margin-top:24px; padding:12px; background:var(--bg-secondary, #f8f5f0); border-radius:6px; font-size:12px; color:#999; text-align:center; }

@media (max-width:768px) {
  .letter-container { padding:20px 16px; }
  .letter-header h1 { font-size:20px; }
  .opening { font-size:14px; padding:0; }
  .data-cards { grid-template-columns:repeat(2,1fr); gap:8px; }
  .data-card { padding:10px; }
  .data-card .label { font-size:10px; }
  .data-card .value { font-size:16px; }
  .section-title h2 { font-size:15px; }
  .stock-card { padding:14px; }
  .stock-card-change { font-size:16px; }
  .temp-details { grid-template-columns:1fr; }
  .closing .words { font-size:14px; padding:0; }
}
</style>
'''

POSITIVE_SIGNALS = {"主力流入", "放量", "突破MA20", "创新高", "板块联动", "超卖"}
NEGATIVE_SIGNALS = {"主力流出", "缩量", "跌破MA20", "创新低", "超买"}


def letter_html_head(date_str: str = "") -> str:
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")
    return f'''{LETTER_CSS}
<div class="letter-container">
  <div class="letter-header">
    <div class="label">BUFFETT'S LETTER</div>
    <h1>致我的合伙人</h1>
    <div class="divider"></div>
    <div class="letter-date">{date_str} · 收盘总结</div>
  </div>
'''


def letter_opening_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="opening">{escaped}</div>\n'


def letter_data_cards_html(daily_pnl: float, daily_pct: float, total_asset: float,
                           total_pnl_pct: float, vs_hs300: float) -> str:
    pnl_cls = "up" if daily_pnl >= 0 else "down"
    pnl_sign = "+" if daily_pnl >= 0 else ""
    total_cls = "up" if total_pnl_pct >= 0 else "down"
    total_sign = "+" if total_pnl_pct >= 0 else ""
    vs_cls = "up" if vs_hs300 >= 0 else "down"
    vs_sign = "+" if vs_hs300 >= 0 else ""
    return f'''<div class="data-cards">
  <div class="data-card"><div class="label">今日盈亏</div><div class="value {pnl_cls}">{pnl_sign}{daily_pnl:,.0f}</div><div class="label" style="color:var(--{pnl_cls}-color)">{pnl_sign}{daily_pct:.2f}%</div></div>
  <div class="data-card"><div class="label">总资产</div><div class="value">{total_asset:,.0f}</div></div>
  <div class="data-card"><div class="label">持仓盈亏</div><div class="value {total_cls}">{total_sign}{total_pnl_pct:.2f}%</div></div>
  <div class="data-card"><div class="label">vs 沪深300</div><div class="value {vs_cls}">{vs_sign}{vs_hs300:.1f}%</div></div>
</div>'''


def letter_section_title(title: str) -> str:
    return f'<div class="section-title"><div class="bar"></div><h2>{title}</h2></div>\n'



def _signal_class(signal: str) -> str:
    if signal in POSITIVE_SIGNALS:
        return "positive"
    if signal in NEGATIVE_SIGNALS:
        return "negative"
    return ""


def _action_class(action: str) -> str:
    if "加仓" in action:
        return "buy"
    if "减仓" in action:
        return "sell"
    return "hold"


def letter_stock_card(stock: dict) -> str:
    change = stock.get("change_pct", 0)
    cls = "up" if change >= 0 else "down"
    sign = "+" if change >= 0 else ""
    name = stock.get("name", "")
    code = stock.get("code", "")
    reason = stock.get("reason", "")
    signals = stock.get("signals", [])
    action = stock.get("action", "持有")
    score = stock.get("action_score", 3)
    risk = stock.get("risk", "")

    signals_html = "".join(
        f'<span class="signal-tag {_signal_class(s)}">{s}</span>' for s in signals
    )
    dots = "".join(
        f'<span class="confidence-dot {"filled" if i < score else ""}"></span>'
        for i in range(5)
    )
    action_cls = _action_class(action)
    risk_html = f'<div class="stock-card-risk">{risk}</div>' if risk else ""

    return f'''<div class="stock-card {cls}">
  <div class="stock-card-header">
    <span class="stock-card-name">{name} <span style="font-weight:normal;font-size:12px;color:var(--text-secondary)">{code}</span></span>
    <span class="stock-card-change {cls}">{sign}{change:.2f}%</span>
  </div>
  <div class="stock-card-reason">{reason}</div>
  <div class="stock-card-signals">{signals_html}</div>
  <div class="stock-card-footer">
    <span class="action-badge {action_cls}">{action}</span>
    <div class="confidence-bar">{dots}</div>
  </div>
  {risk_html}
</div>'''


def letter_stocks_html(stocks: list[dict]) -> str:
    cards = "\n".join(letter_stock_card(s) for s in stocks)
    return f'{letter_section_title("个股涨跌解读")}\n{cards}\n'



def _impact_class(impact: str) -> str:
    if impact == "利好":
        return "positive"
    if impact == "利空":
        return "negative"
    return "neutral"


def _impact_label(impact: str) -> str:
    if impact == "利好":
        return "利好"
    if impact == "利空":
        return "利空"
    return "中性"


def letter_news_html(news_items: list[dict]) -> str:
    html = letter_section_title("今日要闻")
    if not news_items:
        return html + '<div class="news-empty">今日无重大相关消息</div>\n'
    items = []
    for item in news_items[:3]:
        impact = item.get("impact", "中性")
        impact_cls = _impact_class(impact)
        title = item.get("title", "")
        summary = item.get("summary", "")
        stocks = item.get("stocks", [])
        stock_tags = "".join(f'<span class="news-stock-tag">{s}</span>' for s in stocks)
        items.append(f'''<div class="news-item">
  <span class="news-impact {impact_cls}">{_impact_label(impact)}</span>
  <div class="news-body">
    <div class="news-title">{title}</div>
    <div class="news-summary">{summary}</div>
    <div class="news-stocks">{stock_tags}</div>
  </div>
</div>''')
    return html + "\n".join(items) + "\n"


def _sentiment_bar_color(score: int) -> str:
    if score < 30:
        return "#c0513f"
    if score < 45:
        return "#3f6a8b"
    if score < 55:
        return "#8b7355"
    if score < 70:
        return "#b8860b"
    return "#c0513f"


def _sentiment_label_cls(label: str) -> str:
    mapping = {"恐慌": "fear", "偏冷": "cool", "中性": "neutral", "偏暖": "warm", "贪婪": "greed"}
    return mapping.get(label, "neutral")


def letter_market_html(market: dict) -> str:
    score = market.get("sentiment_score", 50)
    label = market.get("sentiment_label", "中性")
    summary = market.get("summary", "")
    north = market.get("north_flow", "")
    hot = market.get("hot_sectors", "")
    risk = market.get("risk_sectors", "")
    bar_color = _sentiment_bar_color(score)
    label_cls = _sentiment_label_cls(label)

    return f'''{letter_section_title("市场温度计")}
<div class="market-temp">
  <div class="temp-header">
    <span class="temp-score">{score}</span>
    <span class="temp-label {label_cls}">{label}</span>
  </div>
  <div class="temp-bar"><div class="temp-bar-fill" style="width:{score}%;background:{bar_color};"></div></div>
  <div class="temp-summary">{summary}</div>
  <div class="temp-details">
    <div class="temp-detail-item"><span class="temp-detail-label">北向资金</span><span class="temp-detail-value">{north}</span></div>
    <div class="temp-detail-item"><span class="temp-detail-label">领涨板块</span><span class="temp-detail-value">{hot}</span></div>
    <div class="temp-detail-item"><span class="temp-detail-label">领跌板块</span><span class="temp-detail-value">{risk}</span></div>
  </div>
</div>
'''


def letter_closing_html(text: str) -> str:
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<div class="closing">
  <div class="words">{escaped}</div>
  <div class="signature">— 你的投资伙伴，沃伦</div>
</div>
<div class="disclaimer">以上内容由AI生成，仅供参考，不构成投资建议。投资有风险，决策需谨慎。</div>
'''


def letter_html_footer() -> str:
    return '</div>'

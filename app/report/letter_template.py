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
.module-title { display:flex; align-items:center; gap:8px; margin-bottom:16px; margin-top:32px; }
.module-title .bar { width:4px; height:20px; background:var(--accent-gold, #C9A961); border-radius:2px; }
.module-title h2 { font-size:16px; font-family:var(--font-serif, 'Noto Serif SC', serif); color:var(--accent-green, #2C3E2D); font-weight:bold; margin:0; }
.module-sep { text-align:center; margin:24px 0; color:var(--border, #e0d8cc); letter-spacing:8px; }
.data-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:16px; }
.data-card { background:#fff; border-radius:8px; padding:12px; text-align:center; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
.data-card .label { font-size:11px; color:var(--text-secondary, #6B6B6B); }
.data-card .value { font-size:18px; font-weight:bold; font-family:var(--font-mono, 'IBM Plex Mono', monospace); }
.data-card .value.up { color:var(--up-color, #D97757); }
.data-card .value.down { color:var(--down-color, #7A9B6E); }
.letter-md { font-size:15px; line-height:1.8; color:var(--text-primary, #2A2A2A); }
.letter-md p { margin-bottom:12px; }
.letter-md strong { color:var(--accent-green, #2C3E2D); }
.letter-md ul, .letter-md ol { padding-left:20px; margin-bottom:12px; }
.letter-md li { margin-bottom:6px; }
.letter-md h3 { font-size:15px; font-weight:bold; color:var(--accent-green, #2C3E2D); margin:16px 0 8px; }
.letter-md h4 { font-size:14px; font-weight:bold; color:var(--text-primary, #2A2A2A); margin:12px 0 6px; }
.letter-md blockquote { border-left:3px solid var(--accent-gold, #C9A961); padding-left:12px; color:var(--text-secondary, #6B6B6B); margin:12px 0; font-style:italic; }
.closing { border-top:1px solid var(--border, #e0d8cc); padding-top:24px; margin-top:32px; }
.closing .words { font-family:var(--font-serif, 'Noto Serif SC', serif); font-size:15px; font-style:italic; line-height:1.8; padding:0 16px; }
.closing .signature { text-align:right; color:var(--text-secondary, #6B6B6B); font-size:14px; margin-top:16px; font-family:var(--font-serif, 'Noto Serif SC', serif); }
.disclaimer { margin-top:24px; padding:12px; background:var(--bg-secondary, #f8f5f0); border-radius:6px; font-size:12px; color:#999; text-align:center; }
@media (max-width:768px) {
  .letter-container { padding:20px 16px; }
  .letter-header h1 { font-size:20px; }
  .opening { font-size:14px; padding:0; }
  .module-title h2 { font-size:15px; }
  .module-title .bar { width:3px; height:16px; }
  .data-cards { grid-template-columns:repeat(2,1fr); gap:8px; }
  .data-card { padding:10px; }
  .data-card .label { font-size:10px; }
  .data-card .value { font-size:16px; }
  .letter-md { font-size:14px; }
  .closing .words { font-size:14px; padding:0; }
}
</style>
'''


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


def letter_module_html(number: int, title: str, content: str) -> str:
    return f'''<div class="module-title"><div class="bar"></div><h2>{title}</h2></div>
{content}
<div class="module-sep">· · ·</div>
'''


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

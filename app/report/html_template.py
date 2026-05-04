def report_html_head(stock_name: str, stock_code: str) -> str:
    """报告HTML头部，包含完整CSS和ECharts CDN。"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_name}({stock_code}) - 深度分析 | 知行录</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;700&family=Noto+Sans+SC:wght@300;400;500;700&family=Source+Serif+4:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {{
  --bg: #FAF7F2;
  --text-primary: #2A2A2A;
  --text-secondary: #6B6B6B;
  --accent-green: #2C3E2D;
  --accent-blue: #2A3B4D;
  --accent-gold: #C9A961;
  --accent-orange: #E8A87C;
  --up-color: #D97757;
  --down-color: #7A9B6E;
  --border: #E5E0D8;
  --card-bg: #FFFFFF;
  --font-serif: 'Noto Serif SC', 'Source Serif 4', serif;
  --font-sans: 'Noto Sans SC', -apple-system, sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  background: var(--bg);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
}}

.report-container {{
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 24px 80px;
}}

.report-header {{
  text-align: center;
  padding: 60px 0 40px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 48px;
  position: relative;
}}

.download-btn {{
  position: absolute;
  top: 20px;
  right: 0;
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--card-bg);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s, border-color 0.2s, box-shadow 0.2s;
}}

.download-btn.visible {{
  opacity: 1;
  pointer-events: auto;
}}

.download-btn:hover {{
  border-color: var(--accent-gold);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}}

.download-btn svg {{
  width: 18px;
  height: 18px;
  stroke: var(--text-secondary);
  transition: stroke 0.2s;
}}

.download-btn:hover svg {{
  stroke: var(--accent-gold);
}}

.report-header h1 {{
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: 700;
  color: var(--accent-green);
  margin-bottom: 8px;
}}

.report-header .stock-code {{
  font-family: var(--font-mono);
  font-size: 14px;
  color: var(--text-secondary);
  letter-spacing: 1px;
}}

.report-header .report-date {{
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 12px;
}}

.module {{
  margin-bottom: 48px;
  padding-bottom: 40px;
  border-bottom: 1px solid var(--border);
  animation: fadeIn 0.5s ease-in;
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(12px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.module-number {{
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-gold);
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 8px;
}}

.module h2 {{
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  color: var(--accent-green);
  margin-bottom: 20px;
}}

.module p, .module li {{
  color: var(--text-primary);
  line-height: 1.8;
  margin-bottom: 12px;
}}

.module .insight {{
  background: var(--card-bg);
  border-left: 3px solid var(--accent-gold);
  padding: 16px 20px;
  margin: 16px 0;
  border-radius: 0 8px 8px 0;
  font-size: 15px;
  color: var(--text-secondary);
}}

.module .data-label {{
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-secondary);
}}

.module .data-value {{
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 500;
  color: var(--accent-green);
}}

.module .up {{ color: var(--up-color); }}
.module .down {{ color: var(--down-color); }}

.indicator-card {{
  background: var(--card-bg);
  border-radius: 12px;
  padding: 20px;
  margin: 12px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}

.indicator-card .indicator-header {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}}

.indicator-card .indicator-name {{
  font-weight: 500;
  font-size: 15px;
}}

.disclaimer {{
  background: #F5F0E8;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 16px;
  line-height: 1.6;
}}

.trading-disclaimer {{
  background: #FFF3E0;
  border: 1px solid #FFB74D;
  border-radius: 8px;
  padding: 14px 18px;
  font-size: 14px;
  color: #E65100;
  margin-top: 20px;
  line-height: 1.6;
  font-weight: 500;
}}

.dcf-controls {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  margin: 16px 0;
}}

.dcf-control-row {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 10px 0;
}}

.dcf-control-row label {{
  flex: 0 0 200px;
  font-size: 14px;
  color: var(--text-secondary);
}}

.dcf-control-row input[type="range"] {{
  flex: 1;
  accent-color: var(--accent-green);
  height: 6px;
}}

.dcf-control-row span {{
  flex: 0 0 50px;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 500;
  color: var(--accent-green);
  text-align: right;
}}

@media (max-width: 600px) {{
  .dcf-control-row {{
    flex-wrap: wrap;
  }}
  .dcf-control-row label {{
    flex: 0 0 100%;
    margin-bottom: 4px;
  }}
}}

.bull-bear {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin: 16px 0;
}}

@media (max-width: 600px) {{
  .bull-bear {{ grid-template-columns: 1fr; }}
}}

.bull-section {{ border-left: 3px solid var(--up-color); padding-left: 16px; }}
.bear-section {{ border-left: 3px solid var(--down-color); padding-left: 16px; }}

.bull-section h3, .bear-section h3 {{
  font-family: var(--font-serif);
  font-size: 16px;
  margin-bottom: 12px;
}}

.questions-list {{
  list-style: none;
  padding: 0;
}}

.questions-list li {{
  background: var(--card-bg);
  border-radius: 10px;
  padding: 16px 20px;
  margin: 10px 0;
  cursor: pointer;
  transition: box-shadow 0.2s;
  font-size: 15px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}}

.questions-list li:hover {{
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}}

.report-footer {{
  text-align: center;
  padding: 40px 0;
  border-top: 1px solid var(--border);
  margin-top: 20px;
}}

.report-footer .disclaimer-main {{
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 20px;
}}

.report-footer .brand {{
  font-family: var(--font-serif);
  font-size: 13px;
  color: var(--border);
  margin-top: 24px;
}}

.fin-table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}}

.fin-table th {{
  background: var(--accent-green);
  color: #fff;
  padding: 10px 14px;
  text-align: left;
  font-weight: 500;
}}

.fin-table td {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}}

.fin-table tr:hover td {{
  background: #F5F0E8;
}}

.fin-table a {{
  color: var(--accent-gold);
  text-decoration: none;
}}

.fin-table a:hover {{
  text-decoration: underline;
}}

/* Markdown rendered content */
.md-content h3 {{
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--accent-green);
  margin: 24px 0 12px;
}}

.md-content h4 {{
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 20px 0 8px;
}}

.md-content p {{
  margin-bottom: 14px;
  line-height: 1.85;
}}

.md-content strong {{
  color: var(--accent-green);
  font-weight: 600;
}}

.md-content em {{
  color: var(--text-secondary);
  font-style: italic;
}}

.md-content ul, .md-content ol {{
  padding-left: 20px;
  margin: 12px 0;
}}

.md-content li {{
  margin-bottom: 8px;
  line-height: 1.75;
}}

.md-content li::marker {{
  color: var(--accent-gold);
}}

.md-content blockquote {{
  border-left: 3px solid var(--accent-gold);
  padding: 12px 16px;
  margin: 16px 0;
  background: var(--card-bg);
  border-radius: 0 8px 8px 0;
  color: var(--text-secondary);
  font-size: 15px;
}}

.md-content blockquote p {{
  margin-bottom: 4px;
}}

.md-content hr {{
  border: none;
  border-top: 1px solid var(--border);
  margin: 24px 0;
}}

.md-content code {{
  font-family: var(--font-mono);
  font-size: 14px;
  background: #F0EBE3;
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--accent-green);
}}

.md-content a {{
  color: var(--accent-gold);
  text-decoration: underline;
  text-underline-offset: 2px;
}}

.md-content a:hover {{
  color: var(--accent-green);
}}

.md-content table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}}

.md-content table th {{
  background: var(--accent-green);
  color: #fff;
  padding: 10px 14px;
  text-align: left;
  font-weight: 500;
}}

.md-content table td {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}}

.report-loading {{
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  transition: opacity 0.5s, transform 0.5s;
}}

.report-loading.done {{
  opacity: 0;
  transform: translateY(-100%);
  pointer-events: none;
}}

.report-loading-bar {{
  height: 3px;
  background: var(--border);
  overflow: hidden;
}}

.report-loading-bar-inner {{
  height: 100%;
  background: linear-gradient(90deg, var(--accent-gold), var(--accent-green));
  width: 0%;
  transition: width 0.6s ease;
}}

.report-loading-info {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 10px 16px;
  background: rgba(250,247,242,0.95);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
}}

.report-loading-spinner {{
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--accent-gold);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}}

@keyframes spin {{
  to {{ transform: rotate(360deg); }}
}}

.report-loading-text {{
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-sans);
}}
</style>
</head>
<body>
<div class="report-loading" id="report-loading">
  <div class="report-loading-bar"><div class="report-loading-bar-inner" id="loading-bar-inner"></div></div>
  <div class="report-loading-info">
    <div class="report-loading-spinner"></div>
    <span class="report-loading-text" id="loading-text">AI 正在分析中...</span>
  </div>
</div>
<script>
(function(){{
  var total=10,loaded=0;
  var bar=document.getElementById('loading-bar-inner');
  var txt=document.getElementById('loading-text');
  var wrap=document.getElementById('report-loading');
  var labels={{1:'了解公司业务',2:'分析商业模式',3:'财务体检',4:'估值分析',5:'整理最新研报',6:'梳理市场观点',7:'分析股价走势',8:'整理财报',9:'生成交易参考',10:'生成延展问题'}};
  var ob=new MutationObserver(function(muts){{
    muts.forEach(function(m){{
      m.addedNodes.forEach(function(n){{
        if(n.nodeType===1&&n.classList&&n.classList.contains('module')){{
          loaded++;
          var pct=Math.min(Math.round(loaded/total*100),100);
          bar.style.width=pct+'%';
          var next=labels[loaded+1];
          if(next)txt.textContent='正在'+next+'...（'+pct+'%）';
        }}
        if(n.nodeType===1&&n.classList&&n.classList.contains('report-footer')){{
          bar.style.width='100%';
          txt.textContent='分析完成';
          setTimeout(function(){{wrap.classList.add('done')}},600);
          var dlBtn=document.getElementById('download-btn');
          if(dlBtn)dlBtn.classList.add('visible');
        }}
      }});
    }});
  }});
  ob.observe(document.body,{{childList:true,subtree:true}});
}})();
</script>
<div class="report-container">
<header class="report-header">
  <button class="download-btn" id="download-btn" title="下载报告" onclick="(function(btn){{btn.style.display='none';var html='<!DOCTYPE html>\\n'+document.documentElement.outerHTML;btn.style.display='';var title=document.title||'report';var fn=title.replace(/\\s*[\\|\\-].*$/,'').replace(/[\\(\\)]/g,'_').trim()+'_'+new Date().toISOString().slice(0,10)+'.html';var b=new Blob([html],{{type:'text/html;charset=utf-8'}});var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=fn;document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(a.href);}})(this)">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  </button>
  <h1>{stock_name}</h1>
  <div class="stock-code">{stock_code}</div>
  <div class="report-date">REPORT_DATE_PLACEHOLDER</div>
</header>
<div id="report-modules">
'''


MODULE_TITLES = {
    1: "这家公司在做什么",
    2: "它怎么赚钱",
    3: "财务体检",
    4: "估值坐标",
    5: "最新研报",
    6: "市场分歧",
    7: "最近股价走势分析",
    8: "财报附录",
    9: "交易参考",
    10: "你还想知道什么",
}


def module_html(module_num: int, content: str) -> str:
    """包装单个模块的HTML。AI文本部分用marked.js渲染markdown。"""
    title = MODULE_TITLES.get(module_num, f"模块{module_num}")
    return f'''
<section class="module" id="module-{module_num}">
  <div class="module-number">MODULE {module_num}</div>
  <h2>{title}</h2>
  <div class="module-content md-content">{content}</div>
</section>
'''


def report_html_footer() -> str:
    """报告底部HTML。"""
    return '''
</div>
<footer class="report-footer">
  <p class="disclaimer-main">以上为分析框架，非投资建议。投资决策应基于自身研究和判断。</p>
  <p class="brand">知行录 · 记录投资的知与行</p>
</footer>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
  if (typeof marked === 'undefined') return;
  var renderer = new marked.Renderer();
  renderer.link = function(href, title, text) {
    if (typeof href === 'object') { text = href.text; title = href.title; href = href.href; }
    var t = title ? ' title="' + title + '"' : '';
    return '<a href="' + href + '" target="_blank" rel="noopener"' + t + '>' + text + '</a>';
  };
  marked.setOptions({ breaks: true, gfm: true, renderer: renderer });
  document.querySelectorAll('.md-text').forEach(function(el) {
    el.innerHTML = marked.parse(el.textContent);
  });
});
</script>
</body>
</html>'''

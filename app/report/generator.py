import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from app.data.stock_search import search_stock
from app.data.financial_data import (
    get_financial_summary, get_profit_sheet, get_cash_flow_sheet, get_stock_info,
    get_dividend_yield,
)
from app.data.market_data import get_stock_kline, get_realtime_quote
from app.data.valuation_data import get_valuation_history
from app.data.news_data import get_stock_news, get_research_reports, get_stock_announcements, get_profit_forecast
from app.ai.llm_client import chat, chat_with_search
from app.ai.prompts import (
    module1_prompt, module2_prompt, module3_indicator_prompt,
    module4_prompt, module5_research_prompt, module5_prompt,
    module5_forecast_prompt,
    module6_prompt, module8_prompt,
    module_trade_ref_prompt,
)
from app.ai.dcf_model import calculate_dcf
from app.ai.valuation_models import run_valuation_summary
from app.report.html_template import report_html_head, module_html, report_html_footer
from app.report.chart_config import pie_chart, line_chart, kline_chart, gauge_chart


def _md(text: str) -> str:
    """将AI生成的文本包装为markdown待渲染容器。"""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="md-text">{escaped}</div>'


async def generate_report(symbol: str) -> AsyncGenerator[str, None]:
    results = await asyncio.to_thread(search_stock, symbol)
    if not results:
        yield _error_html("未找到该股票，请检查代码或名称")
        return

    stock = results[0]
    stock_code = stock["code"]
    stock_name = stock["name"]
    market = stock.get("market", "A")

    head = report_html_head(stock_name, stock_code)
    head = head.replace("REPORT_DATE_PLACEHOLDER",
                        f"分析日期：{datetime.now().strftime('%Y年%m月%d日')}")
    yield head

    data = await _fetch_all_data(stock_code, market)

    yield await _generate_module1(stock_name, data)
    yield await _generate_module2(stock_name, data)
    yield await _generate_module3(stock_name, data)
    yield await _generate_module4(stock_name, data)
    yield await _generate_module5_research(stock_name, data)
    yield await _generate_module6_divergence(stock_name, data)
    yield await _generate_module7_price(stock_name, data)
    yield _generate_module8_reports(stock_name, stock_code, data)
    yield await _generate_module9_trade_ref(stock_name, data)

    context = f"{stock_name}，最新财务数据：{_brief_financials(data)}"
    yield await _generate_module10_questions(stock_name, context)

    yield report_html_footer()


async def _fetch_all_data(symbol: str, market: str = "A") -> dict:
    tasks = {
        "info": asyncio.to_thread(get_stock_info, symbol, market),
        "financial_summary": asyncio.to_thread(get_financial_summary, symbol, market),
        "profit": asyncio.to_thread(get_profit_sheet, symbol, market),
        "cashflow": asyncio.to_thread(get_cash_flow_sheet, symbol, market),
        "kline_90d": asyncio.to_thread(get_stock_kline, symbol, 90, market),
        "valuation": asyncio.to_thread(get_valuation_history, symbol, market),
        "news": asyncio.to_thread(get_stock_news, symbol, market),
        "reports": asyncio.to_thread(get_research_reports, symbol, market),
        "announcements": asyncio.to_thread(get_stock_announcements, symbol, market),
        "quote": asyncio.to_thread(get_realtime_quote, symbol, market),
        "profit_forecast": asyncio.to_thread(get_profit_forecast, symbol, market),
        "dividend_yield": asyncio.to_thread(get_dividend_yield, symbol, market),
    }

    data = {}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for key, result in zip(tasks.keys(), results):
        data[key] = None if isinstance(result, Exception) else result
    data["_symbol"] = symbol
    data["_market"] = market
    return data


def _brief_financials(data: dict) -> str:
    fs = data.get("financial_summary")
    if fs is None or fs.empty:
        return "暂无"
    latest = fs.iloc[-1]
    parts = []
    for col in ["营业总收入", "净利润", "销售毛利率", "净资产收益率"]:
        v = latest.get(col, "")
        if v:
            parts.append(f"{col}:{v}")
    return "，".join(parts) if parts else "暂无"


async def _generate_module1(stock_name: str, data: dict) -> str:
    info = data.get("info") or {}
    fs = data.get("financial_summary")
    if fs is not None and not fs.empty:
        latest = fs.iloc[-1]
        info["营业总收入"] = latest.get("营业总收入", "")
        info["净利润"] = latest.get("净利润", "")
        info["销售毛利率"] = latest.get("销售毛利率", "")
    try:
        text = await asyncio.to_thread(chat, module1_prompt(stock_name, info))
    except Exception:
        text = f"{stock_name}的详细介绍暂时无法生成，请稍后重试。"
    return module_html(1, _md(text))


async def _generate_module2(stock_name: str, data: dict) -> str:
    profit = data.get("profit")
    fs = data.get("financial_summary")

    profit_str = "暂无数据"
    if profit is not None and not profit.empty:
        profit_str = profit.head(3).to_string()

    ind_str = "暂无数据"
    if fs is not None and not fs.empty:
        ind_str = fs.tail(5)[["报告期", "营业总收入", "净利润", "销售毛利率", "净资产收益率"]].to_string()

    try:
        text = await asyncio.to_thread(chat, module2_prompt(stock_name, profit_str, ind_str, ""))
    except Exception:
        text = "商业模式分析暂时无法生成。"
    return module_html(2, _md(text))


async def _generate_module3(stock_name: str, data: dict) -> str:
    fs = data.get("financial_summary")
    quote = data.get("quote") or {}
    content_parts = []

    if fs is not None and not fs.empty:
        metrics = [
            ("营业总收入同比增长率", "营业收入增速"),
            ("净利润同比增长率", "净利润增速"),
            ("销售毛利率", "毛利率"),
            ("净资产收益率", "ROE"),
            ("每股经营现金流", "每股经营现金流"),
        ]

        recent_20 = fs.tail(min(20, len(fs))).copy()
        x_labels = []
        if "报告期" in recent_20.columns:
            x_labels = recent_20["报告期"].astype(str).tolist()
        else:
            x_labels = [str(i) for i in range(len(recent_20))]

        chart_series = []
        for col, display_name in metrics:
            if col not in recent_20.columns:
                continue
            vals_20 = recent_20[col].apply(_parse_number).tolist()
            chart_series.append({"name": display_name, "data": vals_20})

        div_df = data.get("dividend_yield")
        if div_df is not None and not div_df.empty:
            div_map = dict(zip(div_df["报告期"].astype(str), div_df["股息率"]))
            div_vals = [div_map.get(label) for label in x_labels]
            if any(v is not None for v in div_vals):
                chart_series.append({"name": "股息率", "data": div_vals})

        if chart_series:
            trend_chart = line_chart("fin-health-chart", "财务健康趋势（近20期）", x_labels, chart_series)
            content_parts.append(trend_chart)

        abs_series = []
        for col, display_name in [("营业总收入", "营业总收入(亿元)"), ("净利润", "净利润(亿元)")]:
            if col in recent_20.columns:
                vals = recent_20[col].apply(_parse_number).tolist()
                if any(v is not None for v in vals):
                    abs_series.append({"name": display_name, "data": vals})
        if abs_series:
            abs_chart = line_chart("fin-abs-chart", "季度营收与净利润（近20期，亿元）", x_labels, abs_series)
            content_parts.insert(0, abs_chart)

        for col, display_name in metrics:
            if col not in fs.columns:
                continue
            recent = fs.tail(5).copy()
            recent[col] = recent[col].apply(_parse_number)
            values = recent[col].dropna().tolist()
            if not values:
                continue

            current = values[-1]
            trend_str = " → ".join([f"{v}" for v in values])
            unit = "%" if "率" in col or "增长" in col else "元"

            try:
                insight = await asyncio.to_thread(
                    chat, module3_indicator_prompt(stock_name, display_name, f"{current}{unit}", trend_str, "暂无")
                )
            except Exception:
                insight = ""

            card = f'''<div class="indicator-card">
  <div class="indicator-header">
    <span class="indicator-name">{display_name}</span>
    <span class="data-value">{current}{unit}</span>
  </div>
  <p class="data-label">近5期趋势：{trend_str}</p>
  {f'<div class="insight">{insight}</div>' if insight else ''}
</div>'''
            content_parts.append(card)

    dcf_html = _build_dcf_section(data, quote)
    content_parts.append(dcf_html)

    return module_html(3, "\n".join(content_parts) if content_parts else "<p>财务数据暂不可用。</p>")


def _parse_number(val):
    if val is None or val is False or str(val).strip() == "":
        return None
    s = str(val).replace("%", "").replace(",", "").strip()
    if "亿" in s:
        s = s.replace("亿", "")
        try:
            return round(float(s), 2)
        except ValueError:
            return None
    if "万" in s:
        s = s.replace("万", "")
        try:
            return round(float(s) / 10000, 4)
        except ValueError:
            return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _build_dcf_section(data: dict, quote: dict) -> str:
    cashflow = data.get("cashflow")
    fs = data.get("financial_summary")

    current_price = 0
    try:
        current_price = float(quote.get("最新价", 0))
    except (ValueError, TypeError):
        pass

    total_shares = 0
    market = data.get("_market", "A")
    if market == "HK":
        try:
            from app.data.financial_data import _yf_info_safe
            info = _yf_info_safe(data.get("_symbol", ""))
            total_shares = info.get("sharesOutstanding", 0) or 0
            net_debt_val = (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)
            if net_debt_val > 0:
                net_debt = net_debt_val
        except Exception:
            pass
    else:
        try:
            import akshare as ak
            mv_df = ak.stock_zh_valuation_baidu(symbol=data.get("_symbol", ""), indicator="总市值", period="近一年")
            if mv_df is not None and not mv_df.empty:
                total_mv = float(mv_df.iloc[-1]["value"]) * 1e8
                if current_price > 0 and total_mv > 0:
                    total_shares = total_mv / current_price
        except Exception:
            pass

    if current_price <= 0 or total_shares <= 0:
        return '<div class="disclaimer">DCF估值：缺少股价或股本数据，无法计算。</div>'

    operating_cf = []
    capex_list = []
    if cashflow is not None and not cashflow.empty:
        for col in cashflow.columns:
            if "经营活动产生的现金流量净额" in str(col):
                for v in cashflow[col].dropna().tolist():
                    try:
                        operating_cf.append(float(v))
                    except (ValueError, TypeError):
                        continue
                break
        for col in cashflow.columns:
            col_str = str(col)
            if "购建固定资产" in col_str or "购买固定资产" in col_str:
                for v in cashflow[col].dropna().tolist():
                    try:
                        capex_list.append(abs(float(v)))
                    except (ValueError, TypeError):
                        continue
                break

    fcf_list = []
    if operating_cf:
        if capex_list and len(capex_list) == len(operating_cf):
            fcf_list = [ocf - cap for ocf, cap in zip(operating_cf, capex_list)]
        else:
            fcf_list = operating_cf

    if fcf_list and len(fcf_list) > 5:
        fcf_list = fcf_list[-5:]
    elif fcf_list:
        fcf_list = fcf_list[-len(fcf_list):]

    growth_list = []
    if fs is not None and not fs.empty and "营业总收入同比增长率" in fs.columns:
        for v in fs.tail(5)["营业总收入同比增长率"].tolist():
            n = _parse_number(v)
            if n is not None:
                growth_list.append(n / 100)

    net_debt = 0.0

    if not fcf_list:
        return '<div class="disclaimer">DCF估值：缺少现金流数据，无法计算。</div>'

    dcf = calculate_dcf(fcf_list, growth_list, current_price, total_shares, net_debt=net_debt)
    if "error" in dcf:
        return f'<div class="disclaimer">{dcf["error"]}</div>'

    mid = dcf["中性"]
    opt = dcf["乐观"]
    pes = dcf["悲观"]

    detail_rows = ""
    for i in range(10):
        stage = "I" if i < 5 else "II"
        detail_rows += f'<tr><td>第{i+1}年<sup style="color:var(--text-secondary);font-size:10px;">{stage}</sup></td><td id="dcf-fcf-{i}"></td>'
        detail_rows += f'<td id="dcf-df-{i}"></td><td id="dcf-pv-{i}"></td></tr>'

    dcf_params = json.dumps({
        "base_fcf": dcf["base_fcf"],
        "growth_1_5": dcf["growth_1_5"],
        "growth_6_10": dcf["growth_6_10"],
        "current_price": current_price,
        "total_shares": total_shares,
        "net_debt": dcf.get("net_debt", 0),
        "wacc": dcf["wacc_raw"],
        "terminal_growth": dcf["terminal_growth_raw"],
    }, ensure_ascii=False)

    return f'''<div class="indicator-card">
  <h3 style="font-family:var(--font-serif);margin-bottom:12px;">DCF估值分析（10年两阶段）</h3>
  <div id="dcf-summary">
    <p>中性假设下内在价值：<strong id="dcf-mid-value">¥{mid["内在价值"]}/股</strong>（第1-5年 <span id="dcf-mid-growth">{mid["增速假设_1_5"]}%</span> / 第6-10年 <span id="dcf-mid-growth2">{mid["增速假设_6_10"]}%</span>）</p>
    <p>当前股价：¥{current_price}/股，<strong id="dcf-judgment" class="{"up" if mid["偏离度"] > 0 else "down"}">当前{dcf["判断"]}约 {dcf["判断幅度"]}%</strong></p>
    <p style="font-size:14px;color:var(--text-secondary);" id="dcf-scenarios">乐观：¥{opt["内在价值"]}（{opt["偏离度"]:+.1f}%） | 悲观：¥{pes["内在价值"]}（{pes["偏离度"]:+.1f}%）</p>
    <p style="font-size:13px;color:var(--text-secondary);">敏感性区间：¥{dcf["sensitivity_low"]} ~ ¥{dcf["sensitivity_high"]}</p>
  </div>

  <div id="dcf-gauge-container" style="width:100%;height:280px;margin:20px 0;"></div>

  <div class="dcf-controls">
    <h4 style="font-family:var(--font-serif);margin-bottom:12px;font-size:15px;">调整参数（拖动滑块重新计算）</h4>
    <div class="dcf-control-row">
      <label>WACC（加权平均资本成本）</label>
      <input type="range" id="dcf-wacc" min="5" max="15" step="0.5" value="{dcf["wacc_raw"]*100:.1f}">
      <span id="dcf-wacc-val">{dcf["wacc_raw"]*100:.1f}%</span>
    </div>
    <div class="dcf-control-row">
      <label>永续增长率</label>
      <input type="range" id="dcf-tg" min="1" max="4" step="0.5" value="{dcf["terminal_growth_raw"]*100:.1f}">
      <span id="dcf-tg-val">{dcf["terminal_growth_raw"]*100:.1f}%</span>
    </div>
    <div class="dcf-control-row">
      <label>第1-5年增速</label>
      <input type="range" id="dcf-g1" min="-5" max="30" step="0.5" value="{dcf["growth_1_5"]*100:.1f}">
      <span id="dcf-g1-val">{dcf["growth_1_5"]*100:.1f}%</span>
    </div>
    <div class="dcf-control-row">
      <label>第6-10年增速</label>
      <input type="range" id="dcf-g2" min="-5" max="20" step="0.5" value="{dcf["growth_6_10"]*100:.1f}">
      <span id="dcf-g2-val">{dcf["growth_6_10"]*100:.1f}%</span>
    </div>
  </div>

  <h4 style="font-family:var(--font-serif);margin:20px 0 12px;font-size:15px;">中性情景计算明细</h4>
  <table class="fin-table" id="dcf-detail-table">
    <thead><tr><th>年份</th><th>预测FCF</th><th>折现因子</th><th>现值</th></tr></thead>
    <tbody id="dcf-detail-body">
      {detail_rows}
      <tr style="font-weight:600;"><td>终值</td><td id="dcf-tv" colspan="2"></td><td id="dcf-tv-pv"></td></tr>
      <tr style="font-weight:700;background:#F5F0E8;"><td>合计</td><td colspan="2">企业价值</td><td id="dcf-ev"></td></tr>
    </tbody>
  </table>

  <div class="disclaimer">DCF估值基于模型假设，实际价值受多种因素影响，仅作为分析参考框架。</div>
</div>
<script>
(function(){{
  var P={dcf_params};
  var gaugeChart=echarts.init(document.getElementById('dcf-gauge-container'),null,{{renderer:'canvas'}});

  function fmt(n){{ return (n/1e8).toFixed(2)+'亿'; }}
  function fmtS(n){{ return n.toFixed(2); }}

  function calcDCF(wacc,tg,g1,g2){{
    var scenarios={{}};
    var mults={{'乐观':1.3,'中性':1.0,'悲观':0.6}};
    for(var label in mults){{
      var sg1=g1*mults[label];
      var sg2=g2*mults[label];
      sg1=Math.max(Math.min(sg1,0.30),-0.10);
      sg2=Math.max(Math.min(sg2,0.20),-0.05);
      var fcfs=[],dfs=[],pvs=[];
      var fcf=P.base_fcf;
      var totalPv=0;
      for(var y=1;y<=10;y++){{
        if(y<=5){{ fcf=fcf*(1+sg1); }}
        else{{ fcf=fcf*(1+sg2); }}
        var df=Math.pow(1+wacc,y);
        fcfs.push(fcf);dfs.push(df);pvs.push(fcf/df);
        totalPv+=fcf/df;
      }}
      var tv=(fcf*(1+tg))/(wacc-tg);
      var tvpv=tv/Math.pow(1+wacc,10);
      var ev=totalPv+tvpv;
      var eqv=ev-(P.net_debt||0);
      var ps=eqv/P.total_shares;
      var dev=(ps-P.current_price)/P.current_price*100;
      scenarios[label]={{ps:ps,dev:dev,g1:sg1*100,g2:sg2*100,fcfs:fcfs,dfs:dfs,pvs:pvs,tv:tv,tvpv:tvpv,ev:ev,eqv:eqv}};
    }}
    return scenarios;
  }}

  function updateUI(){{
    var wacc=parseFloat(document.getElementById('dcf-wacc').value)/100;
    var tg=parseFloat(document.getElementById('dcf-tg').value)/100;
    var g1=parseFloat(document.getElementById('dcf-g1').value)/100;
    var g2=parseFloat(document.getElementById('dcf-g2').value)/100;
    document.getElementById('dcf-wacc-val').textContent=((wacc*100).toFixed(1))+'%';
    document.getElementById('dcf-tg-val').textContent=((tg*100).toFixed(1))+'%';
    document.getElementById('dcf-g1-val').textContent=((g1*100).toFixed(1))+'%';
    document.getElementById('dcf-g2-val').textContent=((g2*100).toFixed(1))+'%';

    if(wacc<=tg){{document.getElementById('dcf-summary').innerHTML='<p style="color:#D97757;">WACC必须大于永续增长率</p>';return;}}

    var s=calcDCF(wacc,tg,g1,g2);
    var mid=s['中性'],opt=s['乐观'],pes=s['悲观'];

    document.getElementById('dcf-mid-value').textContent='¥'+fmtS(mid.ps)+'/股';
    document.getElementById('dcf-mid-growth').textContent=mid.g1.toFixed(1)+'%';
    document.getElementById('dcf-mid-growth2').textContent=mid.g2.toFixed(1)+'%';
    var j=mid.dev>0?'被低估':'被高估';
    var jEl=document.getElementById('dcf-judgment');
    jEl.textContent='当前'+j+'约 '+Math.abs(mid.dev).toFixed(1)+'%';
    jEl.className=mid.dev>0?'up':'down';
    document.getElementById('dcf-scenarios').textContent='乐观：¥'+fmtS(opt.ps)+'（'+(opt.dev>0?'+':'')+opt.dev.toFixed(1)+'%） | 悲观：¥'+fmtS(pes.ps)+'（'+(pes.dev>0?'+':'')+pes.dev.toFixed(1)+'%）';

    for(var i=0;i<10;i++){{
      document.getElementById('dcf-fcf-'+i).textContent=fmt(mid.fcfs[i]);
      document.getElementById('dcf-df-'+i).textContent=mid.dfs[i].toFixed(4);
      document.getElementById('dcf-pv-'+i).textContent=fmt(mid.pvs[i]);
    }}
    document.getElementById('dcf-tv').textContent=fmt(mid.tv);
    document.getElementById('dcf-tv-pv').textContent=fmt(mid.tvpv);
    document.getElementById('dcf-ev').textContent=fmt(mid.ev);

    gaugeChart.setOption({{
      title:{{text:'DCF估值 vs 当前股价',left:'center',textStyle:{{fontFamily:"'Source Serif Pro','Noto Serif SC',serif",fontSize:14,color:'#2A2A2A'}}}},
      series:[{{type:'gauge',startAngle:180,endAngle:0,min:pes.ps,max:opt.ps,
        pointer:{{show:true,length:'60%',width:4,itemStyle:{{color:'#C9A961'}}}},
        axisLine:{{lineStyle:{{width:20,color:[[0.3,'#7A9B6E'],[0.7,'#E8A87C'],[1,'#D97757']]}}}},
        axisTick:{{show:false}},splitLine:{{show:false}},
        splitNumber:4,
        axisLabel:{{fontSize:11,distance:30}},
        detail:{{formatter:'{{value}}\\n当前股价 ¥'+P.current_price,fontSize:16,offsetCenter:[0,'40%'],color:'#2A2A2A'}},
        data:[{{value:P.current_price.toFixed(2)}}]
      }}]
    }});
  }}

  document.getElementById('dcf-wacc').addEventListener('input',updateUI);
  document.getElementById('dcf-tg').addEventListener('input',updateUI);
  document.getElementById('dcf-g1').addEventListener('input',updateUI);
  document.getElementById('dcf-g2').addEventListener('input',updateUI);
  updateUI();
  window.addEventListener('resize',function(){{gaugeChart.resize()}});
}})();
</script>'''


def _build_valuation_summary_table(data: dict) -> str:
    results = run_valuation_summary(data)
    if not results:
        return ""

    rows = ""
    note = ""
    for r in results:
        fair_val = f"¥{r['fair_value']:.2f}"
        pd_val = r["premium_discount"]
        pd_str = f"{pd_val:+.1f}%"

        assessment = r["assessment"]
        if pd_val < -10:
            css_class = "down"
            if "Overvalued" in assessment or "overvalued" in assessment:
                assessment = "估值过高"
        elif pd_val > 10:
            css_class = "up"
            if "Undervalued" in assessment or "undervalued" in assessment:
                assessment = "被低估"
        else:
            css_class = ""
            if assessment == "定价":
                pass
            elif "Fair" in assessment or "fair" in assessment:
                assessment = "定价合理"

        if r.get("note"):
            note = r["note"]

        rows += f'<tr><td><strong>{r["method"]}</strong></td><td>{fair_val}</td><td>{pd_str}</td><td class="{css_class}">{assessment}</td></tr>\n'

    table = f'''<div class="indicator-card">
  <h3 style="font-family:var(--font-serif);margin-bottom:12px;">估值汇总</h3>
  <table class="fin-table">
    <thead><tr><th>方法</th><th>公允价值</th><th>溢价/折价</th><th>评估</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {f'<p class="data-label" style="margin-top:8px;">{note}</p>' if note else ''}
  <div class="disclaimer" style="margin-top:12px;">以上估值基于经典模型和公开财务数据自动计算，仅供参考。不同方法适用于不同类型的公司。</div>
</div>'''
    return table


async def _generate_module4(stock_name: str, data: dict) -> str:
    val_data = data.get("valuation") or {}
    content_parts = []

    valuation_table = _build_valuation_summary_table(data)
    if valuation_table:
        content_parts.append(valuation_table)

    for key, display in [("pe", "PE(TTM)"), ("pb", "PB")]:
        df = val_data.get(key)
        if df is None or df.empty:
            continue

        five_years_ago = datetime.now().timestamp() - 5 * 365 * 86400
        df_5y = df[df["date"] >= datetime.fromtimestamp(five_years_ago)].copy()
        if df_5y.empty:
            df_5y = df.tail(250)

        series = df_5y["value"]
        current = float(series.iloc[-1])
        hist_min = float(series.min())
        hist_max = float(series.max())
        percentile = (series < current).sum() / len(series) * 100

        try:
            insight = await asyncio.to_thread(
                chat, module4_prompt(
                    stock_name, display, f"{current:.1f}",
                    f"[{hist_min:.1f}, {hist_max:.1f}]",
                    f"{percentile:.0f}%分位", "暂无"
                )
            )
        except Exception:
            insight = ""

        chart = gauge_chart(
            f"val-{key}", f"{display} 历史分位",
            current, hist_min, hist_max, f"{percentile:.0f}%分位"
        )

        card = f'''<div class="indicator-card">
  <div class="indicator-header">
    <span class="indicator-name">{display}</span>
    <span class="data-value">{current:.1f}</span>
  </div>
  <p class="data-label">历史5年区间：[{hist_min:.1f}, {hist_max:.1f}]，当前在 {percentile:.0f}%分位</p>
  {chart}
  {f'<div class="insight">{insight}</div>' if insight else ''}
</div>'''
        content_parts.append(card)

    return module_html(4, "\n".join(content_parts) if content_parts else "<p>估值数据暂不可用。</p>")


async def _generate_module5_research(stock_name: str, data: dict) -> str:
    reports = data.get("reports")
    market = data.get("_market", "A")

    rows = []
    if reports is not None and not reports.empty:
        for _, row in reports.head(3).iterrows():
            title = str(row.get("报告名称", row.iloc[0] if len(row) > 0 else "未知标题"))
            org = str(row.get("机构", ""))
            date = str(row.get("日期", ""))
            link = str(row.get("报告PDF链接", ""))
            rating = str(row.get("东财评级", ""))

            try:
                summary = await asyncio.to_thread(
                    chat, module5_research_prompt(stock_name, title, org, date, rating)
                )
            except Exception:
                summary = "摘要生成失败。"

            link_html = f' · <a href="{link}" target="_blank" style="color:var(--accent-gold);">查看原文</a>' if link and link != "nan" else ""
            rows.append(f'''<div class="indicator-card">
  <div class="indicator-header">
    <span class="indicator-name" style="font-size:14px;">{title}</span>
    <span class="data-label">{date}</span>
  </div>
  <p class="data-label">机构：{org}{f" · 评级：{rating}" if rating and rating != "nan" else ""}{link_html}</p>
  <div class="insight">{summary}</div>
</div>''')
    elif market == "HK":
        try:
            prompt = f"请搜索{stock_name}最近3个月的券商研报或分析师报告，列出最新的3篇研报，每篇包含：标题、发布机构、日期、核心观点（1-2句话）。如果找不到具体研报，请基于公开信息总结近期主要券商对该股的看法。用中文回答。"
            text = await asyncio.to_thread(chat_with_search, prompt)
            rows.append(f'<div class="indicator-card"><div class="insight">{text}</div></div>')
        except Exception:
            pass

    forecast_html = await _build_forecast_section(stock_name, data)
    content = "\n".join(rows) + forecast_html
    if not rows and not forecast_html:
        content = "<p>暂无研报数据。</p>"
    return module_html(5, content)


async def _build_forecast_section(stock_name: str, data: dict) -> str:
    forecast = data.get("profit_forecast")
    if not forecast:
        return ""

    eps_df = forecast.get("eps")
    profit_df = forecast.get("net_profit")
    ratings = forecast.get("ratings") or {}

    has_eps = eps_df is not None and not eps_df.empty
    has_profit = profit_df is not None and not profit_df.empty
    has_ratings = bool(ratings)

    if not has_eps and not has_profit and not has_ratings:
        return ""

    parts = ['<h3 style="font-family:var(--font-serif);margin:32px 0 16px;color:var(--accent-green);">分析师盈利预测</h3>']

    if has_ratings:
        buy = int(ratings.get("机构投资评级(近六个月)-买入", 0) or 0)
        overweight = int(ratings.get("机构投资评级(近六个月)-增持", 0) or 0)
        neutral = int(ratings.get("机构投资评级(近六个月)-中性", 0) or 0)
        reduce_r = int(ratings.get("机构投资评级(近六个月)-减持", 0) or 0)
        sell = int(ratings.get("机构投资评级(近六个月)-卖出", 0) or 0)
        report_count = ratings.get("研报数", 0)
        parts.append(f'''<div class="indicator-card">
  <div class="indicator-header">
    <span class="indicator-name">机构评级分布（近六个月）</span>
    <span class="data-label">{report_count}篇研报</span>
  </div>
  <p><span class="data-value" style="font-size:18px;">买入 {buy}</span> · 增持 {overweight} · 中性 {neutral} · 减持 {reduce_r} · 卖出 {sell}</p>
</div>''')

    if has_eps:
        table_rows = ""
        for _, row in eps_df.iterrows():
            table_rows += f'<tr><td>{row["年度"]}</td><td>{row["预测机构数"]}</td><td>{row["最小值"]}</td><td>{row["均值"]}</td><td>{row["最大值"]}</td></tr>'
        parts.append(f'''<div class="indicator-card">
  <div class="indicator-header"><span class="indicator-name">每股收益预测（元）</span></div>
  <table class="fin-table">
  <thead><tr><th>年度</th><th>预测机构数</th><th>最小值</th><th>均值</th><th>最大值</th></tr></thead>
  <tbody>{table_rows}</tbody>
  </table>
</div>''')

        years = eps_df["年度"].astype(str).tolist()
        chart_series = [
            {"name": "最高预测", "data": [float(v) for v in eps_df["最大值"].tolist()]},
            {"name": "平均预测", "data": [float(v) for v in eps_df["均值"].tolist()]},
            {"name": "最低预测", "data": [float(v) for v in eps_df["最小值"].tolist()]},
        ]
        parts.append(line_chart("forecast-eps-chart", "每股收益预测趋势（元）", years, chart_series))

    if has_profit:
        table_rows = ""
        for _, row in profit_df.iterrows():
            table_rows += f'<tr><td>{row["年度"]}</td><td>{row["预测机构数"]}</td><td>{row["最小值"]:.2f}亿</td><td>{row["均值"]:.2f}亿</td><td>{row["最大值"]:.2f}亿</td></tr>'
        parts.append(f'''<div class="indicator-card">
  <div class="indicator-header"><span class="indicator-name">净利润预测（亿元）</span></div>
  <table class="fin-table">
  <thead><tr><th>年度</th><th>预测机构数</th><th>最小值</th><th>均值</th><th>最大值</th></tr></thead>
  <tbody>{table_rows}</tbody>
  </table>
</div>''')

    eps_str = eps_df.to_string() if has_eps else "暂无"
    profit_str = profit_df.to_string() if has_profit else "暂无"
    ratings_str = (
        f"买入:{ratings.get('机构投资评级(近六个月)-买入',0)}, "
        f"增持:{ratings.get('机构投资评级(近六个月)-增持',0)}, "
        f"中性:{ratings.get('机构投资评级(近六个月)-中性',0)}"
    ) if has_ratings else "暂无"

    try:
        insight = await asyncio.to_thread(
            chat, module5_forecast_prompt(stock_name, eps_str, profit_str, ratings_str)
        )
        parts.append(f'<div class="insight">{insight}</div>')
    except Exception:
        pass

    return "\n".join(parts)


async def _generate_module6_divergence(stock_name: str, data: dict) -> str:
    news = data.get("news")
    reports = data.get("reports")

    news_text = "暂无近期新闻"
    if news is not None and not news.empty:
        items = []
        for _, row in news.head(15).iterrows():
            title = row.get("新闻标题", "")
            date = row.get("发布时间", "")
            if title:
                items.append(f"- [{date}] {title}")
        if items:
            news_text = "\n".join(items)

    report_text = "暂无近期研报"
    if reports is not None and not reports.empty:
        items = []
        for _, row in reports.head(5).iterrows():
            title = str(row.iloc[0]) if len(row) > 0 else ""
            org = str(row.get("机构", row.iloc[1] if len(row) > 1 else "")) if len(row) > 1 else ""
            date = str(row.get("日期", row.iloc[-1] if len(row) > 0 else ""))
            if title:
                items.append(f"- [{date}] {title}（机构：{org}）")
        if items:
            report_text = "\n".join(items)

    try:
        text = await asyncio.to_thread(chat_with_search, module5_prompt(stock_name, news_text, report_text))
    except Exception:
        text = "市场分歧分析暂时无法生成。"

    return module_html(6, _md(text))


async def _generate_module7_price(stock_name: str, data: dict) -> str:
    kline = data.get("kline_90d")
    news = data.get("news")

    if kline is None or kline.empty:
        return module_html(6, "<p>近期K线数据暂不可用。</p>")

    dates = kline["date"].astype(str).tolist()
    opens = kline["open"].tolist()
    closes = kline["close"].tolist()
    lows = kline["low"].tolist()
    highs = kline["high"].tolist()
    volumes = kline["volume"].tolist() if "volume" in kline.columns else [0] * len(dates)
    kline_data = [[o, c, l, h] for o, c, l, h in zip(opens, closes, lows, highs)]

    first_close = closes[0] if closes else 0
    last_close = closes[-1] if closes else 0
    change_pct = (last_close - first_close) / first_close * 100 if first_close else 0

    kline_summary = (
        f"区间涨跌幅: {change_pct:+.1f}%\n"
        f"最高价: {max(highs)}\n最低价: {min(lows)}\n"
        f"最新收盘: {last_close}\n交易日数: {len(dates)}"
    )

    news_text = "暂无同期新闻"
    if news is not None and not news.empty:
        items = []
        for _, row in news.head(10).iterrows():
            title = row.get("新闻标题", "")
            date = row.get("发布时间", "")
            if title:
                items.append(f"- [{date}] {title}")
        if items:
            news_text = "\n".join(items)

    try:
        text = await asyncio.to_thread(chat_with_search, module6_prompt(stock_name, kline_summary, news_text))
    except Exception:
        text = "走势分析暂时无法生成。"

    chart = kline_chart("kline-90d", f"{stock_name} 近90日走势", dates, kline_data, volumes)

    return module_html(7, f'''{chart}
{_md(text)}
<div class="disclaimer">以上走势分析基于公开信息，不构成对未来股价的预测或投资建议。</div>''')


def _generate_module8_reports(stock_name: str, symbol: str, data: dict) -> str:
    announcements = data.get("announcements")
    rows = []

    if announcements is not None and not announcements.empty:
        for _, row in announcements.iterrows():
            title = str(row.get("公告标题", row.iloc[0] if len(row) > 0 else ""))
            date = str(row.get("公告日期", row.iloc[1] if len(row) > 1 else ""))
            if any(kw in title for kw in ["年报", "季报", "中报", "年度报告", "季度报告", "半年度"]):
                rows.append(f"<tr><td>{title}</td><td>{date}</td></tr>")
            if len(rows) >= 4:
                break

    if not rows:
        rows.append(f'<tr><td colspan="2">请访问 <a href="http://www.cninfo.com.cn" target="_blank">巨潮资讯网</a> 搜索"{stock_name}"查看财报。</td></tr>')

    table = f'''<table class="fin-table">
<thead><tr><th>财报</th><th>披露日期</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>'''
    return module_html(8, table)


async def _generate_module9_trade_ref(stock_name: str, data: dict) -> str:
    quote = data.get("quote") or {}
    current_price = 0
    try:
        current_price = float(quote.get("最新价", 0))
    except (ValueError, TypeError):
        pass

    context_parts = [f"股票名称：{stock_name}", f"当前股价：¥{current_price}"]

    fs = data.get("financial_summary")
    if fs is not None and not fs.empty:
        latest = fs.iloc[-1]
        for col in ["营业总收入", "净利润", "销售毛利率", "净资产收益率", "营业总收入同比增长率"]:
            v = latest.get(col, "")
            if v:
                context_parts.append(f"{col}：{v}")

    kline = data.get("kline_90d")
    if kline is not None and not kline.empty:
        highs = kline["high"].tolist()
        lows = kline["low"].tolist()
        closes = kline["close"].tolist()
        context_parts.append(f"90日最高价：{max(highs)}")
        context_parts.append(f"90日最低价：{min(lows)}")
        context_parts.append(f"90日涨跌幅：{(closes[-1] - closes[0]) / closes[0] * 100:+.1f}%")

    val_data = data.get("valuation") or {}
    for key, display in [("pe", "PE(TTM)"), ("pb", "PB")]:
        df = val_data.get(key)
        if df is not None and not df.empty:
            current_val = float(df["value"].iloc[-1])
            series = df["value"]
            percentile = (series < current_val).sum() / len(series) * 100
            context_parts.append(f"{display}：{current_val:.1f}，历史分位{percentile:.0f}%")

    context_parts.append(f"DCF估值参考：详见财务体检模块")

    full_context = "\n".join(context_parts)

    try:
        text = await asyncio.to_thread(chat_with_search, module_trade_ref_prompt(stock_name, full_context))
    except Exception:
        text = "交易参考分析暂时无法生成。"

    disclaimer = '<div class="trading-disclaimer">以上交易参考基于历史数据和模型分析，不构成任何投资建议。股市有风险，投资需谨慎，请结合自身情况独立判断。</div>'
    return module_html(9, f'{_md(text)}\n{disclaimer}')


async def _generate_module10_questions(stock_name: str, context: str) -> str:
    try:
        text = await asyncio.to_thread(chat, module8_prompt(stock_name, context))
    except Exception:
        text = f"1. {stock_name}未来的增长空间在哪里？\n2. 当前的估值水平是否合理？\n3. 主要的风险因素有哪些？"

    questions = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            q = line.lstrip("0123456789.-、）) ").strip()
            if q:
                questions.append(f"<li>{q}</li>")

    if not questions:
        questions = [f"<li>{text}</li>"]

    return module_html(10, f'<ul class="questions-list">{"".join(questions)}</ul>')


def _error_html(message: str) -> str:
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>body{{background:#FAF7F2;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;}}
.err{{text-align:center;color:#6B6B6B;}}.err h2{{color:#2C3E2D;margin-bottom:12px;}}</style></head>
<body><div class="err"><h2>未找到结果</h2><p>{message}</p></div></body></html>'''

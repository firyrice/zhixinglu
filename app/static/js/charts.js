const Charts = {
  profiles: null,
  colors: ['#2C3E2D', '#4A6B4E', '#7A9B6E', '#C9A961', '#E8A87C', '#8B7355', '#2A3B4D', '#6B8FA3'],

  async render(container, quotes) {
    const held = Store.getHeldStocks();
    if (!held.length) {
      container.innerHTML = '<div class="empty-state"><p>添加持仓后即可查看组合穿透分析</p></div>';
      return;
    }
    container.innerHTML = '<div class="charts-container"><p class="text-secondary text-sm" style="text-align:center;">正在加载穿透数据...</p></div>';

    // 每次切换到穿透 tab 都重新加载 profiles，避免缓存导致看不到数据
    try {
      const symbols = held.map(s => s.code).join(',');
      const resp = await fetch('/api/stock-profiles?symbols=' + symbols);
      this.profiles = await resp.json();
    } catch {
      container.innerHTML = '<div class="charts-container"><p class="text-secondary text-sm" style="text-align:center;">穿透数据加载失败，请稍后刷新</p></div>';
      return;
    }

    if (!this.profiles || !Object.keys(this.profiles).length) {
      container.innerHTML = '<div class="charts-container"><p class="text-secondary text-sm" style="text-align:center;">暂无穿透数据，请稍后刷新</p></div>';
      return;
    }

    const stocks = held.map(s => {
      const q = quotes[s.code] || {};
      const p = this.profiles[s.code] || {};
      return {
        code: s.code, name: q.name || p.name || s.name,
        marketValue: (q.price || 0) * s.shares,
        industry: p.industry || '未知',
        capType: p.cap_type || '未知',
        totalMv: p.total_mv || 0,
        peTtm: p.pe_ttm || 0,
        dividendYield: p.dividend_yield || 0
      };
    });

    container.innerHTML = `
      <div class="charts-container">
        <div class="chart-section">
          <h4>持仓明细</h4>
          <div id="stock-detail-table"></div>
        </div>
        <div class="chart-section">
          <h4>行业分布</h4>
          <div id="chart-industry" style="height:320px;"></div>
          <div id="industry-table"></div>
        </div>
        <div class="chart-section">
          <h4>股票风格穿透</h4>
          <div class="chart-row">
            <div id="chart-cap" style="height:280px;"></div>
            <div id="chart-style" style="height:280px;"></div>
            <div id="chart-dividend" style="height:280px;"></div>
          </div>
        </div>
      </div>`;

    this._renderDetailTable(stocks);
    this._renderIndustry(stocks);
    this._renderCapSize(stocks);
    this._renderValuationStyle(stocks);
    this._renderDividend(stocks);
  },

  _renderDetailTable(stocks) {
    const el = document.getElementById('stock-detail-table');
    if (!el) return;
    const total = stocks.reduce((s, d) => s + d.marketValue, 0);
    el.innerHTML = '<table style="width:100%;font-size:13px;border-collapse:collapse;">' +
      '<tr style="color:var(--text-secondary);"><td style="padding:6px 0;">股票</td><td>行业</td><td>市值类型</td><td>持仓市值</td><td>占比</td></tr>' +
      stocks.sort((a, b) => b.marketValue - a.marketValue).map(s => {
        const pct = total > 0 ? (s.marketValue / total * 100).toFixed(1) : '0.0';
        return `<tr style="border-top:1px solid var(--border);"><td style="padding:6px 0;"><span style="font-weight:500;">${s.name}</span><br><span class="mono text-secondary" style="font-size:11px;">${s.code}</span></td><td>${s.industry}</td><td>${s.capType}</td><td class="mono">¥${s.marketValue.toLocaleString('zh-CN',{maximumFractionDigits:0})}</td><td>${pct}%</td></tr>`;
      }).join('') +
      '</table>';
  },

  _renderIndustry(stocks) {
    const groups = {};
    stocks.forEach(s => {
      if (!groups[s.industry]) groups[s.industry] = { value: 0, stocks: [] };
      groups[s.industry].value += s.marketValue;
      groups[s.industry].stocks.push(s.name);
    });
    let data = Object.entries(groups).map(([name, g]) => ({ name, value: Math.round(g.value), stocks: g.stocks }));
    data.sort((a, b) => b.value - a.value);
    if (data.length > 8) {
      const main = data.slice(0, 7);
      const other = data.slice(7).reduce((acc, d) => ({ name: '其他', value: acc.value + d.value, stocks: [...acc.stocks, ...d.stocks] }), { name: '其他', value: 0, stocks: [] });
      data = [...main, other];
    }
    this._pie('chart-industry', '行业分布', data);

    const total = data.reduce((s, d) => s + d.value, 0);
    const tableEl = document.getElementById('industry-table');
    if (tableEl && total > 0) {
      tableEl.innerHTML = '<table style="width:100%;font-size:13px;margin-top:12px;border-collapse:collapse;">' +
        '<tr style="color:var(--text-secondary);"><td style="padding:6px 0;">行业</td><td>持仓市值</td><td>占比</td><td>包含股票</td></tr>' +
        data.map(d => `<tr style="border-top:1px solid var(--border);"><td style="padding:6px 0;">${d.name}</td><td class="mono">¥${(d.value/1).toLocaleString('zh-CN',{maximumFractionDigits:0})}</td><td>${(d.value/total*100).toFixed(1)}%</td><td class="text-secondary">${d.stocks.join('、')}</td></tr>`).join('') +
        '</table>';
    }
  },

  _renderCapSize(stocks) {
    const groups = { '大盘股': 0, '中盘股': 0, '小盘股': 0 };
    stocks.forEach(s => {
      const key = groups.hasOwnProperty(s.capType) ? s.capType : '小盘股';
      groups[key] += s.marketValue;
    });
    const data = Object.entries(groups).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value: Math.round(value) }));
    this._pie('chart-cap', '市值规模', data, ['#2C3E2D', '#7A9B6E', '#C9A961']);
  },

  _renderValuationStyle(stocks) {
    const groups = { '价值型（PE分位<30%）': 0, '均衡型（30%-70%）': 0, '成长型（PE分位>70%）': 0 };
    stocks.forEach(s => {
      if (s.peTtm <= 0) groups['均衡型（30%-70%）'] += s.marketValue;
      else if (s.peTtm < 20) groups['价值型（PE分位<30%）'] += s.marketValue;
      else if (s.peTtm < 40) groups['均衡型（30%-70%）'] += s.marketValue;
      else groups['成长型（PE分位>70%）'] += s.marketValue;
    });
    const data = Object.entries(groups).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value: Math.round(value) }));
    this._pie('chart-style', '估值风格', data, ['#2A3B4D', '#E8A87C', '#D97757']);
  },

  _renderDividend(stocks) {
    const groups = { '高股息（>3%）': 0, '中股息（1%-3%）': 0, '低股息（<1%）': 0 };
    stocks.forEach(s => {
      if (s.dividendYield >= 3) groups['高股息（>3%）'] += s.marketValue;
      else if (s.dividendYield >= 1) groups['中股息（1%-3%）'] += s.marketValue;
      else groups['低股息（<1%）'] += s.marketValue;
    });
    const data = Object.entries(groups).filter(([,v]) => v > 0).map(([name, value]) => ({ name, value: Math.round(value) }));
    this._pie('chart-dividend', '股息特征', data, ['#C9A961', '#8B7355', '#E5E0D8']);
  },

  _pie(id, title, data, customColors) {
    const el = document.getElementById(id);
    if (!el || !data.length) return;
    const chart = echarts.init(el);
    chart.setOption({
      title: { text: title, left: 'center', top: 5, textStyle: { fontFamily: "'Noto Serif SC', serif", fontSize: 14, color: '#2A2A2A' } },
      tooltip: { trigger: 'item', formatter: '{b}<br/>¥{c} ({d}%)' },
      color: customColors || this.colors,
      series: [{
        type: 'pie', radius: ['35%', '65%'], center: ['50%', '55%'],
        itemStyle: { borderRadius: 4, borderColor: '#FAF7F2', borderWidth: 2 },
        label: { formatter: '{b}\n{d}%', fontSize: 11 },
        data
      }]
    });
    window.addEventListener('resize', () => chart.resize());
  }
};

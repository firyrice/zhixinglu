const Portfolio = {
  profiles: {},
  quotes: {},
  activeTab: 'pnl',
  refreshTimer: null,
  lastUpdate: null,

  async render() {
    const app = document.getElementById('app');
    if (!Store.hasStocks()) {
      this._renderEmpty(app);
      return;
    }
    app.innerHTML = this._shell();
    await this.refreshQuotes();
    this._startAutoRefresh();
  },

  _shell() {
    const settings = Store.getSettings();
    return `
      <div class="portfolio-header">
        <span class="back-btn" onclick="Router.navigate('/')">&#8592; 知行录</span>
        <h2>我的持仓</h2>
        <div class="actions">
          <button class="btn btn-sm btn-secondary" onclick="ImportScreenshot.showImport()" title="截图导入">&#128247; 导入</button>
          <button class="btn btn-sm btn-gold" onclick="AddStock.showAdd()">+ 添加</button>
          <button class="btn btn-sm btn-secondary" onclick="Portfolio.refreshQuotes()" title="刷新行情">&#8635;</button>
        </div>
      </div>
      <div class="summary-card card" id="summary-card" style="position:relative;margin:16px;">
        <span class="eye-toggle" onclick="Portfolio.toggleHide()">${settings.hide_amount ? '&#9673;' : '&#9678;'}</span>
        <div id="summary-content"><span class="text-secondary text-sm">加载行情中...</span></div>
      </div>
      <div class="tab-bar">
        <div class="tab ${this.activeTab === 'pnl' ? 'active' : ''}" onclick="Portfolio.switchTab('pnl')">实盘盈亏</div>
        <div class="tab ${this.activeTab === 'xray' ? 'active' : ''}" onclick="Portfolio.switchTab('xray')">实盘穿透</div>
      </div>
      <div id="tab-content"></div>
      <div class="footer-note" id="footer-note"></div>`;
  },

  _renderEmpty(app) {
    app.innerHTML = `
      <div class="portfolio-header">
        <span class="back-btn" onclick="Router.navigate('/')">&#8592; 知行录</span>
        <h2>我的持仓</h2>
        <div class="actions">
          <button class="btn btn-sm btn-gold" onclick="AddStock.showAdd()">+ 添加</button>
        </div>
      </div>
      <div class="empty-state">
        <p>还没有持仓记录<br>添加你的第一只股票，开始客观面对自己的投资组合</p>
        <button class="btn btn-primary" onclick="AddStock.showAdd()">添加持仓</button>
      </div>`;
  },

  switchTab(tab) {
    this.activeTab = tab;
    document.querySelectorAll('.tab-bar .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab-bar .tab:${tab === 'pnl' ? 'first' : 'last'}-child`).classList.add('active');
    this._renderTabContent();
  },

  async refreshQuotes() {
    const allStocks = Store.getStockList();
    if (!allStocks.length) return;
    const symbols = allStocks.map(s => s.code).join(',');
    try {
      const [quotesResp, profilesResp] = await Promise.all([
        fetch('/api/quotes?symbols=' + symbols),
        fetch('/api/stock-profiles?symbols=' + symbols)
      ]);
      this.quotes = await quotesResp.json();
      this.profiles = await profilesResp.json();
      this.lastUpdate = new Date();
      this._renderSummary();
      this._renderTabContent();
      this._renderFooter();
    } catch {
      const el = document.getElementById('summary-content');
      if (el) el.innerHTML = '<span class="text-secondary">行情加载失败，请稍后刷新</span>';
    }
  },

  _renderSummary() {
    const el = document.getElementById('summary-content');
    if (!el) return;
    const settings = Store.getSettings();
    const held = Store.getHeldStocks();
    let totalAsset = 0, totalCost = 0, totalDailyPnl = 0;
    held.forEach(s => {
      const q = this.quotes[s.code];
      if (!q) return;
      totalAsset += q.price * s.shares;
      totalCost += s.cost_price * s.shares;
      totalDailyPnl += (q.price - q.prev_close) * s.shares;
    });
    const totalPnl = totalAsset - totalCost;
    const dailyPct = totalAsset - totalDailyPnl > 0 ? (totalDailyPnl / (totalAsset - totalDailyPnl) * 100) : 0;
    const totalPct = totalCost > 0 ? (totalPnl / totalCost * 100) : 0;

    if (settings.hide_amount) {
      el.innerHTML = `
        <div class="total-asset">****</div>
        <div class="daily-pnl text-secondary">今日 ****</div>
        <div class="total-pnl text-secondary">总盈亏 ****</div>`;
      return;
    }
    el.innerHTML = `
      <div class="total-asset">¥${this._fmt(totalAsset)}</div>
      <div class="daily-pnl">今日 <span class="${totalDailyPnl >= 0 ? 'text-up' : 'text-down'}">${this._sign(totalDailyPnl)}¥${this._fmt(Math.abs(totalDailyPnl))}（${this._sign(dailyPct)}${Math.abs(dailyPct).toFixed(2)}%）</span></div>
      <div class="total-pnl">总盈亏 <span class="${totalPnl >= 0 ? 'text-up' : 'text-down'}">${this._sign(totalPnl)}¥${this._fmt(Math.abs(totalPnl))}（${this._sign(totalPct)}${Math.abs(totalPct).toFixed(2)}%）</span></div>`;
  },

  _renderTabContent() {
    const el = document.getElementById('tab-content');
    if (!el) return;
    if (this.activeTab === 'pnl') this._renderPnlView(el);
    else Charts.render(el, this.quotes);
  },

  _renderPnlView(el) {
    const settings = Store.getSettings();
    const sortBy = settings.sort_by || 'market_value';
    const held = Store.getHeldStocks().map(s => this._enrichStock(s)).sort((a, b) => this._sortFn(a, b, sortBy));
    const watched = Store.getWatchedStocks().map(s => this._enrichStock(s));

    const sortOpts = [
      { key: 'market_value', label: '持仓市值' },
      { key: 'daily_change', label: '今日涨跌' },
      { key: 'profit', label: '持仓盈亏' }
    ];

    let html = `<div class="sort-bar">${sortOpts.map(o =>
      `<span class="sort-option ${sortBy === o.key ? 'active' : ''}" onclick="Portfolio.setSort('${o.key}')">${o.label}${sortBy === o.key ? ' ▼' : ''}</span>`
    ).join('')}</div><div class="stock-list">`;

    held.forEach(s => { html += this._stockCard(s, settings.hide_amount); });
    if (watched.length) {
      html += '<div class="section-divider">── 关注中 ──</div>';
      watched.forEach(s => { html += this._stockCard(s, settings.hide_amount, true); });
    }
    html += '</div>';
    el.innerHTML = html;
  },

  _stockCard(s, hide, isWatch = false) {
    const pnlClass = s.dailyPnl >= 0 ? 'text-up' : 'text-down';
    const holdPnlClass = s.holdPnl >= 0 ? 'text-up' : 'text-down';
    return `
      <div class="stock-item card" onclick="Portfolio.toggleDetail('${s.code}')">
        <div class="stock-row">
          <div>
            <span class="stock-name">${s.name}</span>
            <span class="stock-code">${s.code}</span>
          </div>
          <div class="stock-price">
            <div class="mono">${hide ? '****' : '¥' + (s.price || 0).toFixed(2)}</div>
            <div class="${pnlClass}" style="font-size:13px;">${s.changePct >= 0 ? '+' : ''}${s.changePct.toFixed(2)}%</div>
          </div>
        </div>
        ${!isWatch ? `<div class="stock-metrics">
          <span>今日 <span class="${pnlClass}">${hide ? '****' : this._sign(s.dailyPnl) + '¥' + this._fmt(Math.abs(s.dailyPnl))}</span></span>
          <span>市值 ${hide ? '****' : '¥' + this._fmt(s.marketValue)}</span>
          <span>盈亏 <span class="${holdPnlClass}">${hide ? '****' : this._sign(s.holdPnl) + '¥' + this._fmt(Math.abs(s.holdPnl)) + '（' + this._sign(s.holdPct) + Math.abs(s.holdPct).toFixed(2) + '%）'}</span></span>
        </div>` : ''}
        <div class="stock-detail" id="detail-${s.code}">
          <div class="detail-grid">
            <div><span class="label">行业</span></div><div>${s.industry || '-'}</div>
            <div><span class="label">市值类型</span></div><div>${s.capType || '-'}</div>
            <div><span class="label">持仓数量</span></div><div>${s.shares}股</div>
            <div><span class="label">成本价</span></div><div class="mono">¥${(s.cost_price || 0).toFixed(2)}</div>
            <div><span class="label">买入日期</span></div><div>${s.buy_date || '-'}</div>
            <div><span class="label">备注</span></div><div>${s.note || '-'}</div>
          </div>
          <div class="detail-actions">
            <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();AddStock.showEdit('${s.code}')">修改持仓</button>
            <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();window.location.href='/api/report/${s.code}'">查看深度分析 →</button>
            <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();AddStock.showDelete('${s.code}')" style="margin-left:auto;">移除</button>
          </div>
        </div>
      </div>`;
  },

  _enrichStock(s) {
    const q = this.quotes[s.code] || {};
    const p = this.profiles[s.code] || {};
    const price = q.price || 0;
    const prevClose = q.prev_close || price;
    return {
      ...s,
      name: q.name || s.name,
      price,
      prevClose,
      changePct: q.change_pct || 0,
      dailyPnl: (price - prevClose) * (s.shares || 0),
      marketValue: price * (s.shares || 0),
      holdPnl: (price - (s.cost_price || 0)) * (s.shares || 0),
      holdPct: s.cost_price > 0 ? ((price - s.cost_price) / s.cost_price * 100) : 0,
      industry: p.industry || '',
      capType: p.cap_type || ''
    };
  },

  _sortFn(a, b, key) {
    if (key === 'daily_change') return b.changePct - a.changePct;
    if (key === 'profit') return b.holdPnl - a.holdPnl;
    return b.marketValue - a.marketValue;
  },

  setSort(key) {
    Store.updateSettings({ sort_by: key });
    this._renderTabContent();
  },

  toggleDetail(code) {
    const el = document.getElementById('detail-' + code);
    if (el) el.classList.toggle('open');
  },

  toggleHide() {
    const settings = Store.getSettings();
    Store.updateSettings({ hide_amount: !settings.hide_amount });
    const eyeEl = document.querySelector('.eye-toggle');
    if (eyeEl) eyeEl.innerHTML = !settings.hide_amount ? '&#9673;' : '&#9678;';
    this._renderSummary();
    this._renderTabContent();
  },

  _startAutoRefresh() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
    const now = new Date();
    const day = now.getDay();
    const h = now.getHours(), m = now.getMinutes();
    const isTrading = day >= 1 && day <= 5 && ((h === 9 && m >= 30) || (h > 9 && h < 15));
    if (isTrading) {
      this.refreshTimer = setInterval(() => this.refreshQuotes(), 5 * 60 * 1000);
    }
  },

  _renderFooter() {
    const el = document.getElementById('footer-note');
    if (!el) return;
    const timeStr = this.lastUpdate ? this.lastUpdate.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--:--';
    el.innerHTML = `最后更新：${timeStr}<br>持仓数据由用户手动录入，仅供个人记录和参考。价格数据来自公开市场，可能存在延迟。本功能不构成任何投资建议。`;
  },

  _fmt(n) { return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); },
  _sign(n) { return n >= 0 ? '+' : ''; }
};

const AddStock = {
  _searchTimer: null,

  showAdd() {
    this._renderModal('add', null);
  },

  showEdit(code) {
    const stock = Store.getStock(code);
    if (!stock) return;
    this._renderModal('edit', stock);
  },

  showDelete(code) {
    const stock = Store.getStock(code);
    if (!stock) return;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal confirm-dialog">
        <h3>确认移除</h3>
        <p>确定移除 <strong>${stock.name}（${stock.code}）</strong>？<br>历史盈亏数据将不再追踪。</p>
        <div class="btn-group">
          <button class="btn btn-secondary" id="cancel-delete">再想想</button>
          <button class="btn btn-danger" id="confirm-delete">确认移除</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#cancel-delete').onclick = () => overlay.remove();
    overlay.querySelector('#confirm-delete').onclick = () => {
      Store.removeStock(code);
      overlay.remove();
      Portfolio.render();
    };
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  },

  _renderModal(mode, stock) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    if (mode === 'add') {
      overlay.innerHTML = `
        <div class="modal">
          <h3>添加持仓</h3>
          <div id="add-step-search">
            <div class="search-in-modal">
              <input type="text" id="modal-search" placeholder="搜索股票代码或名称" autocomplete="off">
            </div>
            <div class="search-results" id="modal-results"></div>
          </div>
          <div id="add-step-form" style="display:none;"></div>
        </div>`;
    } else {
      overlay.innerHTML = `
        <div class="modal">
          <h3>修改持仓 · ${stock.name}</h3>
          <div id="add-step-form"></div>
        </div>`;
    }

    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

    if (mode === 'add') {
      const searchInput = overlay.querySelector('#modal-search');
      searchInput.focus();
      searchInput.addEventListener('input', () => {
        clearTimeout(this._searchTimer);
        const q = searchInput.value.trim();
        if (!q) { overlay.querySelector('#modal-results').innerHTML = ''; return; }
        this._searchTimer = setTimeout(() => this._doSearch(q, overlay), 200);
      });
    } else {
      this._renderForm(overlay, stock, 'edit');
    }
  },

  async _doSearch(q, overlay) {
    const results = overlay.querySelector('#modal-results');
    try {
      const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
      const data = await resp.json();
      if (!data.length) { results.innerHTML = '<p class="text-secondary text-sm" style="padding:12px;">未找到匹配的股票</p>'; return; }
      results.innerHTML = data.map(s => `
        <div class="search-result-item" data-code="${s.code}" data-name="${s.name}">
          <span style="font-weight:500;">${s.name}</span>
          <span class="mono text-secondary" style="font-size:13px;">${s.code}</span>
        </div>`).join('');
      results.querySelectorAll('.search-result-item').forEach(item => {
        item.onclick = () => {
          const code = item.dataset.code;
          const name = item.dataset.name;
          overlay.querySelector('#add-step-search').style.display = 'none';
          this._renderForm(overlay, { code, name, shares: 0, cost_price: 0, buy_date: new Date().toISOString().slice(0,10), note: '' }, 'add');
        };
      });
    } catch { results.innerHTML = '<p class="text-secondary text-sm" style="padding:12px;">搜索出错，请重试</p>'; }
  },

  _renderForm(overlay, stock, mode) {
    const formEl = overlay.querySelector('#add-step-form');
    formEl.style.display = 'block';
    const isWatch = mode === 'add';
    formEl.innerHTML = `
      <div style="margin-bottom:16px;padding:12px;background:var(--bg);border-radius:8px;">
        <span style="font-weight:500;">${stock.name}</span>
        <span class="mono text-secondary" style="font-size:13px;margin-left:6px;">${stock.code}</span>
      </div>
      <div class="form-group">
        <label>持仓数量（股）<span class="text-secondary" style="font-size:11px;margin-left:4px;">填0表示仅关注</span></label>
        <input type="number" id="input-shares" value="${stock.shares || ''}" placeholder="如 100、200" min="0" step="100">
        <div class="error-hint" id="shares-error">持仓数量需为100的整数倍</div>
      </div>
      <div class="form-group">
        <label>成本价（元/股）</label>
        <input type="number" id="input-cost" value="${stock.cost_price || ''}" placeholder="如 1680.50" min="0" step="0.01">
      </div>
      <div class="form-group">
        <label>买入日期</label>
        <input type="date" id="input-date" value="${stock.buy_date || new Date().toISOString().slice(0,10)}">
      </div>
      <div class="form-group">
        <label>备注 <span class="text-secondary" style="font-size:11px;">（选填，限100字）</span></label>
        <textarea id="input-note" rows="2" maxlength="100" placeholder="记录买入理由...">${stock.note || ''}</textarea>
      </div>
      <div style="display:flex;gap:12px;margin-top:20px;">
        <button class="btn btn-secondary" style="flex:1;" id="form-cancel">取消</button>
        <button class="btn btn-primary" style="flex:1;" id="form-submit">${mode === 'add' ? '确认添加' : '保存修改'}</button>
      </div>`;

    formEl.querySelector('#form-cancel').onclick = () => overlay.remove();
    formEl.querySelector('#form-submit').onclick = async () => {
      const shares = parseInt(formEl.querySelector('#input-shares').value) || 0;
      const cost = parseFloat(formEl.querySelector('#input-cost').value) || 0;
      const date = formEl.querySelector('#input-date').value;
      const note = formEl.querySelector('#input-note').value.trim();

      if (shares > 0 && shares % 100 !== 0) {
        const err = formEl.querySelector('#shares-error');
        err.style.display = 'block';
        return;
      }
      if (shares > 0 && cost <= 0) {
        alert('请输入成本价');
        return;
      }

      if (mode === 'add') {
        Store.addStock({ code: stock.code, name: stock.name, shares, cost_price: cost, buy_date: date, note });
      } else {
        Store.updateStock(stock.code, { shares, cost_price: cost, buy_date: date, note });
      }

      if (shares > 0 && cost > 0) {
        overlay.querySelector('.modal').innerHTML = `
          <div style="text-align:center;padding:24px 0;">
            <p class="text-secondary text-sm">正在获取最新行情，计算盈亏...</p>
          </div>`;
        try {
          const resp = await fetch('/api/quotes?symbols=' + stock.code);
          const quotes = await resp.json();
          const q = quotes[stock.code];
          if (q && q.price > 0) {
            const pnl = (q.price - cost) * shares;
            const pnlPct = ((q.price - cost) / cost * 100);
            const pnlClass = pnl >= 0 ? 'text-up' : 'text-down';
            const sign = pnl >= 0 ? '+' : '';
            overlay.querySelector('.modal').innerHTML = `
              <div style="text-align:center;padding:20px 0;">
                <h3 style="margin-bottom:16px;">${mode === 'add' ? '添加成功' : '修改成功'}</h3>
                <div style="margin-bottom:12px;">
                  <span style="font-weight:500;">${q.name || stock.name}</span>
                  <span class="mono text-secondary" style="font-size:13px;margin-left:6px;">${stock.code}</span>
                </div>
                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:4px;">当前价 ¥${q.price.toFixed(2)} · 成本价 ¥${cost.toFixed(2)}</div>
                <div style="font-size:22px;font-weight:600;margin:12px 0;" class="${pnlClass}">
                  ${sign}¥${Math.abs(pnl).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2})}
                </div>
                <div class="${pnlClass}" style="font-size:14px;">${sign}${Math.abs(pnlPct).toFixed(2)}%</div>
                <button class="btn btn-primary" style="margin-top:20px;min-width:120px;" onclick="this.closest('.modal-overlay').remove();Portfolio.render();">确定</button>
              </div>`;
            return;
          }
        } catch {}
      }
      overlay.remove();
      Portfolio.render();
    };
  }
};

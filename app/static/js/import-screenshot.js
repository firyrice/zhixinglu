const ImportScreenshot = {
  showImport() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal import-modal">
        <h3>截图导入持仓</h3>
        <div id="import-upload">
          <div class="upload-zone" id="upload-zone">
            <div class="upload-icon">&#128247;</div>
            <p>点击或拖拽上传持仓截图</p>
            <p class="text-secondary text-sm">支持 JPG / PNG，建议使用券商App完整持仓截图</p>
            <input type="file" id="screenshot-input" accept="image/*" style="display:none;">
          </div>
        </div>
        <div id="import-loading" style="display:none;">
          <div style="text-align:center;padding:40px 0;">
            <div class="import-spinner"></div>
            <p style="margin-top:16px;">AI 正在识别截图中的持仓数据...</p>
            <p class="text-secondary text-sm">通常需要 10-20 秒</p>
          </div>
        </div>
        <div id="import-results" style="display:none;"></div>
        <div id="import-error" style="display:none;"></div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });

    const zone = overlay.querySelector('#upload-zone');
    const input = overlay.querySelector('#screenshot-input');

    zone.onclick = () => input.click();
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files.length) this._handleFile(e.dataTransfer.files[0], overlay);
    });
    input.addEventListener('change', () => {
      if (input.files.length) this._handleFile(input.files[0], overlay);
    });
  },

  async _handleFile(file, overlay) {
    if (!file.type.startsWith('image/')) {
      alert('请上传图片文件');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('图片过大，请上传10MB以内的文件');
      return;
    }

    overlay.querySelector('#import-upload').style.display = 'none';
    overlay.querySelector('#import-loading').style.display = 'block';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch('/api/parse-screenshot', { method: 'POST', body: formData });
      const data = await resp.json();

      if (data.error) {
        this._showError(overlay, data.error);
        return;
      }
      if (!data.stocks || !data.stocks.length) {
        this._showError(overlay, '未能从截图中识别到持仓数据');
        return;
      }
      this._showResults(overlay, data.stocks);
    } catch (e) {
      this._showError(overlay, '请求失败，请检查网络后重试');
    }
  },

  _showError(overlay, msg) {
    overlay.querySelector('#import-loading').style.display = 'none';
    const el = overlay.querySelector('#import-error');
    el.style.display = 'block';
    el.innerHTML = `
      <div style="text-align:center;padding:24px 0;">
        <p style="color:var(--text-primary);margin-bottom:16px;">${msg}</p>
        <div style="display:flex;gap:12px;justify-content:center;">
          <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">关闭</button>
          <button class="btn btn-primary" onclick="this.closest('.modal-overlay').remove();ImportScreenshot.showImport();">重新上传</button>
        </div>
      </div>`;
  },

  _showResults(overlay, stocks) {
    overlay.querySelector('#import-loading').style.display = 'none';
    const el = overlay.querySelector('#import-results');
    el.style.display = 'block';

    const existingStocks = Store.getStocks();
    stocks.forEach((s, i) => {
      s._index = i;
      s._selected = true;
      s._exists = s.code && existingStocks[s.code];
      s._valid = s.code && s.shares > 0;
    });

    const validCount = stocks.filter(s => s._valid).length;
    const conflictCount = stocks.filter(s => s._exists).length;
    const noCodeCount = stocks.filter(s => !s.code).length;

    let html = `
      <div class="import-summary">
        <span>识别到 <strong>${stocks.length}</strong> 只股票</span>
        ${conflictCount > 0 ? `<span class="text-secondary">· ${conflictCount} 只已有持仓</span>` : ''}
        ${noCodeCount > 0 ? `<span class="text-secondary">· ${noCodeCount} 只未匹配代码</span>` : ''}
      </div>
      <div class="import-actions-top">
        <label style="font-size:13px;cursor:pointer;">
          <input type="checkbox" id="import-select-all" checked onchange="ImportScreenshot._toggleAll(this.checked)"> 全选
        </label>
      </div>
      <div class="import-list">`;

    stocks.forEach(s => {
      const pnlClass = (s.pnl || 0) >= 0 ? 'text-up' : 'text-down';
      const sign = (s.pnl || 0) >= 0 ? '+' : '';
      const statusTag = s._exists
        ? '<span class="import-tag tag-conflict">覆盖</span>'
        : s._valid
          ? '<span class="import-tag tag-new">新增</span>'
          : '<span class="import-tag tag-skip">跳过</span>';

      html += `
        <div class="import-item ${!s._valid ? 'import-item-disabled' : ''}" id="import-item-${s._index}">
          <label class="import-check">
            <input type="checkbox" ${s._selected && s._valid ? 'checked' : ''} ${!s._valid ? 'disabled' : ''}
              onchange="ImportScreenshot._toggleItem(${s._index}, this.checked)">
          </label>
          <div class="import-item-info">
            <div class="import-item-header">
              <span style="font-weight:500;">${s.name}</span>
              <span class="mono text-secondary" style="font-size:12px;margin-left:4px;">${s.code || '未匹配'}</span>
              ${statusTag}
            </div>
            <div class="import-item-detail">
              <span>${s.shares || 0}股</span>
              <span>成本 ¥${(s.cost_price || 0).toFixed(2)}</span>
              <span>市值 ¥${(s.market_value || 0).toLocaleString('zh-CN', {maximumFractionDigits: 0})}</span>
              <span class="${pnlClass}">${sign}¥${Math.abs(s.pnl || 0).toLocaleString('zh-CN', {maximumFractionDigits: 0})}</span>
            </div>
          </div>
        </div>`;
    });

    html += `</div>
      <div style="display:flex;gap:12px;margin-top:16px;">
        <button class="btn btn-secondary" style="flex:1;" onclick="this.closest('.modal-overlay').remove()">取消</button>
        <button class="btn btn-primary" style="flex:1;" id="import-confirm" onclick="ImportScreenshot._doImport()">
          确认导入 (${validCount})
        </button>
      </div>`;

    el.innerHTML = html;
    this._stocks = stocks;
  },

  _toggleAll(checked) {
    if (!this._stocks) return;
    this._stocks.forEach(s => {
      if (s._valid) {
        s._selected = checked;
        const cb = document.querySelector(`#import-item-${s._index} input[type=checkbox]`);
        if (cb) cb.checked = checked;
      }
    });
    this._updateConfirmBtn();
  },

  _toggleItem(index, checked) {
    if (!this._stocks) return;
    this._stocks[index]._selected = checked;
    this._updateConfirmBtn();
  },

  _updateConfirmBtn() {
    const count = this._stocks.filter(s => s._selected && s._valid).length;
    const btn = document.getElementById('import-confirm');
    if (btn) btn.textContent = `确认导入 (${count})`;
  },

  _doImport() {
    if (!this._stocks) return;
    const toImport = this._stocks.filter(s => s._selected && s._valid);
    if (!toImport.length) { alert('请至少选择一只股票'); return; }

    const existingStocks = Store.getStocks();
    let added = 0, updated = 0;

    toImport.forEach(s => {
      const data = {
        code: s.code,
        name: s.name,
        shares: s.shares,
        cost_price: s.cost_price || 0,
        buy_date: new Date().toISOString().slice(0, 10),
        note: '截图导入',
        market: s.market || 'A',
      };
      if (existingStocks[s.code]) {
        Store.updateStock(s.code, data);
        updated++;
      } else {
        Store.addStock(data);
        added++;
      }
    });

    const overlay = document.querySelector('.modal-overlay');
    if (overlay) {
      overlay.querySelector('.import-modal').innerHTML = `
        <div style="text-align:center;padding:32px 0;">
          <h3 style="margin-bottom:16px;">导入完成</h3>
          <p>新增 <strong>${added}</strong> 只，覆盖 <strong>${updated}</strong> 只</p>
          <button class="btn btn-primary" style="margin-top:20px;min-width:120px;"
            onclick="this.closest('.modal-overlay').remove();Portfolio.render();">确定</button>
        </div>`;
    }
  },

  _stocks: null,
};

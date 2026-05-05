const DIRECTION_LABELS = {buy: '买入', sell: '卖出', add: '加仓', reduce: '减仓'};

const Diagnosis = {
  _searchTimer: null,
  _selectedStock: null,
  _chatHistory: [],
  _currentDiagnosisId: null,

  renderForm(prefill) {
    const app = document.getElementById('app');
    const params = new URLSearchParams(location.hash.split('?')[1] || '');
    const preCode = prefill?.code || params.get('code') || '';
    const preName = prefill?.name || params.get('name') || '';
    const preMarket = prefill?.market || params.get('market') || 'A';

    app.innerHTML = `
      <div class="diagnosis-form">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/')">← 返回</span>
          <span style="color:var(--accent-gold);cursor:pointer;font-size:13px;" onclick="Router.navigate('/diagnosis/history')">诊断记录</span>
        </div>
        <h1>交易诊断</h1>
        <p class="subtitle">在执行交易前，让AI帮你做一次系统性检查</p>
        <div id="diag-holding-hint"></div>
        <div class="diag-form-group" style="position:relative;">
          <label>股票</label>
          <input type="text" id="diag-stock-input" placeholder="输入股票代码或名称" autocomplete="off">
          <div class="diag-search-results" id="diag-search-results"></div>
        </div>
        <div class="diag-form-group">
          <label>交易方向</label>
          <div class="diag-direction-group" id="diag-direction-group">
            <button class="diag-direction-btn buy" data-dir="buy" onclick="Diagnosis._setDirection('buy')">买入</button>
            <button class="diag-direction-btn sell" data-dir="sell" onclick="Diagnosis._setDirection('sell')">卖出</button>
            <button class="diag-direction-btn add" data-dir="add" onclick="Diagnosis._setDirection('add')">加仓</button>
            <button class="diag-direction-btn reduce" data-dir="reduce" onclick="Diagnosis._setDirection('reduce')">减仓</button>
          </div>
        </div>
        <div class="diag-form-group">
          <label>数量（股）</label>
          <input type="number" id="diag-shares" placeholder="100的整数倍" min="100" step="100">
        </div>
        <div class="diag-form-group">
          <label>目标价格（可选）</label>
          <input type="number" id="diag-price" placeholder="默认使用当前价" step="0.01">
        </div>
        <div class="diag-form-group">
          <label>你为什么想做这笔交易？（可选）</label>
          <textarea id="diag-reason" placeholder="简述你的交易理由，限200字" maxlength="200"></textarea>
        </div>
        <button class="diag-submit-btn" id="diag-submit" onclick="Diagnosis._submit()">开始诊断</button>
      </div>`;

    this._selectedStock = null;
    this._direction = 'buy';
    this._setDirection('buy');

    const input = document.getElementById('diag-stock-input');
    input.addEventListener('input', () => this._onSearchInput());
    input.addEventListener('focus', () => { if (input.value.length >= 1) this._onSearchInput(); });
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.diag-form-group')) {
        document.getElementById('diag-search-results').style.display = 'none';
      }
    });

    if (preCode && preName) {
      this._selectedStock = {code: preCode, name: preName, market: preMarket};
      input.value = `${preName} ${preCode}`;
      this._checkHolding(preCode);
    }
  },

  _setDirection(dir) {
    this._direction = dir;
    document.querySelectorAll('.diag-direction-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.dir === dir);
    });
  },

  _checkHolding(code) {
    const stock = Store.getStock(code);
    const hint = document.getElementById('diag-holding-hint');
    if (stock && stock.shares > 0) {
      hint.innerHTML = `<div class="diag-holding-hint">你当前持有 ${stock.name} ${stock.shares}股，成本价 ¥${stock.cost_price.toFixed(2)}</div>`;
      if (this._direction === 'buy') this._setDirection('add');
    } else {
      hint.innerHTML = '';
    }
  },

  _onSearchInput() {
    clearTimeout(this._searchTimer);
    const input = document.getElementById('diag-stock-input');
    const q = input.value.trim();
    if (q.length < 1) {
      document.getElementById('diag-search-results').style.display = 'none';
      return;
    }
    this._searchTimer = setTimeout(async () => {
      try {
        const resp = await fetch('/api/search?q=' + encodeURIComponent(q));
        const results = await resp.json();
        const container = document.getElementById('diag-search-results');
        if (!results.length) {
          container.style.display = 'none';
          return;
        }
        container.innerHTML = results.slice(0, 8).map(r =>
          `<div class="diag-search-item" onclick="Diagnosis._selectStock('${r.code}','${r.name}','${r.market || 'A'}')">${r.name} <span style="color:var(--text-secondary);font-size:12px;">${r.code}</span></div>`
        ).join('');
        container.style.display = 'block';
      } catch {}
    }, 300);
  },

  _selectStock(code, name, market) {
    this._selectedStock = {code, name, market};
    document.getElementById('diag-stock-input').value = `${name} ${code}`;
    document.getElementById('diag-search-results').style.display = 'none';
    this._checkHolding(code);
  },

  _submit() {
    if (!this._selectedStock) { alert('请选择股票'); return; }
    const shares = parseInt(document.getElementById('diag-shares').value);
    if (!shares || shares <= 0) { alert('请输入交易数量'); return; }
    if (shares % 100 !== 0) { alert('数量必须为100的整数倍'); return; }

    const direction = this._direction;
    if ((direction === 'sell' || direction === 'reduce') && this._selectedStock) {
      const held = Store.getStock(this._selectedStock.code);
      if (held && shares > held.shares) {
        alert(`卖出数量不能超过持仓数量（${held.shares}股）`);
        return;
      }
    }

    const priceVal = document.getElementById('diag-price').value;
    const reason = document.getElementById('diag-reason').value.trim();

    const tradeIntent = {
      code: this._selectedStock.code,
      name: this._selectedStock.name,
      market: this._selectedStock.market || 'A',
      direction, shares,
      target_price: priceVal ? parseFloat(priceVal) : null,
      reason: reason || null,
    };

    sessionStorage.setItem('diag_trade_intent', JSON.stringify(tradeIntent));
    Router.navigate('/diagnosis/generate');
  },

  async renderGenerating() {
    const app = document.getElementById('app');
    const raw = sessionStorage.getItem('diag_trade_intent');
    if (!raw) { Router.navigate('/diagnosis'); return; }
    const tradeIntent = JSON.parse(raw);
    const holdings = Store.getHeldStocks().map(s => ({
      code: s.code, name: s.name, shares: s.shares,
      cost_price: s.cost_price, market: s.market || 'A'
    }));

    const dirLabel = DIRECTION_LABELS[tradeIntent.direction] || '买入';

    const STEPS = [
      {id: 'loading_report', label: '加载分析报告'},
      {id: 'fetching_data', label: '获取市场数据'},
      {id: 'value', label: '价值诊断'},
      {id: 'position', label: '仓位诊断'},
      {id: 'timing', label: '择时诊断'},
      {id: 'market', label: '市场诊断'},
      {id: 'sector', label: '板块环境'},
      {id: 'conclusion', label: '综合判断'},
    ];

    app.innerHTML = `
      <div style="max-width:720px;margin:0 auto;padding:20px 16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/diagnosis')">← 返回</span>
        </div>
        <div id="diag-progress" class="diag-progress">
          <div class="diag-progress-title">交易诊断生成中</div>
          <div class="diag-progress-subtitle">${dirLabel} ${tradeIntent.name} ${tradeIntent.shares}股</div>
          <div class="diag-progress-steps" id="diag-progress-steps">
            ${STEPS.map(s => `<div class="diag-step pending" id="diag-step-${s.id}"><span class="diag-step-icon">○</span><span>${s.label}</span></div>`).join('')}
          </div>
        </div>
        <div id="diag-report-content" style="display:none;"></div>
        <div id="diag-chat-container" style="display:none;">
          <div class="diag-chat-area">
            <h3>对这个诊断有疑问？继续问我</h3>
            <div id="diag-hints"></div>
            <div class="diag-chat-messages" id="diag-chat-messages"></div>
            <div class="diag-chat-input-row">
              <input type="text" class="diag-chat-input" id="diag-chat-input" placeholder="输入你的问题..." onkeydown="if(event.key==='Enter')Diagnosis._sendChat()">
              <button class="diag-chat-send" onclick="Diagnosis._sendChat()">发送</button>
            </div>
          </div>
        </div>
      </div>`;

    this._chatHistory = [];
    this._currentDiagnosisId = null;
    this._hints = [];
    let firstCardShown = false;

    const updateProgress = (stepId) => {
      STEPS.forEach(s => {
        const el = document.getElementById(`diag-step-${s.id}`);
        if (!el) return;
        const idx = STEPS.findIndex(x => x.id === stepId);
        const myIdx = STEPS.findIndex(x => x.id === s.id);
        if (myIdx < idx) {
          el.className = 'diag-step completed';
          el.querySelector('.diag-step-icon').textContent = '✓';
        } else if (myIdx === idx) {
          el.className = 'diag-step active';
          el.querySelector('.diag-step-icon').innerHTML = '<span class="diag-spinner"></span>';
        }
      });
    };

    try {
      const resp = await fetch('/api/diagnosis/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({trade_intent: tradeIntent, holdings})
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let html = '';
      const contentEl = document.getElementById('diag-report-content');
      const progressEl = document.getElementById('diag-progress');

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, {stream: true});
        html += chunk;

        // Parse progress markers
        const progressMatch = chunk.match(/<!-- PROGRESS:(\w+) -->/g);
        if (progressMatch) {
          progressMatch.forEach(m => {
            const id = m.match(/PROGRESS:(\w+)/)[1];
            updateProgress(id);
          });
        }

        // Parse hints marker
        const hintsMatch = html.match(/<!-- HINTS:(.*?) -->/);
        if (hintsMatch) {
          try { this._hints = JSON.parse(hintsMatch[1]); } catch {}
        }

        // Show content (strip progress/hints markers for display)
        const displayHtml = html.replace(/<!-- PROGRESS:\w+ -->/g, '').replace(/<!-- HINTS:.*? -->/g, '');
        if (displayHtml.includes('diag-card') && !firstCardShown) {
          firstCardShown = true;
          progressEl.classList.add('diag-progress-collapsed');
          contentEl.style.display = 'block';
        }
        contentEl.innerHTML = displayHtml;
      }

      // All done
      progressEl.style.display = 'none';
      contentEl.style.display = 'block';
      document.getElementById('diag-chat-container').style.display = 'block';

      // Render hints
      if (this._hints.length > 0) {
        this._renderHints();
      }

      const histResp = await fetch('/api/diagnosis/history');
      const histData = await histResp.json();
      if (histData.length > 0) {
        this._currentDiagnosisId = histData[0].id;
      }
    } catch (e) {
      document.getElementById('diag-progress').style.display = 'none';
      document.getElementById('diag-report-content').style.display = 'block';
      document.getElementById('diag-report-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">诊断生成失败，请重试</p>';
    }
  },

  _renderHints() {
    const container = document.getElementById('diag-hints');
    if (!container || !this._hints.length) return;
    container.innerHTML = `
      <div class="diag-hints-wrapper">
        <div class="diag-hints-label">你可能想问：</div>
        ${this._hints.map(q => `<div class="diag-hint-item" onclick="Diagnosis._clickHint(this, '${q.replace(/'/g, "\\'")}')">${q}</div>`).join('')}
      </div>`;
  },

  _clickHint(el, question) {
    document.getElementById('diag-hints').style.display = 'none';
    document.getElementById('diag-chat-input').value = question;
    this._sendChat();
  },

  async _sendChat() {
    const input = document.getElementById('diag-chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    const msgsEl = document.getElementById('diag-chat-messages');
    msgsEl.innerHTML += `<div class="diag-chat-msg user">${msg}</div>`;
    msgsEl.innerHTML += `<div class="diag-chat-msg assistant" id="diag-chat-typing">思考中...</div>`;
    msgsEl.scrollTop = msgsEl.scrollHeight;

    try {
      const resp = await fetch('/api/diagnosis/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          diagnosis_id: this._currentDiagnosisId,
          message: msg,
          history: this._chatHistory,
        })
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let reply = '';
      const typingEl = document.getElementById('diag-chat-typing');

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        reply += decoder.decode(value, {stream: true});
        typingEl.textContent = reply;
      }

      typingEl.removeAttribute('id');
      this._chatHistory.push({role: 'user', content: msg});
      this._chatHistory.push({role: 'assistant', content: reply});
      msgsEl.scrollTop = msgsEl.scrollHeight;
    } catch {
      const typingEl = document.getElementById('diag-chat-typing');
      if (typingEl) typingEl.textContent = '回答失败，请重试';
    }
  },

  async renderDetail(id) {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div style="max-width:720px;margin:0 auto;padding:20px 16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/diagnosis/history')">← 返回</span>
        </div>
        <div id="diag-report-content"><p class="text-secondary text-sm">加载中...</p></div>
        <div id="diag-chat-container" style="display:none;">
          <div class="diag-chat-area">
            <h3>继续追问</h3>
            <div class="diag-chat-messages" id="diag-chat-messages"></div>
            <div class="diag-chat-input-row">
              <input type="text" class="diag-chat-input" id="diag-chat-input" placeholder="输入你的问题..." onkeydown="if(event.key==='Enter')Diagnosis._sendChat()">
              <button class="diag-chat-send" onclick="Diagnosis._sendChat()">发送</button>
            </div>
          </div>
        </div>
      </div>`;

    try {
      const resp = await fetch('/api/diagnosis/' + id);
      if (!resp.ok) throw new Error('not found');
      const data = await resp.json();

      document.getElementById('diag-report-content').innerHTML = data.content;
      document.getElementById('diag-chat-container').style.display = 'block';
      this._currentDiagnosisId = data.id;
      this._chatHistory = data.chat_history ? JSON.parse(data.chat_history) : [];

      const msgsEl = document.getElementById('diag-chat-messages');
      this._chatHistory.forEach(h => {
        msgsEl.innerHTML += `<div class="diag-chat-msg ${h.role}">${h.content}</div>`;
      });
    } catch {
      document.getElementById('diag-report-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">诊断记录不存在</p>';
    }
  },

  async renderHistory() {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div class="diag-history-list">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/')">← 返回</span>
        </div>
        <h1 style="font-family:var(--font-serif);font-size:22px;color:var(--accent-green);margin-bottom:20px;">诊断记录</h1>
        <div id="diag-history-items"><p class="text-secondary text-sm">加载中...</p></div>
      </div>`;

    try {
      const resp = await fetch('/api/diagnosis/history');
      const records = await resp.json();
      const container = document.getElementById('diag-history-items');

      if (!records.length) {
        container.innerHTML = '<p class="text-secondary" style="text-align:center;margin-top:40px;">暂无诊断记录</p>';
        return;
      }

      container.innerHTML = records.map(r => {
        const dirCls = (r.direction === 'buy' || r.direction === 'add') ? 'buy' : 'sell';
        const dirLabel = DIRECTION_LABELS[r.direction] || r.direction;
        return `<div class="diag-history-card" onclick="Router.navigate('/diagnosis/${r.id}')">
          <div class="diag-history-info">
            <div class="diag-history-title"><span class="diag-dir-tag ${dirCls}">${dirLabel}</span>${r.stock_name} ${r.shares}股</div>
            <div class="diag-history-summary">${r.summary || ''}</div>
          </div>
          <span class="diag-history-date">${r.date}</span>
          <button class="diag-history-delete" onclick="event.stopPropagation();Diagnosis._deleteRecord(${r.id})">删除</button>
        </div>`;
      }).join('');
    } catch {
      document.getElementById('diag-history-items').innerHTML =
        '<p class="text-secondary" style="text-align:center;">加载失败</p>';
    }
  },

  async _deleteRecord(id) {
    if (!confirm('确定删除这条诊断记录？')) return;
    await fetch('/api/diagnosis/' + id, {method: 'DELETE'});
    this.renderHistory();
  },
};

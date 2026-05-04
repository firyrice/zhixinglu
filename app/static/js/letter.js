const Letter = {
  async render(id) {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div style="max-width:720px;margin:0 auto;padding:20px 16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
          <span style="color:var(--accent-gold);cursor:pointer;font-size:14px;" onclick="Router.navigate('/')">← 返回</span>
          <span class="text-secondary text-sm" id="letter-date"></span>
        </div>
        <div id="letter-content"><p class="text-secondary text-sm">加载中...</p></div>
      </div>`;

    if (id === 'generate') {
      this._generate();
    } else {
      this._loadExisting(id);
    }
  },

  _renderMarkdown() {
    if (typeof marked === 'undefined') return;
    const renderer = new marked.Renderer();
    renderer.link = function(href, title, text) {
      if (typeof href === 'object') { text = href.text; title = href.title; href = href.href; }
      var t = title ? ' title="' + title + '"' : '';
      return '<a href="' + href + '" target="_blank" rel="noopener"' + t + '>' + text + '</a>';
    };
    marked.setOptions({ breaks: true, gfm: true, renderer: renderer });
    document.querySelectorAll('#letter-content .md-text').forEach(function(el) {
      el.innerHTML = marked.parse(el.textContent);
    });
  },

  async _generate() {
    const holdings = Store.getHeldStocks();
    if (!holdings.length) {
      document.getElementById('letter-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">请先在持仓页添加股票</p>';
      return;
    }

    const payload = holdings.map(s => ({
      code: s.code, name: s.name, shares: s.shares,
      cost_price: s.cost_price, market: s.market || 'A'
    }));

    document.getElementById('letter-date').textContent = '正在撰写...';
    const contentEl = document.getElementById('letter-content');
    contentEl.innerHTML = `
      <div style="text-align:center;padding:40px 0;">
        <p class="text-secondary" style="margin-bottom:12px;">巴菲特正在为你撰写今日来信...</p>
        <div style="width:200px;height:3px;background:var(--border);border-radius:2px;margin:0 auto;overflow:hidden;">
          <div style="width:30%;height:100%;background:var(--accent-gold);border-radius:2px;animation:progress 2s ease-in-out infinite;"></div>
        </div>
      </div>`;

    try {
      const resp = await fetch('/api/letter/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings: payload })
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let html = '';
      let firstChunk = true;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        html += decoder.decode(value, { stream: true });
        if (firstChunk) {
          contentEl.innerHTML = html;
          firstChunk = false;
        } else {
          contentEl.innerHTML = html;
        }
      }

      document.getElementById('letter-date').textContent =
        new Date().toLocaleDateString('zh-CN');
      this._renderMarkdown();
    } catch (e) {
      contentEl.innerHTML = '<p class="text-secondary" style="text-align:center;margin-top:60px;">生成失败，请重试</p>';
    }
  },

  async _loadExisting(id) {
    try {
      const resp = await fetch('/api/letter/' + id);
      if (!resp.ok) throw new Error('not found');
      const data = await resp.json();

      document.getElementById('letter-date').textContent = data.date;
      document.getElementById('letter-content').innerHTML = data.content;
      this._renderMarkdown();

      if (!data.is_read) {
        fetch('/api/letter/' + id + '/read', { method: 'PUT' });
      }
    } catch {
      document.getElementById('letter-content').innerHTML =
        '<p class="text-secondary" style="text-align:center;margin-top:60px;">来信不存在</p>';
    }
  }
};

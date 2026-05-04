const Mailbox = {
  async render() {
    const app = document.getElementById('app');
    app.innerHTML = `
      <div style="max-width:600px;margin:0 auto;padding:40px 24px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
          <div>
            <h1 class="serif" style="font-size:20px;color:var(--accent-green);margin:0;">信箱</h1>
            <p class="text-secondary text-sm" id="mailbox-stats"></p>
          </div>
          <span style="color:var(--accent-gold);cursor:pointer;font-size:13px;" onclick="Router.navigate('/')">← 返回首页</span>
        </div>
        <div id="mailbox-list"><p class="text-secondary text-sm">加载中...</p></div>
      </div>`;
    this._loadList();
  },

  async _loadList() {
    try {
      const resp = await fetch('/api/letters');
      const letters = await resp.json();
      const listEl = document.getElementById('mailbox-list');
      const statsEl = document.getElementById('mailbox-stats');

      if (!letters.length) {
        listEl.innerHTML = '<p class="text-secondary" style="text-align:center;margin-top:60px;">还没有来信</p>';
        statsEl.textContent = '';
        return;
      }

      const unread = letters.filter(l => !l.is_read).length;
      statsEl.textContent = `共 ${letters.length} 封 · ${unread} 封未读`;

      listEl.innerHTML = letters.map(l => {
        const isUnread = !l.is_read;
        const retPct = l.daily_return != null ? (l.daily_return >= 0 ? '+' : '') + l.daily_return.toFixed(2) + '%' : '';
        const retCls = l.daily_return >= 0 ? 'text-up' : 'text-down';
        return `
          <div style="background:#fff;border-radius:${isUnread ? '10' : '8'}px;padding:${isUnread ? '18px 20px' : '14px 16px'};margin-bottom:${isUnread ? '10' : '8'}px;
            box-shadow:0 ${isUnread ? '2px 8px' : '1px 3px'} rgba(0,0,0,${isUnread ? '0.06' : '0.04'});
            cursor:pointer;${isUnread ? 'border-left:4px solid var(--accent-gold);' : 'opacity:0.85;'}
            display:flex;align-items:flex-start;justify-content:space-between;transition:box-shadow 0.2s;"
            onmouseover="this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)'"
            onmouseout="this.style.boxShadow='0 ${isUnread ? '2px 8px' : '1px 3px'} rgba(0,0,0,${isUnread ? '0.06' : '0.04'})'"
            onclick="Router.navigate('/letter/${l.id}')">
            <div style="flex:1;min-width:0;">
              <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                ${isUnread ? '<div style="width:6px;height:6px;background:var(--accent-gold);border-radius:50%;"></div>' : ''}
                <span style="font-size:${isUnread ? '15' : '14'}px;${isUnread ? 'font-weight:bold;' : ''}color:var(--accent-green);font-family:var(--font-serif);">致我的合伙人</span>
                ${isUnread ? '<span style="font-size:10px;color:var(--accent-gold);background:#faf3e6;padding:1px 4px;border-radius:2px;">未读</span>' : ''}
              </div>
              <div class="text-secondary" style="font-size:12px;line-height:1.4;margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                ${l.summary || ''}
              </div>
              <div style="display:flex;gap:8px;font-size:11px;color:#999;">
                <span>${l.date}</span>
                <span>·</span>
                <span>${l.stock_count || 0}只持仓股</span>
                ${retPct ? `<span>·</span><span class="${retCls}">${retPct}</span>` : ''}
              </div>
            </div>
            <button onclick="event.stopPropagation();Mailbox.deleteLetter(${l.id})" title="删除"
              style="border:none;background:none;cursor:pointer;padding:6px;opacity:0.3;transition:opacity 0.2s;margin-left:8px;"
              onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='0.3'">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D97757" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>`;
      }).join('');
    } catch {
      document.getElementById('mailbox-list').innerHTML = '<p class="text-secondary">加载失败</p>';
    }
  },

  async deleteLetter(id) {
    if (!confirm('确定删除这封来信？')) return;
    await fetch('/api/letter/' + id, { method: 'DELETE' });
    this._loadList();
  }
};

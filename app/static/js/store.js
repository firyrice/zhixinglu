const STORAGE_KEY = 'zhixinglu_portfolio';
const QUOTE_CACHE_KEY = 'zhixinglu_quote_cache';
const QUOTE_CACHE_TTL = 60 * 60 * 1000;

const Store = {
  _data: null,

  _load() {
    if (this._data) return this._data;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      this._data = raw ? JSON.parse(raw) : { version: 1, stocks: {}, settings: { sort_by: 'market_value', hide_amount: false } };
    } catch {
      this._data = { version: 1, stocks: {}, settings: { sort_by: 'market_value', hide_amount: false } };
    }
    return this._data;
  },

  _save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this._data));
  },

  getStocks() {
    return this._load().stocks;
  },

  getStockList() {
    return Object.values(this._load().stocks);
  },

  getStock(code) {
    return this._load().stocks[code] || null;
  },

  addStock({ code, name, shares, cost_price, buy_date, note, market }) {
    const data = this._load();
    const existing = data.stocks[code];
    if (existing && existing.shares > 0 && shares > 0) {
      const totalShares = existing.shares + shares;
      existing.cost_price = (existing.shares * existing.cost_price + shares * cost_price) / totalShares;
      existing.shares = totalShares;
      existing.note = note || existing.note;
      existing.updated_at = new Date().toISOString();
    } else {
      data.stocks[code] = {
        code, name, shares: shares || 0,
        cost_price: cost_price || 0,
        buy_date: buy_date || new Date().toISOString().slice(0, 10),
        note: note || '',
        market: market || 'A',
        added_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
    }
    this._save();
  },

  updateStock(code, updates) {
    const data = this._load();
    if (!data.stocks[code]) return;
    Object.assign(data.stocks[code], updates, { updated_at: new Date().toISOString() });
    this._save();
  },

  removeStock(code) {
    const data = this._load();
    delete data.stocks[code];
    this._save();
  },

  getSettings() {
    return this._load().settings;
  },

  updateSettings(updates) {
    const data = this._load();
    Object.assign(data.settings, updates);
    this._save();
  },

  hasStocks() {
    return Object.keys(this._load().stocks).length > 0;
  },

  getHeldStocks() {
    return this.getStockList().filter(s => s.shares > 0);
  },

  getWatchedStocks() {
    return this.getStockList().filter(s => s.shares === 0);
  },

  getSymbolsByMarket() {
    const groups = {};
    this.getStockList().forEach(s => {
      const m = s.market || 'A';
      if (!groups[m]) groups[m] = [];
      groups[m].push(s.code);
    });
    return groups;
  },

  getQuoteCache() {
    try {
      const raw = localStorage.getItem(QUOTE_CACHE_KEY);
      if (!raw) return null;
      const cache = JSON.parse(raw);
      if (Date.now() - cache.ts > QUOTE_CACHE_TTL) return null;
      return cache;
    } catch { return null; }
  },

  setQuoteCache(quotes, profiles) {
    localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify({ quotes, profiles, ts: Date.now() }));
  },

  clearQuoteCache() {
    localStorage.removeItem(QUOTE_CACHE_KEY);
  }
};

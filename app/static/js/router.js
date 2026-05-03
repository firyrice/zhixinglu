const Router = {
  routes: {},
  currentRoute: null,

  register(path, handler) {
    this.routes[path] = handler;
  },

  start() {
    window.addEventListener('hashchange', () => this._resolve());
    this._resolve();
  },

  navigate(path) {
    window.location.hash = '#' + path;
  },

  _resolve() {
    const hash = window.location.hash.slice(1) || '/';
    const path = hash.split('?')[0];
    this.currentRoute = path;
    const handler = this.routes[path] || this.routes['/'];
    if (handler) handler();
  }
};

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
    let handler = this.routes[path];
    if (!handler) {
      const sorted = Object.keys(this.routes).sort((a, b) => b.length - a.length);
      for (const route of sorted) {
        if (route !== '/' && path.startsWith(route + '/')) {
          handler = this.routes[route];
          break;
        }
      }
    }
    handler = handler || this.routes['/'];
    if (handler) handler();
  }
};

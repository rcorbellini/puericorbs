// A entrada da página: descobre que site é este (qual consultório o endereço abre), quem está entrando e com que
// papel, e entrega a tela certa: a plataforma, o site público do consultório, a equipe ou a família.
import { api, html, icon, fail, dialog } from './lib.js';
import * as site from './site.js';
import * as staff from './staff.js';
import * as family from './family.js';

const THEME_KEY = 'pc-theme';

export const app = {
  site: null,
  me: null,
  get today() { return this.site?.today; },
  async reload() { location.reload(); },
  async logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (e) { fail(e); }
    location.hash = '';
    location.reload();
  },
  async switchSite(slug) {
    try { await api('/api/demo/site', { method: 'POST', body: { slug } }); } catch (e) { fail(e); return; }
    location.hash = '';
    location.reload();
  },
  theme() { try { return localStorage.getItem(THEME_KEY) || 'claro'; } catch { return 'claro'; } },
  setTheme(value) {
    try { localStorage.setItem(THEME_KEY, value); } catch { /* sem armazenamento: vale só agora */ }
    applyTheme(value);
  },
};

function applyTheme(value = app.theme()) {
  const root = document.documentElement;
  if (value === 'escuro') root.dataset.theme = 'dark';
  else if (value === 'auto') delete root.dataset.theme;
  else root.dataset.theme = 'light';
}

function addBackground() {
  const veil = document.createElement('div');
  veil.className = 'veil';
  veil.setAttribute('aria-hidden', 'true');
  const bubbles = document.createElement('div');
  bubbles.className = 'bubbles';
  bubbles.setAttribute('aria-hidden', 'true');
  bubbles.innerHTML = [
    'width:320px;height:320px;left:-120px;top:22vh;animation-duration:17s',
    'width:150px;height:150px;right:7vw;top:-40px;animation-duration:13s;animation-delay:-5s',
    'width:250px;height:250px;right:-90px;top:52vh;animation-duration:18s;animation-delay:-3s',
    'width:110px;height:110px;left:38vw;bottom:-36px;animation-duration:15s;animation-delay:-9s',
    'width:80px;height:80px;left:12vw;top:70vh;animation-duration:14s;animation-delay:-11s',
  ].map((s) => `<i class="bub" style="${s}"></i>`).join('');
  document.body.prepend(veil, bubbles);
}

function demoBar() {
  const s = app.site;
  if (!s.demo || s.kind !== 'practice') return;
  const bar = document.createElement('button');
  bar.className = 'demobar';
  bar.type = 'button';
  const domain = (s.domains && s.domains[0]) || s.host;
  bar.innerHTML = String(html`${icon('globe')}<span class="lbl"><b>Demonstração</b></span>`);
  bar.setAttribute('aria-label', `Demonstração: ${domain}`);
  bar.addEventListener('click', () => {
    const d = dialog({
      title: 'Demonstração',
      body: html`<p class="muted pretty">Você está no site de <b>${domain}</b>${s.simulated ? ', aberto pelo endereço da plataforma' : ''}. Tudo aqui é fictício.</p>
        <div class="opts">
          ${app.me ? html`<button class="opt" type="button" data-demo="person" style="min-height:56px">${icon('users')}<span class="grow"><b>Trocar de pessoa</b><span class="t-small muted" style="display:block">entrar como a pediatra, a recepção ou outra família</span></span></button>` : ''}
          <button class="opt" type="button" data-demo="site" style="min-height:56px">${icon('globe')}<span class="grow"><b>Outro consultório</b><span class="t-small muted" style="display:block">voltar à página da plataforma</span></span></button>
        </div>`,
    });
    d.el.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-demo]');
      if (!b) return;
      if (b.dataset.demo === 'person') app.logout();
      else if (s.simulated) app.switchSite(null);
      else location.href = `${location.protocol}//${location.host.replace(/^[^.]+\./, '')}/`;
    });
  });
  document.body.append(bar);
}

function route() {
  const s = app.site;
  if (s.kind === 'platform') return site.platform(app);
  if (s.kind === 'unknown') return site.unknown(app);
  if (location.hash.startsWith('#/convite/')) return site.invite(app);
  if (!app.me || !app.me.role) return site.publicSite(app);
  if (app.me.role === 'guardian') return family.route(app);
  return staff.route(app);
}

async function boot() {
  applyTheme();
  addBackground();
  const root = document.getElementById('app');
  try {
    app.site = await api('/api/site');
  } catch (e) {
    root.innerHTML = String(html`<div class="platform"><div class="glass error-box"><h1 class="t-title">Não deu para abrir</h1><p class="muted">${e.message}</p><button class="btn" type="button" onclick="location.reload()">Tentar de novo</button></div></div>`);
    return;
  }
  app.me = app.site.me;
  if (app.site.practice) {
    document.documentElement.dataset.accent = app.site.practice.accent;
    document.title = app.me ? `${app.site.practice.name} · Puericorbs` : app.site.practice.name;
  }
  demoBar();
  window.addEventListener('hashchange', route);
  route();
}

boot();

// A casca da equipe: a barra lateral (o pediatra vê tudo da prática; a atendente, a agenda, o cadastro e o dinheiro)
// e o roteador das telas.
import { html, icon, initials, fail } from './lib.js';
import * as day from './staff-day.js';
import * as people from './staff-patients.js';
import * as admin from './staff-admin.js';

const CLINICIAN = [
  ['hoje', 'Hoje', 'sun'], ['agenda', 'Agenda', 'calendar'], ['pacientes', 'Pacientes', 'users'], ['revisar', 'Revisar', 'inbox'],
  'sep', ['recepcao', 'Recepção', 'phone'], ['financeiro', 'Financeiro', 'card'], ['servicos', 'Serviços', 'sliders'], ['planos', 'Planos', 'repeat'],
];
const RECEPTION = [['recepcao', 'Recepção', 'home'], ['agenda', 'Agenda', 'calendar'], ['pacientes', 'Famílias', 'users'], ['planos', 'Planos', 'repeat']];
const VIEWS = {
  hoje: day.today, agenda: day.agenda, recepcao: day.reception,
  pacientes: people.patients, paciente: people.patient, consulta: people.encounter, revisar: people.review,
  servicos: admin.services, planos: admin.plans, financeiro: admin.finance,
};
const CLINICIAN_ONLY = new Set(['hoje', 'consulta', 'revisar', 'servicos', 'financeiro']);

function parse() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  const [name, id] = path.split('/');
  return { name: name || '', id: id ? Number(id) : null, query: Object.fromEntries(new URLSearchParams(query)) };
}

function shell(app) {
  const items = app.me.role === 'clinician' ? CLINICIAN : RECEPTION;
  const root = document.getElementById('app');
  const theme = app.theme();
  root.innerHTML = String(html`
    <div class="shell" id="shell">
      <aside class="side glass">
        <a class="brand" href="#/"><span class="logo"></span><span><span class="wordmark">puericorbs</span><span class="practice">${app.site.practice.name}</span></span></a>
        <nav class="nav" aria-label="Seções">
          ${items.map((it) => it === 'sep' ? html`<span class="navsep" aria-hidden="true"></span>`
            : html`<a href="#/${it[0]}" data-nav="${it[0]}">${icon(it[2])}${it[1]}${it[0] === 'revisar' ? html`<span class="count" data-count="revisar" hidden></span>` : ''}</a>`)}
        </nav>
        <div class="who">
          <span class="av sm">${initials(app.me.name)}</span>
          <div class="grow"><b>${app.me.name}</b><span class="t-small muted">${app.me.role_label}</span></div>
          <span class="who-btns"><button class="iconbtn small" type="button" data-shell="theme" aria-label="Tema: ${theme}" title="Tema: ${theme}">${icon(theme === 'escuro' ? 'moon' : 'sun')}</button>
          <button class="iconbtn small" type="button" data-shell="logout" aria-label="Sair" title="Sair">${icon('logout')}</button></span>
        </div>
      </aside>
      <main class="main" id="view"></main>
    </div>`);
  root.querySelector('.who').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-shell]');
    if (!b) return;
    if (b.dataset.shell === 'logout') app.logout();
    if (b.dataset.shell === 'theme') {
      const next = { claro: 'escuro', escuro: 'auto', auto: 'claro' }[app.theme()];
      app.setTheme(next);
      b.innerHTML = String(icon(next === 'escuro' ? 'moon' : 'sun'));
      b.setAttribute('aria-label', `Tema: ${next}`);
      b.title = `Tema: ${next}`;
    }
  });
}

export function setCount(name, n) {
  const el = document.querySelector(`[data-count="${name}"]`);
  if (!el) return;
  el.hidden = !n;
  el.textContent = n || '';
}

let current = null;

// redesenha a tela atual sem voltar ao topo (depois de uma ação)
export function refresh() { if (current) route(current, { keep: true }); }

export async function route(app, opts = {}) {
  current = app;
  if (!document.getElementById('shell')) shell(app);
  let { name, id, query } = parse();
  const home = app.me.role === 'clinician' ? 'hoje' : 'recepcao';
  if (!name || !VIEWS[name] || (CLINICIAN_ONLY.has(name) && app.me.role !== 'clinician')) {
    if (name && name !== home) history.replaceState(null, '', `#/${home}`);
    name = home;
  }
  const navKey = { paciente: 'pacientes', consulta: app.me.role === 'clinician' ? 'hoje' : 'agenda' }[name] || name;
  document.querySelectorAll('[data-nav]').forEach((a) => {
    if (a.dataset.nav === navKey) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  const old = document.getElementById('view');
  const view = old.cloneNode(false);
  let slow = null;
  if (!opts.keep) {
    old.replaceWith(view);
    slow = setTimeout(() => { view.innerHTML = '<div class="loading">Carregando…</div>'; }, 250);
  }
  try {
    await VIEWS[name](view, { id, query }, app);
    if (opts.keep) document.getElementById('view').replaceWith(view);
  } catch (e) {
    if (opts.keep) { fail(e); return; }
    if (e.status === 401) { location.reload(); return; }
    view.innerHTML = String(html`<div class="glass error-box"><h1 class="t-h2">Não deu para abrir esta tela</h1><p class="muted">${e.message}</p><button class="btn ghost" type="button" onclick="location.reload()">Tentar de novo</button></div>`);
    fail(e);
  } finally {
    clearTimeout(slow);
  }
  if (!opts.keep) window.scrollTo({ top: 0 });
}

// O app da família, no celular: o que vem pela frente e o que já foi feito, agendar, a saúde (curva, vacinas, marcos) e
// os arquivos trocados com o consultório. Só as crianças desta família, só o que foi liberado para ela.
import { api, html, raw, icon, toast, fail, dialog, ask, money, dateLong, dateBR, dateFull, initials, actions, careTick, carePill,
  fileIcon, relDay, statusPill } from './lib.js';
import { growthChart, bindGrowth, growthTable } from './charts.js';

const DOCK = [['inicio', 'Início', 'home'], ['agenda', 'Agenda', 'calendar'], ['saude', 'Saúde', 'heart'], ['arquivos', 'Arquivos', 'folder']];
const CHILD_KEY = 'pc-child';
let current = null;

function parse() {
  const raw0 = location.hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw0.split('?');
  return { name: path.split('/')[0] || 'inicio', query: Object.fromEntries(new URLSearchParams(query)) };
}

function childId(query) {
  if (query.c) { try { localStorage.setItem(CHILD_KEY, query.c); } catch { /* sem armazenamento */ } return Number(query.c); }
  try { return Number(localStorage.getItem(CHILD_KEY)) || null; } catch { return null; }
}

export function refresh() { if (current) route(current, { keep: true }); }

export async function route(app, opts = {}) {
  current = app;
  document.body.classList.add('has-dock');
  const root = document.getElementById('app');
  if (!document.getElementById('famapp')) {
    root.innerHTML = String(html`<div class="famapp" id="famapp"><div class="fview" id="fview"></div></div>
      <nav class="dock" aria-label="Seções">${DOCK.map(([k, l, ic]) => html`<a href="#/${k}" data-dock="${k}">${icon(ic)}<span>${l}</span></a>`)}</nav>`);
  }
  let { name, query } = parse();
  const views = { inicio: home, agenda, agendar: book, saude: health, arquivos: files };
  if (!views[name]) name = 'inicio';
  document.querySelectorAll('[data-dock]').forEach((a) => {
    const on = a.dataset.dock === (name === 'agendar' ? 'agenda' : name);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  const dock = document.querySelector('.dock');
  dock.hidden = name === 'agendar';
  const old = document.getElementById('fview');
  const view = old.cloneNode(false);
  if (!opts.keep) { old.replaceWith(view); view.innerHTML = '<div class="loading">Carregando…</div>'; }
  try {
    await views[name](view, query, app);
    if (opts.keep) document.getElementById('fview').replaceWith(view);
  } catch (e) {
    if (e.status === 401) { location.reload(); return; }
    if (opts.keep) { fail(e); return; }
    view.innerHTML = String(html`<div class="glass error-box"><h1 class="t-h2">Não deu para abrir</h1><p class="muted">${e.message}</p><button class="btn ghost" type="button" onclick="location.reload()">Tentar de novo</button></div>`);
  }
  if (!opts.keep) window.scrollTo({ top: 0 });
}

// o topo: a criança (trocar, se houver mais de uma) e o menu da conta
function top(app, data, title) {
  const kid = data.children.find((c) => c.id === data.child) || data.children[0];
  const many = data.children.length > 1;
  return html`<header class="famtop">
    ${title ? html`<div class="grow"><h1 class="t-title">${title}</h1><p class="t-small muted">${kid ? `${kid.first_name} · ${kid.age}` : ''}</p></div>`
      : html`<button class="kidpick" type="button" data-act="kid" ${many ? '' : raw('aria-disabled="true"')} aria-label="${many ? 'Trocar de criança' : kid.name}">
        <span class="av lg">${initials(kid.name)}</span>
        <span class="grow" style="display:flex;flex-direction:column;gap:2px">
          <span style="display:flex;align-items:center;gap:4px"><span class="t-title">${kid.first_name}</span>${many ? icon('chevD') : ''}</span>
          <span class="t-small muted">${kid.age} · ${app.site.practice.name}</span></span></button>`}
    <button class="iconbtn" type="button" data-act="account" aria-label="Minha conta">${icon('users')}</button>
  </header>`;
}

function topActions(app, data) {
  return {
    kid: () => {
      if (data.children.length < 2) return;
      const d = dialog({
        title: 'Trocar de criança',
        body: html`<div class="opts">${data.children.map((c) => html`<button class="opt" type="button" data-c="${c.id}" aria-pressed="${c.id === data.child}"><span class="av sm">${initials(c.name)}</span><span class="grow"><b>${c.name}</b><span class="t-small muted" style="display:block">${c.age}</span></span></button>`)}</div>`,
      });
      d.el.addEventListener('click', (ev) => {
        const b = ev.target.closest('[data-c]');
        if (!b) return;
        d.close();
        const { name, query } = parse();
        location.hash = `#/${name}?${new URLSearchParams({ ...query, c: b.dataset.c })}`;
      });
    },
    account: () => {
      const theme = app.theme();
      const d = dialog({
        title: app.me.name,
        body: html`<p class="muted">${app.me.guardian ? `${app.me.guardian.relation} · ` : ''}${app.me.email}</p>
          <div class="rows"><div class="row"><span class="lbl">Tema</span><div class="seg" role="group" aria-label="Tema">${[['claro', 'Claro'], ['escuro', 'Escuro'], ['auto', 'Automático']].map(([k, l]) => html`<button type="button" data-theme="${k}" aria-pressed="${k === theme}">${l}</button>`)}</div></div></div>
          <p class="t-small muted pretty">Em caso de urgência, procure o pronto-socorro. O app não substitui o atendimento de urgência.</p>`,
        actions: [{ label: 'Sair', kind: 'ghost', run: () => app.logout() }],
      });
      d.el.addEventListener('click', (ev) => {
        const b = ev.target.closest('[data-theme]');
        if (!b) return;
        app.setTheme(b.dataset.theme);
        d.el.querySelectorAll('[data-theme]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      });
    },
  };
}

// ---- Início ---------------------------------------------------------------------------------------------------------
async function home(view, query, app) {
  const data = await api(`/api/family/home${childId(query) ? `?child=${childId(query)}` : ''}`);
  if (!data.children.length) { view.innerHTML = String(html`<div class="glass error-box"><h1 class="t-h2">Nenhuma criança ligada à sua conta</h1><p class="muted">Peça ao consultório para ligar a sua conta ao cadastro da criança.</p></div>`); return; }
  const kid = data.children.find((c) => c.id === data.child);
  const next = data.next;
  const todo = data.todo.filter((i) => !next || i !== data.todo.find((t) => t.title === next.title && t.type === next.type));
  const plan = kid.plan;
  view.innerHTML = String(html`
    ${top(app, data)}
    ${kid.allergies ? html`<p class="pill late" style="align-self:flex-start;height:auto;padding:6px 12px;white-space:normal">${icon('alert')}${kid.allergies}</p>` : ''}
    ${next ? html`<section class="glass card" style="display:flex;flex-direction:column;gap:12px">
      <span class="t-cap">Próximo passo</span>
      <div style="display:flex;flex-direction:column;gap:4px">
        <h2 class="t-h2" style="font-size:21px">${next.title}</h2>
        <p class="muted pretty">${nextText(next, app)}</p>
      </div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px">
        ${next.action === 'agendar' ? html`<a class="btn" href="#/agendar?c=${kid.id}&k=${next.type === 'retorno' ? 'follow_up' : 'well_child'}">Agendar</a>` : ''}
        ${next.status === 'agendado' ? html`<a class="btn ghost" href="#/agenda">Ver a consulta</a>` : ''}
        ${next.action === 'enviar' ? html`<a class="btn" href="#/arquivos?c=${kid.id}">Enviar</a>` : ''}
        ${plan && next.type === 'consulta' ? html`<span class="pill ok">Incluída no plano</span>` : ''}
      </div>
    </section>` : ''}
    <section class="glass card">
      <div class="phead"><h2 class="t-h2">A fazer</h2><span class="t-small muted">${todo.length} ${todo.length === 1 ? 'item' : 'itens'}</span></div>
      <div style="margin-top:4px">${todo.length ? todo.map((i) => todoRow(i, kid, app)) : html`<p class="t-small muted" style="padding:10px 0">Nada pendente. Tudo em dia.</p>`}</div>
    </section>
    <section class="glass card">
      <div class="phead"><h2 class="t-h2">Feito</h2><a class="linkbtn t-small" href="#/saude?c=${kid.id}">Saúde</a></div>
      <div style="margin-top:4px">${data.done.slice(0, 6).map((i) => html`<div class="li top">${careTick(i)}
        <div class="grow"><b>${i.title}</b><p class="t-small muted">${dateBR(i.date)}${i.detail && i.type !== 'consulta' ? ` · ${i.detail}` : ''}</p>
          ${i.type === 'consulta' && i.detail ? html`<p class="t-small pretty" style="margin-top:4px">${i.detail.length > 110 ? `${i.detail.slice(0, 110).trim()}…` : i.detail}</p>
          <button class="linkbtn t-small" type="button" data-act="summary" data-text="${i.detail}" data-title="${i.title}" data-date="${i.date}" style="margin-top:4px">Ler o resumo</button>` : ''}</div></div>`)}</div>
    </section>
    ${plan ? html`<section class="glass card" style="display:flex;flex-direction:column;gap:12px">
      <div class="phead"><h2 class="t-h3">Plano ${plan.plan}</h2><span class="t-small muted">renova em ${dateFull(addDay(plan.ends_on))}</span></div>
      ${plan.usage.map((u) => html`<div style="display:flex;flex-direction:column;gap:6px"><div style="display:flex;justify-content:space-between;gap:8px"><span class="t-small">${u.label}</span><span class="t-small muted">${u.used} de ${u.qty}${u.booked ? ` · ${u.booked} marcada${u.booked > 1 ? 's' : ''}` : ''}</span></div>
        <div class="meter"><i style="width:${Math.min(100, Math.round(100 * u.used / u.qty))}%"></i></div></div>`)}
      ${plan.perks.length ? html`<p class="t-small muted">${plan.perks.join(' · ')}</p>` : ''}
    </section>` : ''}`);
  actions(view, {
    ...topActions(app, data),
    summary: (el) => dialog({ title: el.dataset.title, body: html`<p class="t-small muted">${dateLong(el.dataset.date)} · ${app.site.practice.name}</p><p class="pretty" style="font-size:16px;line-height:1.55">${el.dataset.text}</p>` }),
    mark: async (el) => {
      await api(`/api/family/children/${kid.id}/milestones`, { method: 'POST', body: { code: el.dataset.code } });
      toast(`Que bom! Marcado. A ${app.site.practice.name.split(' ').slice(0, 2).join(' ')} vê na próxima consulta.`);
      refresh();
    },
  });
}

const addDay = (iso) => { const d = new Date(`${iso}T12:00`); d.setDate(d.getDate() + 1); return d.toISOString().slice(0, 10); };

function nextText(n, app) {
  if (n.type === 'consulta' && n.status === 'agendado') return `Marcada: ${n.detail}, com ${app.site.practice.name}.`;
  if (n.type === 'consulta' && n.status === 'atrasado') return `A consulta passou da janela (${n.detail.replace(/^era /, '')}). Agende assim que puder.`;
  if (n.type === 'consulta') return `${n.detail.charAt(0).toUpperCase()}${n.detail.slice(1)}.`;
  return n.detail;
}

function todoRow(i, kid, app) {
  let act = '';
  if (i.action === 'enviar') act = html`<a class="btn ghost small" href="#/arquivos?c=${kid.id}${i.refs.care_item_id ? `&item=${i.refs.care_item_id}` : ''}">Enviar</a>`;
  if (i.action === 'marcar') act = html`<button class="btn ghost small" type="button" data-act="mark" data-code="${i.refs.milestone}">Marcar</button>`;
  if (i.action === 'agendar') act = html`<a class="btn ghost small" href="#/agendar?c=${kid.id}&k=${i.type === 'retorno' ? 'follow_up' : 'well_child'}">Agendar</a>`;
  return html`<div class="li">${careTick(i)}<div class="grow"><b>${i.type === 'marco' ? `Observar: ${i.title.toLowerCase()}` : i.title}</b><div class="meta">${carePill(i, app.today)}<span class="t-small muted">${i.detail}</span></div></div>${act}</div>`;
}

// ---- Agenda (as consultas) ------------------------------------------------------------------------------------------
async function agenda(view, query, app) {
  const [homeData, r] = await Promise.all([api(`/api/family/home${childId(query) ? `?child=${childId(query)}` : ''}`), api('/api/family/appointments')]);
  const one = homeData.children.length === 1;
  const row = (a, upcoming) => html`<div class="li top"><span class="tick">${icon('calendar')}</span>
    <div class="grow"><b>${a.service}${one ? '' : ` · ${a.patient.first_name}`}</b><p class="t-small muted">${dateLong(a.date)}, às ${a.time} · ${relDay(a.date, app.today)}</p>
      <div class="meta">${statusPill(a.status, a.status_label)}${a.covered ? html`<span class="pill ok">No plano</span>` : a.price_cents ? html`<span class="pill">${money(a.price_cents)}</span>` : ''}</div></div>
    ${upcoming && a.can_cancel ? html`<button class="linkbtn t-small danger" type="button" data-act="cancel" data-id="${a.id}">Cancelar</button>` : ''}</div>`;
  view.innerHTML = String(html`
    ${top(app, homeData, 'Agenda')}
    <a class="btn big wide" href="#/agendar?c=${homeData.child}">${icon('plus')}Agendar uma consulta</a>
    <section class="glass card"><div class="phead"><h2 class="t-h2">Marcadas</h2></div>
      ${r.upcoming.length ? r.upcoming.map((a) => row(a, true)) : html`<p class="t-small muted" style="padding:10px 0">Nenhuma consulta marcada.</p>`}
      ${r.upcoming.some((a) => !a.can_cancel) ? html`<p class="t-small muted" style="margin-top:6px">Faltando menos de ${r.upcoming[0].cancel_hours} h, o cancelamento é pelo telefone do consultório.</p>` : ''}</section>
    ${r.past.length ? html`<section class="glass card"><div class="phead"><h2 class="t-h2">Antes</h2></div>${r.past.map((a) => row(a, false))}</section>` : ''}`);
  actions(view, {
    ...topActions(app, homeData),
    cancel: async (el) => {
      if (!await ask('Cancelar esta consulta?', 'O horário volta a ficar livre para outra família.', 'Cancelar a consulta', true)) return;
      await api(`/api/family/appointments/${el.dataset.id}/cancel`, { method: 'POST' });
      toast('Consulta cancelada.'); refresh();
    },
  });
}

// ---- Agendar ---------------------------------------------------------------------------------------------------------
async function book(view, query, app) {
  const homeData = await api(`/api/family/home${childId(query) ? `?child=${childId(query)}` : ''}`);
  const kid = homeData.children.find((c) => c.id === homeData.child);
  const svcData = await api(`/api/family/children/${kid.id}/services`);
  const services = svcData.services;
  let svc = services.find((s) => s.kind === query.k) || services[0];
  let days = [], window = null, day = null, times = [], time = null, cover = null, questions = [], cancelHours = 24;
  view.innerHTML = String(html`
    <header class="famtop"><a class="iconbtn" href="#/agenda" aria-label="Voltar">${icon('chevL')}</a><h1 class="t-title grow">Agendar</h1>
      <span class="pill" style="height:36px;padding:0 12px 0 4px;gap:8px;font-size:13px;color:var(--text)"><span class="av sm">${initials(kid.name)}</span>${kid.first_name}</span></header>
    <section class="glass card"><span class="t-cap">O quê</span><div class="opts" data-services style="margin-top:10px"></div></section>
    <section class="glass card"><span class="t-cap">Quando</span><p class="t-small muted" data-hint style="margin-top:6px"></p>
      <div class="days" data-days style="margin-top:10px"></div><div class="times" data-times style="margin-top:12px"></div></section>
    <section class="glass card" data-summary hidden></section>
    <div style="height:70px"></div>
    <div class="actionbar"><button class="btn big wide" type="button" data-act="confirm" disabled>Confirmar agendamento</button></div>`);
  const $ = (s) => view.querySelector(s);
  const paintServices = () => {
    $('[data-services]').innerHTML = String(html`${services.map((s) => html`<button class="opt" type="button" data-svc="${s.id}" aria-pressed="${s.id === svc.id}">
      <span class="radio" aria-hidden="true"></span><span class="grow" style="display:flex;flex-direction:column;gap:2px"><b>${s.display || s.name}</b><span class="t-small muted">${s.kind_label} · ${s.duration_min} min</span></span>
      <span class="t-small" style="font-weight:700;text-align:right;max-width:110px">${s.covered ? 'No plano' : s.final_cents ? money(s.final_cents) : 'Sem custo'}</span></button>`)}`);
  };
  const paintDays = () => {
    $('[data-hint]').textContent = window ? `A janela da ${window.title.toLowerCase()} vai de ${dateBR(window.from)} a ${dateBR(window.to)}.` : svc.kind === 'sick_visit' ? 'As vagas para a criança doente abrem no próprio dia.' : '';
    $('[data-days]').innerHTML = days.length ? String(html`${days.map((d) => html`<button class="day" type="button" data-day="${d.date}" aria-pressed="${d.date === day}" aria-label="${dateLong(d.date)}">${d.weekday}<b>${d.day}</b></button>`)}`)
      : String(html`<p class="t-small muted">Nenhum horário livre nos próximos dias. Fale com o consultório.</p>`);
  };
  const paintTimes = () => {
    $('[data-times]').innerHTML = String(html`${times.map((t) => html`<button class="time" type="button" data-time="${t.time}" aria-pressed="${t.time === time}">${t.time}</button>`)}`);
  };
  const paintSummary = () => {
    const box = $('[data-summary]');
    const ok = day && time;
    $('[data-act="confirm"]').disabled = !ok;
    box.hidden = !ok;
    if (!ok) return;
    box.innerHTML = String(html`<span class="t-cap">Resumo</span><div style="margin-top:6px">
      <div class="sumrow">${icon('calendar')}<div class="grow"><b>${dateLong(day)}, às ${time}</b><p class="t-small muted">${svc.display || svc.name} · ${svc.duration_min} min</p></div></div>
      <div class="sumrow">${icon('pin')}<div class="grow"><p>${app.site.practice.address || app.site.practice.name} · ${app.site.practice.name}</p></div></div>
      <div class="sumrow">${icon('card')}<div class="grow"><p>${cover && cover.covered ? cover.label : cover && cover.label ? `${money(cover.price_cents)} · ${cover.label}` : money(svc.final_cents ?? svc.price_cents)}</p><p class="t-small muted">${svc.kind === 'sick_visit' ? 'Melhorou? Cancele pelo app e a vaga volta para outra criança.' : `Remarque ou cancele sem custo até ${cancelHours} h antes.`}</p></div></div>
      ${questions.length ? html`<div class="sumrow">${icon('doc')}<div class="grow"><p class="t-small">Antes da consulta, ${questions.length} pergunta${questions.length > 1 ? 's' : ''} rápida${questions.length > 1 ? 's' : ''} sobre ${questions.slice(0, 2).map((q) => q.replace(/\?$/, '').toLowerCase().replace(/^como está (a|o) /, '')).join(' e ')}.</p></div></div>` : ''}
    </div>`);
  };
  const loadDays = async () => {
    day = null; time = null; times = [];
    const r = await api(`/api/family/children/${kid.id}/days?service_id=${svc.id}`);
    days = r.days; window = r.window;
    paintDays(); paintTimes(); paintSummary();
    if (days.length) await pickDay(days[0].date);
  };
  const pickDay = async (d) => {
    day = d; time = null;
    paintDays();
    const r = await api(`/api/family/children/${kid.id}/slots?service_id=${svc.id}&date=${d}`);
    times = r.times; cover = r.cover; questions = r.questions || []; cancelHours = r.cancel_hours;
    paintTimes(); paintSummary();
  };
  paintServices();
  view.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-svc],[data-day],[data-time],[data-act]');
    if (!b) return;
    try {
      if (b.dataset.svc) { svc = services.find((s) => s.id === Number(b.dataset.svc)); paintServices(); await loadDays(); }
      if (b.dataset.day) await pickDay(b.dataset.day);
      if (b.dataset.time) { time = b.dataset.time; paintTimes(); paintSummary(); }
      if (b.dataset.act === 'confirm') {
        b.disabled = true;
        await api(`/api/family/children/${kid.id}/appointments`, { method: 'POST', body: { service_id: svc.id, date: day, time } });
        toast(`Consulta marcada: ${dateLong(day)}, às ${time}.`);
        location.hash = '#/agenda';
      }
    } catch (e) { fail(e); if (b.dataset.act) b.disabled = false; }
  });
  if (!services.length) { $('[data-services]').innerHTML = '<p class="t-small muted">Nenhum serviço para marcar pelo app. Fale com o consultório.</p>'; return; }
  await loadDays();
}

// ---- Saúde -----------------------------------------------------------------------------------------------------------
async function health(view, query, app) {
  const homeData = await api(`/api/family/home${childId(query) ? `?child=${childId(query)}` : ''}`);
  const kid = homeData.children.find((c) => c.id === homeData.child);
  const indicator = ['wfa', 'lhfa', 'hcfa'].includes(query.m) ? query.m : 'wfa';
  const r = await api(`/api/family/children/${kid.id}/health?indicator=${indicator}`);
  const ch = r.chart;
  const pending = r.vaccines.filter((v) => ['pendente', 'atrasado'].includes(v.status));
  const applied = r.vaccines.filter((v) => v.status === 'feito');
  const upcoming = r.vaccines.filter((v) => v.status === 'futura').slice(0, 3);
  const band = r.milestones.bands.find((b) => b.current);
  const pastBands = r.milestones.bands.filter((b) => !b.current).reverse();
  view.innerHTML = String(html`
    ${top(app, homeData, 'Saúde')}
    <section class="glass card" style="display:flex;flex-direction:column;gap:10px">
      <div class="phead center"><h2 class="t-h2">Crescimento</h2>
        <div class="seg" role="group" aria-label="Medida">${[['wfa', 'Peso'], ['lhfa', 'Altura'], ['hcfa', 'Cabeça']].map(([k, l]) => html`<a href="#/saude?c=${kid.id}&m=${k}" role="button" aria-pressed="${k === indicator}" style="display:inline-flex;align-items:center;height:32px;padding:0 12px;border-radius:999px;text-decoration:none;font:600 13px/1 var(--font);${k === indicator ? 'color:var(--text);font-weight:700;background:var(--lens), color-mix(in srgb, var(--text) 7%, transparent);box-shadow:var(--lens-rim), var(--lens-glow)' : 'color:var(--muted)'}">${l}</a>`)}</div></div>
      ${ch.latest ? html`<div><p><span class="t-title">${ch.latest.value.toLocaleString('pt-BR')} ${ch.unit}</span><span class="muted" style="margin-left:8px">${ch.latest.label === 'Nascimento' ? 'ao nascer' : `aos ${ch.latest.label}`}</span></p>
        <p class="t-small" style="display:flex;align-items:center;gap:6px">${icon('check')}${(ch.latest.reading || '').charAt(0).toUpperCase()}${(ch.latest.reading || '').slice(1)}${ch.latest.pct ? `, ${ch.latest.pct.replace('P', 'percentil ')}` : ''}.</p></div>` : html`<p class="muted">Ainda sem medidas: elas aparecem depois das consultas.</p>`}
      ${growthChart(ch, { name: kid.first_name })}
      <div style="display:flex;justify-content:flex-end"><button class="linkbtn t-small" type="button" data-act="table">Ver tabela</button></div>
      <div data-table hidden>${growthTable(ch)}</div>
    </section>
    <section class="glass card">
      <div class="phead"><h2 class="t-h2">Vacinas</h2><span class="t-small muted">${applied.length} dose${applied.length === 1 ? '' : 's'} aplicada${applied.length === 1 ? '' : 's'}</span></div>
      <div style="margin-top:4px">
        ${[...pending, ...upcoming].map((v) => html`<div class="li"><span class="tick">${icon('syringe')}</span><div class="grow"><b>${v.vaccine} · ${v.dose}</b>
          <div class="meta">${v.status === 'atrasado' ? html`<span class="pill late">Atrasada</span>` : v.status === 'pendente' ? html`<span class="pill todo">A fazer</span>` : html`<span class="pill">${relDay(v.due, app.today).replace(/^em /, 'Em ')}</span>`}<span class="t-small muted">${v.status === 'atrasado' ? `era em ${dateBR(v.due)}` : `a partir de ${dateBR(v.due)}`}</span></div></div></div>`)}
        ${!pending.length && !upcoming.length ? html`<p class="t-small muted" style="padding:10px 0">Nenhuma vacina pendente.</p>` : ''}
      </div>
      <details style="margin-top:8px"><summary class="linkbtn t-small" style="cursor:pointer">Ver a caderneta inteira</summary>
        <div style="margin-top:6px">${applied.slice().reverse().map((v) => html`<div class="li"><span class="tick">${icon('check')}</span><div class="grow"><b>${v.vaccine}</b> <span class="muted">· ${v.dose}</span><p class="t-small muted">${dateFull(v.applied_on)}${v.place ? ` · ${v.place}` : ''}</p></div></div>`)}</div>
      </details>
    </section>
    ${band ? html`<section class="glass card">
      <div class="phead"><h2 class="t-h2">${band.title}</h2></div>
      <div style="margin-top:4px">${band.items.map((it) => html`<div class="li"><span class="tick">${icon(it.checked ? 'check' : 'flag')}</span>
        <div class="grow"><b>${it.label}</b><p class="t-small muted">${it.checked ? `${dateBR(it.achieved_on)} · ${it.marked_by ? `marcado por ${it.marked_by}` : 'conferido na consulta'}` : 'ainda não'}</p></div>
        ${it.checked ? '' : html`<button class="btn ghost small" type="button" data-act="mark" data-code="${it.code}">Marcar</button>`}</div>`)}</div>
      <p class="t-small muted pretty" style="margin-top:8px">Cada criança tem o seu tempo. Os marcos são uma conversa com a pediatra, não uma prova.</p>
      ${pastBands.length ? html`<details style="margin-top:8px"><summary class="linkbtn t-small" style="cursor:pointer">Marcos anteriores</summary>
        ${pastBands.map((b) => html`<div style="margin-top:10px"><span class="t-cap">${b.title}</span>${b.items.map((it) => html`<div class="li"><span class="tick">${icon(it.checked ? 'check' : 'flag')}</span><div class="grow"><b>${it.label}</b><p class="t-small muted">${it.checked ? dateBR(it.achieved_on) : 'não marcado'}</p></div></div>`)}</div>`)}
      </details>` : ''}
    </section>` : ''}`);
  bindGrowth(view, ch);
  actions(view, {
    ...topActions(app, homeData),
    table: (el) => { const t = view.querySelector('[data-table]'); t.hidden = !t.hidden; el.textContent = t.hidden ? 'Ver tabela' : 'Esconder a tabela'; },
    mark: async (el) => {
      await api(`/api/family/children/${kid.id}/milestones`, { method: 'POST', body: { code: el.dataset.code } });
      toast('Que bom! Marcado.'); refresh();
    },
  });
}

// ---- Arquivos ------------------------------------------------------------------------------------------------------
async function files(view, query, app) {
  const homeData = await api(`/api/family/home${childId(query) ? `?child=${childId(query)}` : ''}`);
  const filter = query.f || 'todos';
  const r = await api(`/api/family/files?filter=${filter}`);
  const term = (query.q || '').toLowerCase();
  const list = r.files.filter((f) => !term || `${f.title} ${f.patient || ''}`.toLowerCase().includes(term));
  view.innerHTML = String(html`
    <header class="famtop"><div class="grow"><h1 class="t-title">Arquivos</h1><p class="t-small muted">${homeData.children.map((c) => c.first_name).join(' e ')}</p></div>
      <button class="btn ghost" type="button" data-act="upload">${icon('upload')}Enviar</button></header>
    <form class="field" data-search>${icon('search')}<input name="q" type="search" value="${query.q || ''}" placeholder="Buscar exame, receita, nota…" aria-label="Buscar nos arquivos"></form>
    <div class="chips" role="group" aria-label="Tipo de arquivo">${Object.entries(r.filters).map(([k, l]) => html`<a class="chip" href="#/arquivos?f=${k}" aria-pressed="${k === filter}" style="text-decoration:none">${l}</a>`)}</div>
    ${r.waiting.map((w) => html`<section class="glass card" style="display:flex;flex-direction:column;gap:12px">
      <div style="display:flex;align-items:center;gap:10px"><span class="pill todo">Esperando você</span><span class="t-small muted">pedido em ${dateBR(w.created_at)}</span></div>
      <div style="display:flex;flex-direction:column;gap:4px"><h2 class="t-h2">${w.title} ${homeData.children.length > 1 ? `· ${w.patient.split(' ')[0]}` : ''}</h2>
        <p class="t-small muted pretty">${w.detail ? `${w.detail.charAt(0).toUpperCase()}${w.detail.slice(1)}. ` : ''}Envie o resultado aqui e a pediatra recebe na hora.</p></div>
      <div><button class="btn" type="button" data-act="result" data-item="${w.care_item_id}" data-child="${w.patient_id}" data-title="${w.title}">${icon('upload')}Enviar o resultado</button></div>
    </section>`)}
    <section class="glass card" style="padding-top:8px;padding-bottom:8px">
      ${list.length ? list.map((f) => html`<div class="li top">
        <span class="tick sq">${icon(fileIcon(f.kind))}</span>
        <div class="grow"><b>${f.title}</b><p class="t-small muted">${f.patient ? `${f.patient.split(' ')[0]} · ` : ''}${f.uploader_role === 'familia' ? `enviado por ${f.uploader_name || 'você'}` : f.uploader_name || 'consultório'} · ${dateBR(f.created_at)}</p>
          ${f.note ? html`<p class="quote">“${f.note}”</p>` : ''}
          ${f.review_note ? html`<p class="quote"><b>Pediatra:</b> ${f.review_note}</p>` : f.reviewed_at ? html`<p style="margin-top:6px"><span class="pill ok">${icon('check')}Revisado</span></p>` : f.needs_review ? html`<p style="margin-top:6px"><span class="pill todo">Esperando a revisão</span></p>` : ''}</div>
        <a class="linkbtn t-small" href="/api/files/${f.id}" target="_blank" rel="noopener">Abrir</a>
      </div>`) : html`<p class="empty"><b>Nada por aqui.</b>Receitas, atestados, exames e notas aparecem aqui.</p>`}
    </section>`);
  view.querySelector('[data-search]').addEventListener('submit', (ev) => {
    ev.preventDefault();
    location.hash = `#/arquivos?${new URLSearchParams({ f: filter, q: new FormData(ev.target).get('q') })}`;
  });
  actions(view, {
    upload: () => uploadDialog(homeData, {}),
    result: (el) => uploadDialog(homeData, { item: Number(el.dataset.item), child: Number(el.dataset.child), title: el.dataset.title, kind: 'exame' }),
  });
  if (query.item) {
    const w = r.waiting.find((x) => x.care_item_id === Number(query.item));
    uploadDialog(homeData, w ? { item: w.care_item_id, child: w.patient_id, title: w.title, kind: 'exame' } : { child: homeData.child, kind: 'caderneta', title: 'Caderneta de vacinação', item: Number(query.item) });
  }
}

function uploadDialog(homeData, pre) {
  const kinds = [['exame', 'Exame'], ['foto', 'Foto'], ['video', 'Vídeo'], ['caderneta', 'Caderneta de vacinação'], ['comprovante', 'Comprovante'], ['documento', 'Documento']];
  dialog({
    title: pre.item ? `Enviar: ${pre.title}` : 'Enviar arquivo',
    body: html`<div class="rows">
      ${homeData.children.length > 1 ? html`<label class="row"><span class="lbl">De quem</span><select class="inline" data-f="child">${homeData.children.map((c) => html`<option value="${c.id}" ${c.id === (pre.child || homeData.child) ? raw('selected') : ''}>${c.first_name}</option>`)}</select></label>` : ''}
      <label class="row"><span class="lbl">O que é</span><select class="inline" data-f="kind">${kinds.map(([k, l]) => html`<option value="${k}" ${k === (pre.kind || 'exame') ? raw('selected') : ''}>${l}</option>`)}</select></label>
      <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="title" value="${pre.title || ''}" placeholder="Hemograma, foto da manchinha…"></label>
    </div>
    <label class="t-cap" for="up-note">Quer dizer algo à pediatra?</label>
    <textarea class="area" id="up-note" data-f="note" rows="2" placeholder="Apareceu ontem, não coça."></textarea>
    <label class="field" style="border-radius:18px;padding:12px 16px">${icon('camera')}<input type="file" data-f="file" accept="image/*,application/pdf,video/mp4,video/quicktime" style="height:auto"></label>
    <p class="note">Foto, PDF ou vídeo curto. A localização da foto é apagada antes de guardar.</p>`,
    actions: [{ label: 'Enviar', run: async (dlg) => {
      const f = (k) => dlg.querySelector(`[data-f="${k}"]`);
      const file = f('file').files[0];
      if (!file) throw new Error('Escolha a foto ou o arquivo.');
      const fd = new FormData();
      fd.append('child_id', f('child') ? f('child').value : (pre.child || homeData.child));
      fd.append('kind', f('kind').value);
      fd.append('title', f('title').value);
      fd.append('note', f('note').value);
      if (pre.item) fd.append('care_item_id', pre.item);
      fd.append('upload', file);
      await api('/api/family/files', { method: 'POST', form: fd });
      toast('Enviado. A pediatra recebe e responde por aqui.');
      if (location.hash !== '#/arquivos') location.hash = '#/arquivos'; else refresh();
    } }],
  });
}


// O dia: o painel do pediatra (Hoje), a agenda em grade e as tarefas da recepção.
import { api, html, raw, icon, toast, money, dateLong, dateBR, addDays, initials, statusPill, fileIcon, ago, actions, relDay, weekday, ask } from './lib.js';
import { openAppointment, newAppointment, greeting, waButton, bindWhatsApp, askedText, inviteFamily, documentDialog } from './staff-common.js';
import { setCount, refresh } from './staff.js';

export const shortName = (name) => {
  const parts = String(name || '').split(/\s+/);
  return /^Dra?\.$/.test(parts[0]) ? `${parts[0]} ${parts[1] || ''}` : parts[0];
};

// o que a família leva de cada pagamento: o recibo (pessoa física) ou a nota (empresa)
const TO_ISSUE = { pf: 'Recibos a emitir', pj: 'Notas a emitir' };

// ---- Hoje -------------------------------------------------------------------------------------------------------------
export async function today(view, params, app) {
  const d = await api('/api/staff/today');
  setCount('revisar', d.review_count);
  const f = d.focus;
  const rows = [
    ...d.appointments.map((a) => ({ t: a.time, a })),
    ...d.reserved_free.map((s) => ({ t: s.time, slot: s })),
  ].sort((x, y) => x.t.localeCompare(y.t));
  const others = d.waiting.filter((w) => !f || w.id !== f.appointment.id);
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><span class="t-cap">${dateLong(d.date)}</span><h1 class="t-title">${greeting(d.now)}, ${shortName(app.me.name)}</h1></div>
      <form class="field" style="flex:0 1 320px" data-search>${icon('search')}<input name="q" type="search" placeholder="Buscar criança ou responsável" aria-label="Buscar criança ou responsável"></form>
      <button class="btn ghost" type="button" data-act="encaixe">${icon('plus')}Encaixe</button>
    </div>
    <div class="cols">
      <div class="colmain">
        <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
          ${f ? focusCard(f, others) : html`<span class="t-cap">Agora</span><p class="t-h3">Ninguém na espera.</p><p class="muted">Quando a recepção marcar a chegada, a criança aparece aqui.</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">Agenda de hoje</h2><span class="t-small muted">${d.counts.total} consulta${d.counts.total === 1 ? '' : 's'}${d.counts.squeeze ? ` · ${d.counts.squeeze} encaixe${d.counts.squeeze > 1 ? 's' : ''}` : ''}${d.reserved_free.length ? ` · ${d.reserved_free.length} vaga${d.reserved_free.length > 1 ? 's' : ''} para criança doente` : ''}</span></div>
          <div style="margin-top:8px">
            ${rows.length ? rows.map((r) => r.a ? html`
              <button class="arow ${f && r.a.id === f.appointment.id ? 'next' : ''}" type="button" data-act="appt" data-id="${r.a.id}">
                <span class="tm">${r.a.time}</span>
                <span class="who2"><span class="av sm">${initials(r.a.patient.name)}</span><b>${r.a.patient.name}, ${r.a.patient.age_short}</b></span>
                <span class="svc">${r.a.kind === 'encaixe' ? 'Encaixe · ' : ''}${r.a.service}${r.a.covered ? ' · plano' : ''}</span>
                ${apptPill(r.a)}
              </button>` : html`
              <button class="arow free" type="button" data-act="slot" data-time="${r.slot.time}">
                <span class="tm">${r.slot.time}</span>
                <span class="who2"><span class="tick" style="width:32px;height:32px">${icon('plus')}</span><span>Vaga para criança doente</span></span>
                <span class="svc">aberta para as famílias hoje</span>
                <span class="pill">Livre</span>
              </button>`) : html`<p class="empty">Nenhuma consulta hoje.</p>`}
          </div>
        </section>
      </div>
      <div class="colside">
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">Para revisar</h2><a class="linkbtn t-small" href="#/revisar">Ver tudo</a></div>
          <div style="margin-top:4px">
            ${d.review.length ? d.review.slice(0, 4).map((r) => html`
              <a class="li" href="#/revisar">
                <span class="tick sq">${icon(fileIcon(r.kind))}</span>
                <span class="grow"><b style="display:block">${r.title}</b><span class="t-small muted">${r.patient || ''}${r.age_short ? `, ${r.age_short}` : ''} · ${r.uploader_name || 'família'} · ${ago(r.created_at)}</span>
                ${r.note ? html`<span class="t-small" style="display:block">“${r.note}”</span>` : ''}</span>
                ${icon('chevR', 'muted')}
              </a>`) : html`<p class="empty">Nada para revisar.</p>`}
          </div>
        </section>
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">Pendências do cuidado</h2><span class="t-small muted">a busca ativa</span></div>
          <div style="margin-top:4px">
            ${careLink('calendar', d.care.late_visits, 'puericultura atrasada', 'puericulturas atrasadas', 'a recepção liga para as famílias')}
            ${careLink('syringe', d.care.late_vaccines, 'criança com vacina atrasada', 'crianças com vacina atrasada', 'as famílias recebem o lembrete')}
            ${careLink('flask', d.care.old_exams, 'exame sem resultado', 'exames sem resultado', 'pedidos há mais de 15 dias')}
          </div>
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
          <div class="phead"><h2 class="t-h2">O dia em dinheiro</h2><a class="linkbtn t-small" href="#/financeiro">Ver o financeiro</a></div>
          <div style="display:flex;flex-wrap:wrap;gap:14px 28px">
            <div><span class="t-small muted">Previsto</span><p class="t-title">${money(d.money.expected)}</p></div>
            <div><span class="t-small muted">Recebido</span><p class="t-title">${money(d.money.received)}</p></div>
          </div>
          ${d.counts.covered ? html`<p class="t-small muted">${d.counts.covered} consulta${d.counts.covered > 1 ? 's' : ''} de hoje ${d.counts.covered > 1 ? 'são' : 'é'} do plano e não ${d.counts.covered > 1 ? 'geram' : 'gera'} cobrança.</p>` : ''}
        </section>
      </div>
    </div>`);
  view.querySelector('[data-search]').addEventListener('submit', (ev) => {
    ev.preventDefault();
    location.hash = `#/pacientes?q=${encodeURIComponent(new FormData(ev.target).get('q'))}`;
  });
  actions(view, {
    appt: (el) => openAppointment(app, d.appointments.find((a) => a.id === Number(el.dataset.id)), refresh),
    slot: (el) => newAppointment(app, { date: d.date, time: el.dataset.time, serviceKind: 'sick_visit' }, refresh),
    encaixe: () => newAppointment(app, { date: d.date, kind: 'encaixe', serviceKind: 'sick_visit' }, refresh),
    start: async (el) => {
      const r = await api(`/api/staff/appointments/${el.dataset.id}/encounter`, { method: 'POST' });
      location.hash = `#/consulta/${r.encounter_id}`;
    },
  });
}

function focusCard(f, others) {
  const a = f.appointment, p = f.patient;
  const live = a.status === 'em_atendimento';
  const when = live ? 'em consulta agora' : a.status === 'chegou' ? `na espera há ${a.wait_min} min` : `às ${a.time}`;
  return html`
    <span class="t-cap">${live ? 'Em consulta' : 'Próxima consulta'}</span>
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px 18px">
      <span class="av lg">${initials(p.name)}</span>
      <div class="grow" style="display:flex;flex-direction:column;gap:4px;min-width:220px">
        <h2 class="t-h2" style="font-size:21px">${p.name}, ${p.age_short}</h2>
        <p class="muted">${a.service}${a.kind === 'encaixe' ? ' · encaixe' : ''} · ${when}</p>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">
          ${p.allergies ? html`<span class="pill late long">${icon('alert')}${p.allergies}</span>` : ''}
          ${p.plan ? html`<span class="pill long">Plano ${p.plan.plan} · ${p.plan.summary}</span>` : ''}
        </div>
      </div>
      <button class="btn big" type="button" data-act="start" data-id="${a.id}">${live ? 'Continuar a consulta' : 'Chamar e abrir a consulta'}</button>
    </div>
    ${others.length ? html`<div class="well" style="padding:10px 14px;display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px">
      <span class="t-small muted">Também na espera</span>
      ${others.map((w) => html`<button class="linkbtn t-small" type="button" data-act="appt" data-id="${w.id}">${w.patient.name}, ${w.patient.age_short} · ${w.kind === 'encaixe' ? 'encaixe · ' : ''}há ${w.wait_min} min</button>`)}
    </div>` : ''}`;
}

export function apptPill(a) {
  if (a.status === 'chegou') return html`<span class="pill todo">Na espera${a.wait_min != null ? ` · ${a.wait_min} min` : ''}</span>`;
  if (a.status === 'agendado') return html`<span class="pill todo">Sem confirmação</span>`;
  return statusPill(a.status, a.status_label);
}

function careLink(ic, n, one, many, sub) {
  return html`<a class="li" href="#/recepcao">
    <span class="tick">${icon(ic)}</span>
    <span class="grow" style="display:flex;flex-direction:column"><b>${n ? `${n} ${n === 1 ? one : many}` : `Nenhuma ${one.replace(/^criança com /, '')}`}</b><span class="t-small muted">${n ? sub : 'tudo em dia'}</span></span>
    ${icon('chevR', 'muted')}</a>`;
}

// ---- Agenda em grade --------------------------------------------------------------------------------------------------
const ROW = 22;

// quem se sobrepõe na mesma coluna (o encaixe) ganha uma faixa ao lado: grupos de sobreposição, faixas por ordem
function lanes(col) {
  const items = [
    ...col.appointments.map((a) => ({ a, s: toMin(a.time), e: toMin(a.time) + a.duration_min })),
    ...col.reserved_free.map((slot) => ({ slot, s: toMin(slot.time), e: toMin(slot.time) + slot.duration_min })),
  ].sort((x, y) => x.s - y.s || y.e - x.e);
  let group = [], end = -1;
  const flush = () => {
    const ends = [];
    group.forEach((it) => {
      let k = ends.findIndex((e) => e <= it.s);
      if (k < 0) { k = ends.length; ends.push(it.e); } else ends[k] = it.e;
      it.lane = k;
    });
    group.forEach((it) => { it.lanes = ends.length; });
  };
  items.forEach((it) => {
    if (group.length && it.s >= end) { flush(); group = []; end = -1; }
    group.push(it);
    end = Math.max(end, it.e);
  });
  if (group.length) flush();
  return items;
}
const toMin = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

export async function agenda(view, params, app) {
  const date = params.query.d || app.today;
  const clinicScope = params.query.scope || (app.me.role === 'receptionist' ? 'clinic' : 'me');
  const r = await api(`/api/staff/agenda?date=${date}&scope=${clinicScope}`);
  const go = (q) => { const p = new URLSearchParams({ d: date, scope: clinicScope, ...q }); location.hash = `#/agenda?${p}`; };
  let t0 = 8 * 60, t1 = 18 * 60;
  r.columns.forEach((c) => {
    c.windows.forEach(([s, e]) => { t0 = Math.min(t0, s); t1 = Math.max(t1, e); });
    c.appointments.forEach((a) => { t0 = Math.min(t0, toMin(a.time)); t1 = Math.max(t1, toMin(a.time) + a.duration_min); });
  });
  t0 = Math.floor(t0 / 60) * 60; t1 = Math.ceil(t1 / 60) * 60;
  const nrows = (t1 - t0) / 10;
  const multi = (app.me.practices || []).length > 1;
  const labels = [];
  for (let m = t0; m < t1; m += 30) labels.push(m);
  const nowMin = toMin(r.now);
  const showNow = r.date === r.today && nowMin >= t0 && nowMin <= t1;
  const total = r.columns.reduce((s, c) => s + c.appointments.length, 0);
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Agenda</h1><p class="t-small muted">${dateLong(r.date)}${r.date === r.today ? ' · hoje' : ` · ${relDay(r.date, r.today)}`} · ${total} consulta${total === 1 ? '' : 's'}</p></div>
      <button class="iconbtn" type="button" data-act="prev" aria-label="Dia anterior">${icon('chevL')}</button>
      <button class="btn ghost" type="button" data-act="today">Hoje</button>
      <button class="iconbtn" type="button" data-act="next" aria-label="Próximo dia">${icon('chevR')}</button>
      <label class="field" style="flex:0 0 auto"><input type="date" data-pick value="${r.date}" aria-label="Escolher o dia" style="width:140px"></label>
      ${multi ? html`<div class="seg" role="group" aria-label="De quem"><button type="button" data-act="scope" data-scope="me" aria-pressed="${clinicScope === 'me'}">${app.me.role === 'clinician' ? 'A minha' : app.site.practice.name}</button><button type="button" data-act="scope" data-scope="clinic" aria-pressed="${clinicScope === 'clinic'}">A clínica</button></div>` : ''}
      <a class="btn ghost" href="#/horarios">${icon('clock')}Horários</a>
      <button class="btn" type="button" data-act="new">${icon('plus')}Agendar</button>
    </div>
    ${r.columns.map((c, ci) => c.closure ? html`<section class="glass card closed-day">
      <span class="tick">${icon('calendar')}</span>
      <div class="grow" style="min-width:200px"><b style="display:block">Agenda${r.columns.length > 1 ? ` de ${c.practice.name}` : ''} fechada ${closureRange(c.closure)}${c.closure.reason ? ` · ${c.closure.reason}` : ''}</b>
        <span class="t-small muted">Ninguém marca neste dia, nem a família pelo app.${c.appointments.length ? ' As consultas já marcadas continuam: avise as famílias para remarcar.' : ''}</span></div>
      <button class="btn ghost small" type="button" data-act="reopen" data-col="${ci}">Reabrir</button>
    </section>` : '')}
    <section class="glass card">
      <div class="gridbox">
        <div class="daygrid" style="--row:${ROW}px;grid-template-columns:52px repeat(${r.columns.length}, minmax(250px, 1fr));grid-template-rows:56px repeat(${nrows}, ${ROW}px)">
          ${r.columns.map((c, ci) => html`<div class="colhead" style="grid-column:${ci + 2};grid-row:1"><span class="av sm">${initials(c.practice.name)}</span><div class="grow"><b>${c.practice.name}</b><span class="t-small muted">${c.appointments.length} consulta${c.appointments.length === 1 ? '' : 's'}${c.reserved_free.length ? ` · ${c.reserved_free.length} vaga${c.reserved_free.length > 1 ? 's' : ''} livre${c.reserved_free.length > 1 ? 's' : ''}` : ''}</span></div></div>`)}
          ${labels.map((m) => raw(`<span class="tlabel" style="grid-column:1;grid-row:${2 + (m - t0) / 10}">${hhmm(m)}</span>`))}
          ${r.columns.map((c, ci) => html`<div class="lane ${c.closure ? 'closed' : ''}" data-lane="${ci}" style="grid-column:${ci + 2};grid-row:2 / span ${nrows}" title="${c.closure ? 'Agenda fechada neste dia: só encaixe' : 'Toque num horário vazio para agendar'}"></div>`)}
          ${r.columns.map((c, ci) => lanes(c).map((it) => {
            const start = 2 + Math.round((it.s - t0) / 10);
            const span = Math.max(2, Math.round((it.e - it.s) / 10));
            const place = `grid-column:${ci + 2};grid-row:${start} / span ${span}${it.lanes > 1 ? `;justify-self:start;width:calc(100% / ${it.lanes} - 3px);margin-left:calc(100% / ${it.lanes} * ${it.lane})` : ''}`;
            if (it.slot) return html`<button class="appt slot ${span <= 2 ? 'short' : ''} ${it.lanes > 1 ? 'narrow' : ''}" type="button" data-act="slot" data-col="${ci}" data-time="${it.slot.time}" style="${place}"><b>Vaga para criança doente</b><span class="pill">Livre</span></button>`;
            const a = it.a;
            const cls = [a.status === 'atendido' && 'done', a.status === 'em_atendimento' && 'now', a.kind === 'encaixe' && 'squeeze', a.status === 'faltou' && 'miss', span <= 2 && 'short', it.lanes > 1 && 'narrow', c.closure && 'on-closed'].filter(Boolean).join(' ');
            return html`<button class="appt ${cls}" type="button" data-act="appt" data-col="${ci}" data-id="${a.id}" style="${place}" title="${a.patient.name} · ${a.time} · ${a.service} · ${a.status_label}">
              <b>${a.patient.name}, ${a.patient.age_short}${a.kind === 'encaixe' ? ' · encaixe' : ''}</b>${span > 2 ? html`<span class="s">${a.time} · ${a.service}${a.covered ? ' · plano' : ''}</span>` : ''}${apptPill(a)}</button>`;
          }))}
          ${showNow ? raw(`<span class="nowline" style="top:${56 + ((nowMin - t0) / 10) * ROW}px" aria-hidden="true"></span>`) : ''}
        </div>
      </div>
    </section>`);
  view.querySelector('[data-pick]').addEventListener('change', (ev) => ev.target.value && go({ d: ev.target.value }));
  view.querySelectorAll('[data-lane]').forEach((lane) => lane.addEventListener('click', (ev) => {
    const c = r.columns[Number(lane.dataset.lane)];
    const m = t0 + Math.floor((ev.offsetY) / ROW) * 10;
    newAppointment(app, { date: r.date, time: hhmm(m), practiceId: c.practice.id }, refresh);
  }));
  actions(view, {
    prev: () => go({ d: addDays(r.date, -1) }),
    next: () => go({ d: addDays(r.date, 1) }),
    today: () => go({ d: r.today }),
    scope: (el) => go({ scope: el.dataset.scope }),
    new: () => newAppointment(app, { date: r.date }, refresh),
    appt: (el) => openAppointment(app, r.columns[Number(el.dataset.col)].appointments.find((a) => a.id === Number(el.dataset.id)), refresh),
    slot: (el) => newAppointment(app, { date: r.date, time: el.dataset.time, serviceKind: 'sick_visit', practiceId: r.columns[Number(el.dataset.col)].practice.id }, refresh),
    reopen: async (el) => {
      const c = r.columns[Number(el.dataset.col)];
      if (!await ask(`Reabrir a agenda ${closureRange(c.closure)}?`, 'Os horários voltam para a recepção e para o app da família.', 'Reabrir')) return;
      await api(`/api/staff/closures/${c.closure.id}?practice_id=${c.practice.id}`, { method: 'DELETE' });
      toast('Agenda reaberta.'); refresh();
    },
  });
}

// "em 02/11" ou "de 02/11 a 04/11"
export function closureRange(c) {
  return c.start === c.end ? `em ${dateBR(c.start)}` : `de ${dateBR(c.start)} a ${dateBR(c.end)}`;
}

// ---- Recepção -----------------------------------------------------------------------------------------------------------
// o dia que a recepção confirma: amanhã, ou o próximo com consulta (na sexta, a segunda)
function confirmDay(iso, todayIso) {
  return relDay(iso, todayIso) === 'amanhã' ? 'amanhã' : `${weekday(iso)}, ${dateBR(iso)}`;
}

export async function reception(view, params, app) {
  const r = await api('/api/staff/reception');
  const multi = r.practices.length > 1;
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><span class="t-cap">${dateLong(r.date)}</span><h1 class="t-title">${greeting(new Date().toTimeString().slice(0, 5))}, ${shortName(app.me.name)}</h1></div>
      <button class="btn ghost" type="button" data-act="invite-family">${icon('link')}Convidar família</button>
      <button class="btn" type="button" data-act="new">${icon('plus')}Agendar</button>
    </div>
    ${r.practices.map((p, pi) => html`
      ${multi ? html`<h2 class="t-h2" style="margin-top:6px;display:flex;align-items:center;gap:10px"><span class="av sm">${initials(p.practice.name)}</span>${p.practice.name}</h2>` : ''}
      <div class="grid-cards">
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">Na recepção agora</h3><span class="t-small muted">${p.arrivals.length || 'ninguém'}</span></div>
          ${p.arrivals.length ? html`<div style="margin-top:4px">${p.arrivals.map((a) => html`<button class="li arow" type="button" data-act="appt" data-p="${pi}" data-kind="arrivals" data-id="${a.id}" style="padding:12px 0">
            <span class="av sm">${initials(a.patient.name)}</span><span class="grow"><b style="display:block">${a.patient.name}, ${a.patient.age_short}</b><span class="t-small muted">${a.time} · ${a.service}${a.kind === 'encaixe' ? ' · encaixe' : ''}</span></span><span class="pill todo">${a.wait_min} min</span></button>`)}</div>`
            : html`<p class="t-small muted" style="margin-top:8px">Quando alguém chegar, toque na consulta na agenda e marque "Chegou".</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">Receber</h3><span class="t-small muted">${p.to_receive.length ? money(p.to_receive.reduce((s, a) => s + a.price_cents, 0)) : 'nada pendente'}</span></div>
          ${p.to_receive.length ? html`<div style="margin-top:4px">${p.to_receive.map((a) => html`<div class="li"><div class="grow"><b>${a.patient.name}</b><p class="t-small muted">${a.time} · ${a.service}</p></div><span class="t-small" style="font-weight:700">${money(a.price_cents)}</span><button class="btn ghost small" type="button" data-act="appt" data-p="${pi}" data-kind="to_receive" data-id="${a.id}">Receber</button></div>`)}</div>`
            : html`<p class="t-small muted" style="margin-top:8px">As consultas avulsas atendidas aparecem aqui para receber.</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">Confirmar ${confirmDay(p.confirm_date, r.date)}</h3><span class="t-small muted">${p.confirmed} de ${p.confirm.length} confirmada${p.confirm.length === 1 ? '' : 's'}</span></div>
          ${p.confirm.length ? html`<div class="meter" style="margin-top:10px"><i style="width:${Math.round(100 * p.confirmed / p.confirm.length)}%"></i></div>` : ''}
          <div style="margin-top:4px">${p.confirm.filter((a) => a.status === 'agendado').map((a) => html`<div class="li" style="flex-wrap:wrap">
            <div class="grow" style="min-width:150px"><b>${a.patient.name}</b><p class="t-small muted">${a.time} · ${a.service}${a.confirm_asked_at ? ` · pedida ${askedText(a.confirm_asked_at, r.date)}` : ''}</p></div>
            <span class="libtns">${waButton(app, a, 'confirmar', 'WhatsApp')}<button class="btn ghost small" type="button" data-act="confirm" data-p="${pi}" data-id="${a.id}">Confirmar</button></span></div>`)}</div>
          ${!p.confirm.some((a) => a.status === 'agendado') ? html`<p class="t-small muted" style="margin-top:8px">${p.confirm.length ? 'Todas confirmadas.' : 'Nenhuma consulta para confirmar.'}</p>` : ''}
        </section>
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">Busca ativa</h3><span class="t-small muted">${p.outreach.length} puericultura${p.outreach.length === 1 ? '' : 's'} atrasada${p.outreach.length === 1 ? '' : 's'}</span></div>
          ${p.outreach.length ? html`<div style="margin-top:4px">${p.outreach.map((o) => html`<div class="li" style="flex-wrap:wrap"><div class="grow" style="min-width:170px"><b>${o.patient}, ${o.age_short}</b><p class="t-small muted">${o.visit} · ${o.detail}</p>
            ${o.phone ? html`<p class="t-small" style="margin-top:2px">${o.guardian} · <a class="linkbtn" href="tel:${o.phone.replace(/\D/g, '')}" style="white-space:nowrap">${o.phone}</a></p>` : ''}</div>
            <button class="btn ghost small" type="button" data-act="book" data-p="${pi}" data-patient="${o.patient_id}" data-name="${o.patient}">Agendar</button></div>`)}</div>`
            : html`<p class="t-small muted" style="margin-top:8px">Nenhuma criança com a puericultura atrasada.</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">${TO_ISSUE[p.practice.billing_mode] || 'Recibos e notas a emitir'}</h3><span class="t-small muted">${p.invoices.length || 'em dia'}</span></div>
          ${p.invoices.length ? html`<div style="margin-top:4px">${p.invoices.map((c) => html`<div class="li"><div class="grow"><b>${c.patient || c.family}</b><p class="t-small muted">${c.description} · ${dateBR(c.paid_on)}</p></div><span class="t-small" style="font-weight:700">${money(c.amount_cents)}</span><button class="btn ghost small" type="button" data-act="issue" data-p="${pi}" data-id="${c.id}">Emitir</button></div>`)}</div>`
            : html`<p class="t-small muted" style="margin-top:8px">Tudo emitido.</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h3 class="t-h2">Mensalidades em atraso</h3><span class="t-small muted">${p.overdue.length ? money(p.overdue.reduce((s, c) => s + c.amount_cents, 0)) : 'nenhuma'}</span></div>
          ${p.overdue.length ? html`<div style="margin-top:4px">${p.overdue.map((c) => html`<div class="li" style="flex-wrap:wrap"><div class="grow" style="min-width:160px"><b>${c.patient || c.family}</b><p class="t-small muted">${c.description} · venceu ${dateBR(c.due_on)}</p></div><span class="pill late">${Math.round((new Date(r.date) - new Date(c.due_on)) / 86400000)} dias</span><button class="btn ghost small" type="button" data-act="paid" data-p="${pi}" data-id="${c.id}">Recebida</button></div>`)}</div>`
            : html`<p class="t-small muted" style="margin-top:8px">Nenhuma mensalidade atrasada.</p>`}
        </section>
      </div>`)}`);
  bindWhatsApp(view, app, (id) => r.practices.flatMap((p) => p.confirm).find((a) => a.id === id), refresh);
  actions(view, {
    new: () => newAppointment(app, {}, refresh),
    'invite-family': () => inviteFamily(app),
    appt: (el) => openAppointment(app, r.practices[Number(el.dataset.p)][el.dataset.kind].find((a) => a.id === Number(el.dataset.id)), refresh),
    confirm: async (el) => {
      await api(`/api/staff/appointments/${el.dataset.id}/action`, { method: 'POST', body: { action: 'confirmar', practice_id: r.practices[Number(el.dataset.p)].practice.id } });
      toast('Consulta confirmada.'); refresh();
    },
    book: (el) => newAppointment(app, { practiceId: r.practices[Number(el.dataset.p)].practice.id, patient: { id: Number(el.dataset.patient), name: el.dataset.name, first_name: el.dataset.name.split(' ')[0] }, serviceKind: 'well_child', date: addDays(r.date, 1) }, refresh),
    issue: (el) => documentDialog(app, { practiceId: r.practices[Number(el.dataset.p)].practice.id, chargeId: Number(el.dataset.id) }, refresh),
    paid: async (el) => {
      await api(`/api/staff/charges/${el.dataset.id}/pay?practice_id=${r.practices[Number(el.dataset.p)].practice.id}`, { method: 'POST', body: { method: 'pix' } });
      toast('Mensalidade recebida.'); refresh();
    },
  });
}


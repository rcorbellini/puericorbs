// O que as telas da equipe dividem: o diálogo do agendamento (mudar o estado, começar a consulta, receber), marcar
// consulta, cadastrar família e chamar a família no WhatsApp com a mensagem pronta.
import { api, html, raw, icon, dialog, toast, fail, money, dateLong, dateBR, dateFull, statusPill, initials, centsInput, toCents, debounce, isoDate,
  relDay, weekday, firstName, waNumber, waLink, shareLink } from './lib.js';

export const METHODS = { pix: 'PIX', cartao: 'Cartão', dinheiro: 'Dinheiro' };

export function greeting(hhmm) {
  const h = Number(String(hhmm || '12').slice(0, 2));
  return h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite';
}

export const isClinician = (app) => app.me.role === 'clinician';

export function practiceRole(app, practiceId) {
  const p = (app.me.practices || []).find((x) => x.id === practiceId);
  return p ? p.role : app.me.role;
}

// ---- WhatsApp: a mensagem pronta para o responsável; a recepção só confere e aperta enviar ------------------------------
// O WhatsApp abre no celular ou no computador de quem clica: nada sai do Puericorbs sozinho.

function whenText(a, todayIso) {
  const rel = relDay(a.date, todayIso);
  if (rel === 'hoje') return `hoje, às ${a.time}`;
  if (rel === 'amanhã') return `amanhã (${weekday(a.date)}, ${dateBR(a.date)}), às ${a.time}`;
  return `${weekday(a.date)}, ${dateBR(a.date)}, às ${a.time}`;
}

// kind: 'confirmar' (pedir a confirmação) ou 'remarcar' (a agenda fechou ou o horário saiu da grade)
export function waText(app, a, contact, kind) {
  const hi = `Olá, ${firstName(contact.name)}! Aqui é do consultório de ${a.practice?.name || app.site.practice.name}.`;
  const kid = `${a.patient.sex === 'M' ? 'do' : 'da'} ${a.patient.first_name}`;
  if (kind === 'remarcar') return `${hi} Precisamos remarcar a consulta ${kid} (${a.service}) de ${whenText(a, app.today)}. Qual outro dia fica bom para vocês?`;
  return `${hi} A consulta ${kid} (${a.service}) está marcada para ${whenText(a, app.today)}. Você confirma? Se precisar remarcar, é só responder aqui.`;
}

const reachable = (a) => (a.contacts || []).filter((c) => waNumber(c.phone));

// o botão do WhatsApp de um agendamento: um link direto, ou a escolha de quem chamar (mãe, pai…); sem celular, um aviso
export function waButton(app, a, kind, label) {
  const people = reachable(a);
  if (!people.length) return html`<span class="t-small muted">sem celular no cadastro</span>`;
  const attrs = raw(`data-wa="${a.id}" data-kind="${kind}"`);
  if (people.length === 1) return html`<a class="btn ghost small" href="${waLink(people[0].phone, waText(app, a, people[0], kind))}" target="_blank" rel="noopener" ${attrs}>${icon('message')}${label}</a>`;
  return html`<button class="btn ghost small" type="button" ${attrs} data-wa-pick="1">${icon('message')}${label}</button>`;
}

// liga os botões do WhatsApp de `root`: escolher quem chamar e, no pedido de confirmação, deixar registrado que foi
// pedido (a lista mostra "pedido às 14:32"). `find(id)` acha o agendamento; `onAsked` redesenha.
export function bindWhatsApp(root, app, find, onAsked) {
  const asked = (a, kind) => {
    if (kind !== 'confirmar') return;
    api(`/api/staff/appointments/${a.id}/asked`, { method: 'POST', body: { practice_id: a.practice?.id } })
      .then(() => onAsked && setTimeout(onAsked, 400)).catch(fail);
  };
  root.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-wa]');
    if (!el || !root.contains(el)) return;
    const a = find(Number(el.dataset.wa));
    const kind = el.dataset.kind;
    if (!a) return;
    if (!el.dataset.waPick) { asked(a, kind); return; }  // o link segue para o WhatsApp
    const d = dialog({
      title: 'Para quem mandar?',
      body: html`<div class="opts">${reachable(a).map((c) => html`<a class="opt" href="${waLink(c.phone, waText(app, a, c, kind))}" target="_blank" rel="noopener" data-sent style="min-height:56px;text-decoration:none">
        ${icon('message')}<span class="grow"><b>${c.name}</b><span class="t-small muted" style="display:block">${c.relation} · ${c.phone}</span></span>${icon('chevR', 'muted')}</a>`)}</div>`,
    });
    d.el.addEventListener('click', (e2) => { if (e2.target.closest('[data-sent]')) { asked(a, kind); d.close(); } });
  });
}

// as consultas que ficaram para remarcar (a agenda fechou, ou a grade mudou): cada uma com o aviso pronto no WhatsApp
export function rescheduleDialog(app, title, intro, appts, onDone) {
  const d = dialog({
    title,
    body: html`<p class="muted pretty">${intro}</p>
      <div>${appts.map((a) => html`<div class="li" style="flex-wrap:wrap"><span class="av sm">${initials(a.patient.name)}</span>
        <div class="grow" style="min-width:150px"><b style="display:block">${a.patient.name}</b><span class="t-small muted">${dateBR(a.date)} · ${a.time} · ${a.service}</span></div>
        ${waButton(app, a, 'remarcar', 'Avisar')}</div>`)}</div>
      <p class="note" style="padding:0">Elas continuam na agenda até você remarcar ou cancelar.</p>`,
    actions: [{ label: 'Pronto' }],
  });
  bindWhatsApp(d.el, app, (id) => appts.find((x) => x.id === id));
  d.el.addEventListener('close', () => onDone && onDone());
  return d;
}

// o diálogo de um agendamento; `onChange` redesenha a tela de trás
export function openAppointment(app, a, onChange) {
  const pid = a.practice?.id;
  const role = pid ? practiceRole(app, pid) : app.me.role;
  const clin = role === 'clinician';
  const st = a.status;
  const btns = [];
  if (clin && ['agendado', 'confirmado', 'chegou', 'em_atendimento'].includes(st)) {
    btns.push({ act: 'consulta', label: st === 'em_atendimento' ? 'Abrir a consulta' : 'Começar a consulta', kind: '' });
  }
  if (['agendado', 'confirmado'].includes(st)) btns.push({ act: 'chegou', label: 'Chegou', kind: clin ? 'ghost' : '' });
  if (st === 'agendado') btns.push({ act: 'confirmar', label: 'Confirmar', kind: 'ghost' });
  if (st === 'atendido' && !a.covered && !a.paid && a.price_cents > 0) btns.push({ act: 'receber', label: 'Receber', kind: clin ? 'ghost' : '' });
  if (['agendado', 'confirmado'].includes(st)) btns.push({ act: 'faltou', label: 'Faltou', kind: 'ghost' });
  if (['faltou', 'cancelado'].includes(st)) btns.push({ act: 'reabrir', label: 'Reabrir', kind: 'ghost' });
  if (['agendado', 'confirmado', 'chegou'].includes(st)) btns.push({ act: 'cancelar', label: 'Cancelar a consulta', kind: 'danger' });
  const price = a.covered ? 'Incluída no plano' : a.price_cents ? money(a.price_cents) : 'Sem custo';
  const d = dialog({
    title: a.patient.name,
    body: html`
      <div style="display:flex;align-items:center;gap:12px">
        <span class="av lg">${initials(a.patient.name)}</span>
        <div class="grow"><p class="t-h3">${a.service}</p><p class="muted">${dateLong(a.date)}, às ${a.time} · ${a.duration_min} min</p></div>
        ${statusPill(st, a.status_label)}
      </div>
      <div class="rows">
        <div class="row"><span class="lbl">Idade</span><span class="muted">${a.patient.age_short}</span></div>
        <div class="row"><span class="lbl">Valor</span><span class="muted">${price}${a.paid ? ' · pago' : ''}</span></div>
        ${a.kind === 'encaixe' ? html`<div class="row"><span class="lbl">Tipo</span><span class="muted">Encaixe</span></div>` : ''}
        ${a.kind === 'agudo' ? html`<div class="row"><span class="lbl">Tipo</span><span class="muted">Vaga para criança doente</span></div>` : ''}
        ${a.wait_min != null ? html`<div class="row"><span class="lbl">Na espera</span><span class="muted">há ${a.wait_min} min</span></div>` : ''}
        ${a.practice ? html`<div class="row"><span class="lbl">Pediatra</span><span class="muted">${a.practice.name}</span></div>` : ''}
        ${a.confirm_asked_at && st === 'agendado' ? html`<div class="row"><span class="lbl">Confirmação</span><span class="muted">pedida ${askedText(a.confirm_asked_at, app.today)}</span></div>` : ''}
      </div>
      ${st === 'agendado' && a.date >= app.today ? html`<div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px">${waButton(app, a, 'confirmar', 'Pedir confirmação no WhatsApp')}</div>` : ''}
      <div data-receive hidden class="well" style="padding:14px;display:flex;flex-direction:column;gap:10px">
        <div class="seg" role="group" aria-label="Forma de pagamento">${Object.entries(METHODS).map(([k, v], i) => html`<button type="button" data-method="${k}" aria-pressed="${i === 0}">${v}</button>`)}</div>
        <label class="field"><span>R$</span><input data-amount inputmode="decimal" value="${centsInput(a.price_cents)}" aria-label="Valor recebido"></label>
        <button class="btn" type="button" data-act="confirm-receive">Receber</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:10px">${btns.map((b) => html`<button class="btn ${b.kind}" type="button" data-act="${b.act}">${b.label}</button>`)}</div>
      <a class="linkbtn" href="#/paciente/${a.patient.id}${pid && pid !== app.site.practice.id ? `?practice=${pid}` : ''}" data-close>Abrir a ficha de ${a.patient.first_name}</a>`,
  });
  const body = d.el;
  bindWhatsApp(body, app, () => a, onChange);
  const run = async (action) => {
    const r = await api(`/api/staff/appointments/${a.id}/action`, { method: 'POST', body: { action, practice_id: pid } });
    d.close();
    if (r.encounter_id) { location.hash = `#/consulta/${r.encounter_id}`; return; }
    toast({ chegou: 'Chegada registrada.', confirmar: 'Consulta confirmada.', faltou: 'Falta registrada.', cancelar: 'Consulta cancelada.', reabrir: 'Consulta reaberta.' }[action] || 'Pronto.');
    onChange && onChange();
  };
  body.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-act], [data-method]');
    if (!b) return;
    try {
      if (b.dataset.method) {
        body.querySelectorAll('[data-method]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        return;
      }
      const act = b.dataset.act;
      if (act === 'consulta') {
        const r = await api(`/api/staff/appointments/${a.id}/encounter`, { method: 'POST' });
        d.close();
        location.hash = `#/consulta/${r.encounter_id}`;
      } else if (act === 'receber') {
        body.querySelector('[data-receive]').hidden = false;
        b.hidden = true;
      } else if (act === 'confirm-receive') {
        const method = body.querySelector('[data-method][aria-pressed="true"]').dataset.method;
        const amount = toCents(body.querySelector('[data-amount]').value);
        await api(`/api/staff/appointments/${a.id}/receive`, { method: 'POST', body: { method, amount_cents: amount, practice_id: pid } });
        d.close();
        toast(`Recebido ${money(amount)}. A nota fica na fila para emitir.`);
        onChange && onChange();
      } else {
        await run(act);
      }
    } catch (e) { fail(e); }
  });
}

// marcar uma consulta (com o encaixe); `opts`: {date, time, kind, patient, practiceId}
export async function newAppointment(app, opts = {}, onDone) {
  const practices = app.me.practices || [];
  let practiceId = opts.practiceId || app.site.practice.id;
  let patient = opts.patient || null;
  let kind = opts.kind || 'normal';
  let services = [];
  let time = opts.time || null;
  const d = dialog({
    title: kind === 'encaixe' ? 'Encaixe' : 'Agendar',
    body: html`
      ${practices.length > 1 ? html`<div class="seg" role="group" aria-label="Pediatra" data-practices>${practices.map((p) => html`<button type="button" data-practice="${p.id}" aria-pressed="${p.id === practiceId}">${p.name}</button>`)}</div>` : ''}
      <div data-patient></div>
      <div class="rows">
        <label class="row"><span class="lbl">Serviço</span><select class="inline" data-service aria-label="Serviço"></select></label>
        <label class="row"><span class="lbl">Dia</span><input class="inline" type="date" data-date value="${opts.date || app.today}"></label>
        <div class="row"><span class="lbl">Tipo</span><div class="seg" role="group" aria-label="Tipo"><button type="button" data-kind="normal" aria-pressed="${kind === 'normal'}">Na grade</button><button type="button" data-kind="encaixe" aria-pressed="${kind === 'encaixe'}">Encaixe</button></div></div>
      </div>
      <div data-times></div>`,
    actions: [{ label: 'Agendar', run: async (dlg) => {
      if (!patient) throw new Error('Escolha a criança.');
      const t = kind === 'encaixe' ? dlg.querySelector('[data-free-time]')?.value : time;
      if (!t) throw new Error('Escolha o horário.');
      await api('/api/staff/appointments', { method: 'POST', body: {
        patient_id: patient.id, service_id: Number(dlg.querySelector('[data-service]').value), date: dlg.querySelector('[data-date]').value,
        time: t, kind, practice_id: practiceId } });
      toast(`Consulta de ${patient.first_name || patient.name} marcada.`);
      onDone && onDone();
    } }],
  });
  const el = d.el;
  const patientBox = el.querySelector('[data-patient]');
  const renderPatient = () => {
    if (patient) {
      patientBox.innerHTML = String(html`<div class="well" style="display:flex;align-items:center;gap:12px;padding:10px 12px"><span class="av sm">${initials(patient.name)}</span>
        <div class="grow"><b>${patient.name}</b><p class="t-small muted">${patient.age_short || ''}${patient.plan ? ` · ${patient.plan.plan}` : ''}</p></div>
        <button class="linkbtn t-small" type="button" data-act="change">Trocar</button></div>`);
      return;
    }
    patientBox.innerHTML = String(html`<label class="field">${icon('search')}<input data-q placeholder="Buscar criança ou responsável" aria-label="Buscar criança ou responsável" autocomplete="off"></label>
      <div class="opts" data-results style="margin-top:8px"></div>
      <button class="linkbtn t-small" type="button" data-act="new-family" style="margin-top:6px">+ Família nova</button>`);
    const q = patientBox.querySelector('[data-q]');
    const search = debounce(async () => {
      try {
        const r = await api(`/api/staff/patients?q=${encodeURIComponent(q.value)}&practice_id=${practiceId}`);
        patientBox.querySelector('[data-results]').innerHTML = String(html`${r.patients.slice(0, 6).map((p) => html`<button class="opt" type="button" data-pick="${p.id}" style="min-height:52px"><span class="av sm">${initials(p.name)}</span><span class="grow"><b>${p.name}</b><span class="t-small muted" style="display:block">${p.age_short} · ${p.guardians[0]?.name || p.family}</span></span></button>`)}`);
        patientBox._results = r.patients;
      } catch (e) { fail(e); }
    }, 220);
    q.addEventListener('input', search);
    q.focus();
    search();
  };
  const loadServices = async () => {
    const r = await api(`/api/staff/services?practice_id=${practiceId}`);
    services = r.services.filter((s) => s.active);
    const sel = el.querySelector('[data-service]');
    const prefer = opts.serviceKind ? services.find((s) => s.kind === opts.serviceKind) : null;
    sel.innerHTML = String(html`${services.map((s) => html`<option value="${s.id}" ${prefer && prefer.id === s.id ? raw('selected') : ''}>${s.name} · ${s.duration_min} min</option>`)}`);
  };
  const loadTimes = async () => {
    const box = el.querySelector('[data-times]');
    if (kind === 'encaixe') {
      box.innerHTML = String(html`<div class="rows"><label class="row"><span class="lbl">Horário</span><input class="inline" type="time" step="300" data-free-time value="${time || ''}"></label></div><p class="note">O encaixe passa por cima da grade e de quem já está marcado.</p>`);
      return;
    }
    const sid = el.querySelector('[data-service]').value;
    const day = el.querySelector('[data-date]').value;
    if (!sid || !day) return;
    box.innerHTML = '<p class="t-small muted">Procurando horários…</p>';
    try {
      const r = await api(`/api/staff/slots?service_id=${sid}&date=${day}&practice_id=${practiceId}`);
      if (!r.times.some((t) => t.time === time)) time = null;
      box.innerHTML = r.times.length
        ? String(html`<span class="t-cap">Horários livres</span><div class="times" style="margin-top:8px">${r.times.map((t) => html`<button class="time" type="button" data-time="${t.time}" aria-pressed="${t.time === time}">${t.time}</button>`)}</div>`)
        : String(html`<p class="t-small muted">Nenhum horário livre neste dia para este serviço. Tente outro dia ou use o encaixe.</p>`);
    } catch (e) { box.innerHTML = ''; fail(e); }
  };
  el.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-pick],[data-act],[data-kind],[data-time],[data-practice]');
    if (!b) return;
    if (b.dataset.pick) { patient = patientBox._results.find((p) => p.id === Number(b.dataset.pick)); renderPatient(); }
    if (b.dataset.act === 'change') { patient = null; renderPatient(); }
    if (b.dataset.act === 'new-family') { newFamily(app, practiceId, (p) => { patient = p; renderPatient(); }); }
    if (b.dataset.kind) { kind = b.dataset.kind; el.querySelectorAll('[data-kind]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); loadTimes(); }
    if (b.dataset.time) { time = b.dataset.time; el.querySelectorAll('[data-time]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }
    if (b.dataset.practice) {
      practiceId = Number(b.dataset.practice); patient = null;
      el.querySelectorAll('[data-practice]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      renderPatient(); await loadServices(); loadTimes();
    }
  });
  el.querySelector('[data-service]').addEventListener('change', loadTimes);
  el.querySelector('[data-date]').addEventListener('change', loadTimes);
  renderPatient();
  try { await loadServices(); await loadTimes(); } catch (e) { fail(e); }
}

export function newFamily(app, practiceId, onDone) {
  dialog({
    title: 'Família nova',
    body: html`
      <span class="t-cap">Responsável</span>
      <div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="gname" autocomplete="off"></label>
        <label class="row"><span class="lbl">É</span><select class="inline" data-f="relation"><option>mãe</option><option>pai</option><option>avó</option><option>avô</option><option>responsável</option></select></label>
        <label class="row"><span class="lbl">Telefone</span><input class="inline" data-f="phone" inputmode="tel"></label>
        <label class="row"><span class="lbl">E-mail</span><input class="inline" data-f="email" type="email" placeholder="para entrar no app"></label>
      </div>
      <span class="t-cap">Criança</span>
      <div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="cname" autocomplete="off"></label>
        <div class="row"><span class="lbl">Sexo</span><div class="seg" role="group" aria-label="Sexo"><button type="button" data-sex="F" aria-pressed="true">Menina</button><button type="button" data-sex="M" aria-pressed="false">Menino</button></div></div>
        <label class="row"><span class="lbl">Nascimento</span><input class="inline" type="date" data-f="birth" max="${app.today}"></label>
        <label class="row"><span class="lbl">Semanas de gestação</span><input class="inline" data-f="ga" inputmode="numeric" placeholder="se nasceu antes de 37"></label>
      </div>
      <p class="note">As curvas da OMS são separadas por sexo, e a idade corrigida do prematuro sai das semanas de gestação.</p>`,
    onMount: (dlg) => dlg.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-sex]');
      if (b) dlg.querySelectorAll('[data-sex]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    }),
    actions: [{ label: 'Cadastrar', run: async (dlg) => {
      const v = (k) => dlg.querySelector(`[data-f="${k}"]`).value.trim();
      if (!v('gname') || !v('cname') || !v('birth')) throw new Error('Preencha o nome do responsável, o da criança e o nascimento.');
      const r = await api('/api/staff/families', { method: 'POST', body: {
        practice_id: practiceId,
        guardian: { name: v('gname'), relation: v('relation'), phone: v('phone') || null, email: v('email') || null },
        child: { name: v('cname'), sex: dlg.querySelector('[data-sex][aria-pressed="true"]').dataset.sex, birth_date: v('birth'), gestational_weeks: v('ga') ? Number(v('ga')) : null },
      } });
      toast('Família cadastrada.');
      onDone && onDone({ id: r.patient_id, name: v('cname'), first_name: v('cname').split(' ')[0] });
    } }],
  });
}

// "às 14:32" (hoje) ou "em 27/10, às 14:32"
export function askedText(iso, todayIso) {
  const time = iso.slice(11, 16);
  return iso.slice(0, 10) === todayIso ? `às ${time}` : `em ${dateBR(iso)}, às ${time}`;
}

// ---- o recibo (pessoa física, Receita Saúde) ou a nota (empresa) de um pagamento ------------------------------------
// Os dados prontos para copiar, onde emitir e o PDF, que vai para os arquivos da família (ela vê no app).
const plainMoney = (cents) => centsInput(cents);
const listPT = (xs) => (xs.length > 1 ? `${xs.slice(0, -1).join(', ')} e ${xs[xs.length - 1]}` : xs[0] || '');
const DOC_TITLE = { pf: 'O recibo do Receita Saúde', pj: 'A nota fiscal' };

export async function documentDialog(app, { practiceId, chargeId }, onDone) {
  const qs = practiceId ? `?practice_id=${practiceId}` : '';
  let doc = await api(`/api/staff/charges/${chargeId}/document${qs}`);
  const d = dialog({ title: DOC_TITLE[doc.profile.mode] || 'O recibo ou a nota', body: html`<div data-doc style="display:flex;flex-direction:column;gap:14px"></div>`, wide: true });
  const box = d.el.querySelector('[data-doc]');
  const nota = () => doc.profile.mode === 'pj';
  // o nome do campo em cima, o valor embaixo: no celular, o valor fica com a largura toda
  const copyRow = (label, value) => html`<div class="row"><span class="lbl" style="overflow-wrap:anywhere"><span class="sub">${label}</span>${value}</span>
    <button class="iconbtn small" type="button" data-copy="${value}" aria-label="Copiar ${label.toLowerCase()}" title="Copiar">${icon('copy')}</button></div>`;
  const cpfRow = (label, who, kind) => (who.cpf ? copyRow(label, who.cpf)
    : html`<div class="row" style="display:block;padding-top:10px;padding-bottom:12px">
      <span class="sub">${label} · <span style="color:var(--todo);font-weight:600">falta no cadastro</span></span>
      <span style="display:flex;gap:8px;margin-top:8px"><label class="field" style="flex:1;min-height:40px"><input data-cpf="${kind}" data-id="${who.id}" inputmode="numeric" autocomplete="off" placeholder="000.000.000-00" aria-label="${label}"></label>
      <button class="btn ghost small" type="button" data-save="${kind}">Salvar</button></span></div>`);
  const draw = (done = false) => {
    const p = doc.profile;
    const notice = `Olá${doc.payer ? `, ${firstName(doc.payer.name)}` : ''}! ${nota() ? 'A nota fiscal' : 'O recibo'} do pagamento de ${dateBR(doc.paid_on)} (${doc.service}, ${money(doc.amount_cents)}) já está no app, em Arquivos.`;
    box.innerHTML = String(done ? html`
      <p class="t-h3">${nota() ? 'A nota está' : 'O recibo está'} no app da família, em Arquivos.</p>
      <p class="muted pretty">O pagamento saiu da lista do que falta emitir.</p>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        ${doc.payer && waNumber(doc.payer.phone) ? html`<a class="btn" href="${waLink(doc.payer.phone, notice)}" target="_blank" rel="noopener">${icon('message')}Avisar ${firstName(doc.payer.name)} no WhatsApp</a>` : ''}
        <button class="btn ghost" type="button" data-close>Fechar</button></div>` : html`
      <div><p class="t-h3">${money(doc.amount_cents)} · pago em ${dateBR(doc.paid_on)}</p><p class="muted">${doc.description}</p></div>
      ${!p.mode ? html`<p class="pill todo long">${icon('alert')}A pediatra ainda não disse como recebe (em Consultório): pessoa física, com o recibo do Receita Saúde, ou empresa, com a nota fiscal.</p>`
        : doc.missing.length ? html`<p class="pill todo long">${icon('alert')}Falta ${listPT(doc.missing)}.</p>` : ''}
      <div class="rows">
        ${doc.payer ? html`${copyRow('Quem pagou', doc.payer.name)}${cpfRow('CPF de quem pagou', doc.payer, 'payer')}` : ''}
        ${doc.child ? html`${copyRow('Quem foi atendido', doc.child.name)}${p.mode !== 'pj' ? cpfRow('CPF da criança', doc.child, 'child') : ''}` : ''}
        ${copyRow('Valor', plainMoney(doc.amount_cents))}
        ${copyRow('Data do pagamento', dateFull(doc.paid_on))}
        ${copyRow('Descrição', doc.description)}
        ${nota() ? copyRow('Código do serviço', doc.service_code) : ''}
      </div>
      ${p.portal ? html`<div style="display:flex;flex-direction:column;gap:8px"><a class="btn ghost" href="${p.portal.url}" target="_blank" rel="noopener" style="align-self:flex-start">${icon('link')}Abrir ${p.portal.name}</a>
        <p class="t-small muted pretty">${p.portal.how}${p.mode === 'pf' ? ' A recepção pode emitir em nome da pediatra com uma procuração eletrônica no e-CAC.' : ''}</p></div>` : ''}
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px">
        <label class="btn">${icon('upload')}Anexar o PDF ${nota() ? 'da nota' : 'do recibo'}<input type="file" accept="application/pdf,image/*" data-file hidden></label>
        <button class="linkbtn t-small" type="button" data-plain>Já emiti, sem anexar</button>
      </div>`);
  };
  draw();
  box.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-copy], [data-save], [data-plain]');
    if (!b) return;
    try {
      if (b.dataset.copy !== undefined) {
        try { await navigator.clipboard.writeText(b.dataset.copy); toast('Copiado.'); } catch { toast('Não deu para copiar: selecione e copie.', 'err'); }
      } else if (b.dataset.save) {
        const input = box.querySelector(`[data-cpf="${b.dataset.save}"]`);
        const path = b.dataset.save === 'payer' ? `guardians/${input.dataset.id}` : `patients/${input.dataset.id}`;
        await api(`/api/staff/${path}/cpf${qs}`, { method: 'PUT', body: { cpf: input.value } });
        doc = await api(`/api/staff/charges/${chargeId}/document${qs}`);
        draw();
      } else if (b.dataset.plain !== undefined) {
        await api(`/api/staff/charges/${chargeId}/invoice${qs}`, { method: 'POST', body: { status: 'emitida' } });
        toast(nota() ? 'Nota marcada como emitida.' : 'Recibo marcado como emitido.');
        d.close();
        if (onDone) onDone();
      }
    } catch (e) { fail(e); }
  });
  box.addEventListener('change', async (ev) => {
    const input = ev.target.closest('[data-file]');
    if (!input || !input.files[0]) return;
    const form = new FormData();
    form.append('upload', input.files[0]);
    try {
      await api(`/api/staff/charges/${chargeId}/document${qs}`, { method: 'POST', form });
      draw(true);
      if (onDone) onDone();
    } catch (e) { fail(e); input.value = ''; }
  });
  return d;
}

// o convite de uma família que ainda não está no cadastro: quem convida escreve o que já sabe (tudo opcional), e a
// família confere e completa no celular; a ficha nasce quando ela aceita
export function inviteFamily(app, { practiceId } = {}, onDone) {
  const practices = app.me.practices || [];
  let pid = practiceId || app.site.practice.id;
  let sex = '';
  const d = dialog({
    title: 'Convidar uma família',
    body: html`<p class="muted pretty">Escreva o que você já sabe. A família confere e completa o resto no celular, e a ficha nasce quando ela aceitar.</p>
      ${practices.length > 1 ? html`<div class="seg" role="group" aria-label="Pediatra">${practices.map((p) => html`<button type="button" data-practice="${p.id}" aria-pressed="${p.id === pid}">${p.name}</button>`)}</div>` : ''}
      <span class="t-cap">Responsável</span>
      <div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="name" autocomplete="off"></label>
        <label class="row"><span class="lbl">É</span><select class="inline" data-f="relation"><option value="">—</option><option>mãe</option><option>pai</option><option>avó</option><option>avô</option><option>responsável</option></select></label>
        <label class="row"><span class="lbl">Celular<span class="sub">para mandar no WhatsApp</span></span><input class="inline" data-f="phone" inputmode="tel"></label>
        <label class="row"><span class="lbl">E-mail</span><input class="inline" data-f="email" type="email"></label>
      </div>
      <span class="t-cap">Criança</span>
      <div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="child_name" autocomplete="off"></label>
        <div class="row"><span class="lbl">Sexo</span><div class="seg" role="group" aria-label="Sexo"><button type="button" data-sex="F" aria-pressed="false">Menina</button><button type="button" data-sex="M" aria-pressed="false">Menino</button></div></div>
        <label class="row"><span class="lbl">Nascimento</span><input class="inline" type="date" data-f="child_birth" max="${app.today}"></label>
      </div>`,
    onMount: (dlg) => dlg.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-sex], [data-practice]');
      if (!b) return;
      if (b.dataset.practice) {
        pid = Number(b.dataset.practice);
        dlg.querySelectorAll('[data-practice]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        return;
      }
      sex = sex === b.dataset.sex ? '' : b.dataset.sex;  // tocar de novo desmarca: a família escolhe
      dlg.querySelectorAll('[data-sex]').forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.sex === sex)));
    }),
    actions: [{ label: 'Cancelar', kind: 'ghost' }, { label: 'Gerar o convite', run: async (dlg) => {
      const v = (k) => dlg.querySelector(`[data-f="${k}"]`).value.trim() || null;
      const x = await api('/api/staff/family-invites', { method: 'POST', body: {
        practice_id: pid, name: v('name'), relation: v('relation'), phone: v('phone'), email: v('email'),
        child_name: v('child_name'), child_sex: sex || null, child_birth: v('child_birth') } });
      shareLink({ title: 'Convite para a família', link: x.link, text: x.text, phone: x.phone, qr: x.qr,
        note: 'Vale 7 dias e uma vez só. A ficha da criança nasce quando a família aceitar.' })
        .el.addEventListener('close', () => onDone && onDone());
    } }],
  });
  return d;
}

export function nav(hash) { location.hash = hash; }

export function weekdayShort(iso) { return ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'][new Date(`${iso}T12:00`).getDay()]; }
export { isoDate, dateBR };

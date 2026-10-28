// As crianças: a lista, a ficha (linha do cuidado, curvas, vacinas, marcos, consultas, arquivos, agenda), a consulta e
// a caixa de revisão. A atendente vê a ficha sem nada clínico: o servidor já manda assim.
import { api, html, raw, icon, toast, fail, dialog, ask, money, dateLong, dateBR, dateFull, initials, statusPill, fileIcon,
  ago, actions, debounce, careTick, carePill, relDay } from './lib.js';
import { growthChart, bindGrowth, growthTable } from './charts.js';
import { newAppointment, newFamily, isClinician } from './staff-common.js';
import { setCount, refresh } from './staff.js';

const SEX = { F: 'menina', M: 'menino' };
const KIND_LABEL = { exame: 'Exame', tarefa: 'Tarefa', orientacao: 'Orientação', retorno: 'Retorno' };

// ---- a lista --------------------------------------------------------------------------------------------------------
export async function patients(view, params, app) {
  const practices = app.me.practices || [];
  const practiceId = Number(params.query.practice) || app.site.practice.id;
  let q = params.query.q || '';
  const title = isClinician(app) ? 'Pacientes' : 'Famílias';
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">${title}</h1><p class="t-small muted" data-count></p></div>
      ${practices.length > 1 ? html`<div class="seg" role="group" aria-label="Consultório">${practices.map((p) => html`<button type="button" data-act="practice" data-id="${p.id}" aria-pressed="${p.id === practiceId}">${p.name}</button>`)}</div>` : ''}
      <button class="btn" type="button" data-act="new">${icon('plus')}Família nova</button>
    </div>
    <label class="field">${icon('search')}<input data-q type="search" value="${q}" placeholder="Buscar pelo nome da criança, do responsável ou pelo telefone" aria-label="Buscar"></label>
    <section class="glass card" style="padding:8px 14px" data-list><p class="loading" style="min-height:120px">Carregando…</p></section>`);
  const list = view.querySelector('[data-list]');
  const load = async () => {
    const r = await api(`/api/staff/patients?q=${encodeURIComponent(q)}&practice_id=${practiceId}`);
    view.querySelector('[data-count]').textContent = `${r.patients.length} criança${r.patients.length === 1 ? '' : 's'}${q ? ` com “${q}”` : ''} · ${r.practice.name}`;
    list.innerHTML = r.patients.length ? String(html`${r.patients.map((p) => html`
      <a class="arow" href="#/paciente/${p.id}${practiceId !== app.site.practice.id ? `?practice=${practiceId}` : ''}">
        <span class="who2" style="flex:1 1 260px"><span class="av sm">${initials(p.name)}</span><span style="min-width:0"><b style="display:block">${p.name}</b><span class="t-small muted">${p.age} · ${p.guardians[0] ? `${p.guardians[0].name}${p.guardians[0].phone ? ` · ${p.guardians[0].phone}` : ''}` : p.family}</span></span></span>
        <span class="svc" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">
          ${p.allergies ? html`<span class="pill late">${icon('alert')}Alergia</span>` : ''}
          ${p.plan ? html`<span class="pill">${p.plan.plan}</span>` : ''}
          ${p.next_visit ? html`<span class="pill ${p.next_visit.status === 'atrasado' ? 'late' : p.next_visit.status === 'agendado' ? 'booked' : ''}">${p.next_visit.title}${p.next_visit.status === 'atrasado' ? ' · atrasada' : p.next_visit.status === 'agendado' ? ' · agendada' : ''}</span>` : ''}
        </span>
        ${icon('chevR', 'muted')}
      </a>`)}`) : String(html`<div class="empty"><b>Ninguém encontrado.</b>Confira o nome ou cadastre a família.</div>`);
  };
  view.querySelector('[data-q]').addEventListener('input', debounce((ev) => { q = ev.target.value.trim(); load().catch(fail); }, 250));
  actions(view, {
    new: () => newFamily(app, practiceId, (p) => { location.hash = `#/paciente/${p.id}${practiceId !== app.site.practice.id ? `?practice=${practiceId}` : ''}`; }),
    practice: (el) => { location.hash = `#/pacientes?practice=${el.dataset.id}`; },
  });
  await load();
}

// ---- a ficha ----------------------------------------------------------------------------------------------------------
export async function patient(view, params, app) {
  const practiceId = params.query.practice ? Number(params.query.practice) : null;
  const qs = practiceId ? `?practice_id=${practiceId}` : '';
  const r = await api(`/api/staff/patients/${params.id}${qs}`);
  const p = r.patient;
  const tabs = r.clinical
    ? [['cuidado', 'Linha do cuidado'], ['curvas', 'Curvas'], ['vacinas', 'Vacinas'], ['marcos', 'Marcos'], ['consultas', 'Consultas'], ['arquivos', 'Arquivos'], ['agenda', 'Agenda']]
    : [['agenda', 'Agenda'], ['arquivos', 'Arquivos'], ['cobrancas', 'Cobranças']];
  const tab = tabs.some((t) => t[0] === params.query.tab) ? params.query.tab : tabs[0][0];
  const birth = r.clinical && (p.gestational_weeks || p.birth_weight_g)
    ? `nasceu ${p.gestational_weeks ? `com ${p.gestational_weeks} semanas` : ''}${p.birth_weight_g ? ` e ${p.birth_weight_g.toLocaleString('pt-BR')} g` : ''}${p.birth_type ? ` · ${p.birth_type}` : ''}` : '';
  view.innerHTML = String(html`
    <div class="topbar"><a class="linkbtn" href="#/pacientes${practiceId ? `?practice=${practiceId}` : ''}" style="display:inline-flex;align-items:center;gap:4px">${icon('chevL')}${isClinician(app) ? 'Pacientes' : 'Famílias'}</a></div>
    <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px 18px">
        <span class="av xl">${initials(p.name)}</span>
        <div class="grow" style="display:flex;flex-direction:column;gap:4px;min-width:240px">
          <h1 class="t-title">${p.name}</h1>
          <p class="muted">${p.age} (${dateFull(p.birth_date)}) · ${SEX[p.sex]}${birth ? ` · ${birth}` : ''}</p>
        </div>
        ${r.clinical ? html`<button class="btn ghost" type="button" data-act="edit">Editar a ficha</button>` : ''}
        <button class="btn" type="button" data-act="book">${icon('calendar')}Agendar</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        ${p.allergies ? html`<span class="pill late long">${icon('alert')}${p.allergies}</span>` : ''}
        ${p.conditions ? html`<span class="pill strong long">${p.conditions}</span>` : ''}
        ${p.plan ? html`<span class="pill long">Plano ${p.plan.plan} · ${p.plan.summary}</span>` : ''}
        ${p.guardians.map((g) => html`<span class="pill long">${g.name} (${g.relation})${g.phone ? ` · ${g.phone}` : ''}</span>`)}
      </div>
      <div class="seg" role="group" aria-label="Ficha de ${p.first_name}">${tabs.map(([k, label]) => html`<button type="button" data-act="tab" data-tab="${k}" aria-pressed="${k === tab}">${label}</button>`)}</div>
    </section>
    <div data-tab-body></div>`);
  const body = view.querySelector('[data-tab-body]');
  const go = (t) => { location.hash = `#/paciente/${params.id}?${new URLSearchParams({ ...(practiceId ? { practice: practiceId } : {}), tab: t })}`; };
  actions(view, {
    tab: (el) => go(el.dataset.tab),
    book: () => newAppointment(app, { patient: { id: p.id, name: p.name, first_name: p.first_name, age_short: p.age_short, plan: p.plan }, practiceId: practiceId || undefined, serviceKind: 'well_child' }, refresh),
    edit: () => editPatient(p, refresh),
  });
  await TABS[tab](body, r, app, refresh);
}

const TABS = {
  async cuidado(body, r, app, refresh) {
    const t = r.timeline;
    const row = (i) => html`<div class="li">
      ${careTick(i)}
      <div class="grow"><b>${i.title}</b><div class="meta">${carePill(i, app.today)}${i.detail ? html`<span class="t-small muted">${i.status === 'feito' ? `${dateBR(i.date)} · ` : ''}${i.detail}</span>` : i.status === 'feito' && i.date ? html`<span class="t-small muted">${dateBR(i.date)}</span>` : ''}</div></div>
      ${i.refs.care_item_id && i.status !== 'feito' ? html`<button class="linkbtn t-small" type="button" data-act="ci-done" data-id="${i.refs.care_item_id}">Feito</button><button class="linkbtn t-small" type="button" data-act="ci-drop" data-id="${i.refs.care_item_id}">Dispensar</button>` : ''}
    </div>`;
    body.innerHTML = String(html`<div class="cols">
      <section class="glass card colmain">
        <div class="phead"><h2 class="t-h2">A fazer</h2><button class="btn ghost small" type="button" data-act="add">${icon('plus')}Pedir ou orientar</button></div>
        <div style="margin-top:4px">${t.todo.length ? t.todo.map(row) : html`<p class="empty">Nada pendente.</p>`}</div>
      </section>
      <section class="glass card colside">
        <div class="phead"><h2 class="t-h2">Feito</h2><span class="t-small muted">${t.done.length} registro${t.done.length === 1 ? '' : 's'}</span></div>
        <div style="margin-top:4px">${t.done.slice(0, 14).map(row)}</div>
      </section></div>`);
    actions(body, {
      add: () => addCareItem(r.patient, null, refresh),
      'ci-done': async (el) => { await api(`/api/staff/care-items/${el.dataset.id}`, { method: 'POST', body: { status: 'feito' } }); toast('Marcado como feito.'); refresh(); },
      'ci-drop': async (el) => { await api(`/api/staff/care-items/${el.dataset.id}`, { method: 'POST', body: { status: 'dispensado' } }); refresh(); },
    });
  },

  async curvas(body, r, app, refresh) {
    let indicator = 'wfa';
    let table = false;
    const draw = async () => {
      const chart = await api(`/api/staff/patients/${r.patient.id}/chart?indicator=${indicator}`);
      body.innerHTML = String(html`<section class="glass card" style="display:flex;flex-direction:column;gap:10px">
        <div class="phead center"><h2 class="t-h2">Crescimento</h2>
          <div class="seg" role="group" aria-label="Medida">${[['wfa', 'Peso'], ['lhfa', 'Comprimento'], ['hcfa', 'Perímetro cefálico']].map(([k, l]) => html`<button type="button" data-act="ind" data-k="${k}" aria-pressed="${k === indicator}">${l}</button>`)}</div></div>
        ${chart.latest ? html`<p><span class="t-title">${chart.latest.value.toLocaleString('pt-BR')} ${chart.unit}</span> <span class="muted">em ${dateFull(chart.latest.date)} · ${chart.latest.pct} · ${chart.latest.reading}</span></p>` : html`<p class="muted">Ainda sem medidas.</p>`}
        ${growthChart(chart, { name: r.patient.first_name, wide: window.innerWidth >= 900 })}
        <div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:center">
          <button class="btn ghost small" type="button" data-act="measure">${icon('plus')}Registrar medida</button>
          <button class="linkbtn t-small" type="button" data-act="table">${table ? 'Esconder a tabela' : 'Ver tabela'}</button></div>
        ${table ? growthTable(chart) : ''}
      </section>`);
      bindGrowth(body, chart);
    };
    actions(body, {
      ind: (el) => { indicator = el.dataset.k; draw().catch(fail); },
      table: () => { table = !table; draw().catch(fail); },
      measure: () => addMeasure(r.patient, app, () => draw().catch(fail)),
    });
    await draw();
  },

  async vacinas(body, r, app, refresh) {
    const groups = [];
    r.vaccines.forEach((v) => { let g = groups.find((x) => x.name === v.group); if (!g) groups.push(g = { name: v.group, items: [] }); g.items.push(v); });
    const pill = (v) => v.status === 'feito' ? html`<span class="pill ok">${icon('check')}${dateBR(v.applied_on)}</span>`
      : v.status === 'atrasado' ? html`<span class="pill late">Atrasada</span>` : v.status === 'pendente' ? html`<span class="pill todo">A partir de ${dateBR(v.due)}</span>` : html`<span class="pill">${dateBR(v.due)}</span>`;
    body.innerHTML = String(html`<section class="glass card">
      <div class="phead"><h2 class="t-h2">Caderneta de vacinação</h2><span class="t-small muted">calendário do PNI · ${r.vaccines.filter((v) => v.status === 'feito').length} doses aplicadas</span></div>
      ${groups.map((g) => html`<div class="vgroup" style="margin-top:12px"><span class="t-cap">Vacinas ${g.name}</span>
        <div>${g.items.map((v) => html`<div class="li"><span class="tick">${icon(v.status === 'feito' ? 'check' : 'syringe')}</span>
          <div class="grow"><b>${v.vaccine}</b> <span class="muted">· ${v.dose}</span>${v.lot || v.place ? html`<p class="t-small muted">${[v.place, v.lot && `lote ${v.lot}`].filter(Boolean).join(' · ')}</p>` : ''}</div>
          ${pill(v)}
          ${v.status === 'feito' ? html`<button class="linkbtn t-small" type="button" data-act="undo" data-code="${v.code}">Desfazer</button>` : html`<button class="btn ghost small" type="button" data-act="apply" data-code="${v.code}" data-name="${v.vaccine} · ${v.dose}">Registrar</button>`}
        </div>`)}</div></div>`)}
    </section>`);
    actions(body, {
      apply: (el) => dialog({
        title: `Registrar ${el.dataset.name}`,
        body: html`<div class="rows"><label class="row"><span class="lbl">Aplicada em</span><input class="inline" type="date" data-d value="${app.today}" max="${app.today}"></label>
          <label class="row"><span class="lbl">Lote</span><input class="inline" data-lot></label>
          <label class="row"><span class="lbl">Local</span><input class="inline" data-place value="Clínica Girassol"></label></div>`,
        actions: [{ label: 'Registrar', run: async (dlg) => {
          await api(`/api/staff/patients/${r.patient.id}/immunizations`, { method: 'POST', body: { code: el.dataset.code, applied_on: dlg.querySelector('[data-d]').value, lot: dlg.querySelector('[data-lot]').value || null, place: dlg.querySelector('[data-place]').value || null } });
          toast('Vacina registrada.'); refresh();
        } }],
      }),
      undo: async (el) => {
        if (!await ask('Desfazer o registro desta dose?', 'A dose volta a aparecer como a fazer.', 'Desfazer', true)) return;
        await api(`/api/staff/patients/${r.patient.id}/immunizations/${el.dataset.code}`, { method: 'DELETE' });
        refresh();
      },
    });
  },

  async marcos(body, r, app, refresh) {
    const m = r.milestones;
    body.innerHTML = String(html`<section class="glass card" style="display:flex;flex-direction:column;gap:14px">
      <div class="phead"><h2 class="t-h2">Marcos do desenvolvimento</h2><span class="t-small muted">a família também marca em casa</span></div>
      ${m.bands.slice().reverse().map((b) => html`<div class="group"><span class="t-cap">${b.title}${b.current ? ' · agora' : ''}</span>
        <div class="rows">${b.items.map((it) => html`<label class="row"><span class="lbl">${it.label}${it.checked ? html`<span class="sub">${dateBR(it.achieved_on)}${it.marked_by ? ` · ${it.marked_by}` : ' · conferido na consulta'}</span>` : ''}</span>
          <input class="switch" type="checkbox" data-ms="${it.code}" ${it.checked ? raw('checked') : ''} aria-label="${it.label}"></label>`)}</div></div>`)}
      <p class="t-small muted pretty">Cada criança tem o seu tempo: o marco é uma conversa com a família, não uma prova.</p>
    </section>`);
    body.addEventListener('change', async (ev) => {
      const sw = ev.target.closest('[data-ms]');
      if (!sw) return;
      try { await api(`/api/staff/patients/${r.patient.id}/milestones`, { method: 'POST', body: { code: sw.dataset.ms, checked: sw.checked } }); }
      catch (e) { sw.checked = !sw.checked; fail(e); }
    });
  },

  async consultas(body, r) {
    body.innerHTML = String(html`<section class="glass card">
      <div class="phead"><h2 class="t-h2">Consultas registradas</h2><span class="t-small muted">${r.encounters.length}</span></div>
      ${r.encounters.length ? r.encounters.map((e) => html`<div class="li top">
        <span class="tick">${icon('stetho')}</span>
        <div class="grow" style="display:flex;flex-direction:column;gap:4px">
          <b>${e.service || 'Consulta'} · ${dateFull(e.started_at)}</b>
          ${e.cid ? html`<span class="t-small">${e.cid}</span>` : ''}
          ${e.conduct ? html`<span class="t-small muted">Conduta: ${e.conduct}</span>` : ''}
          ${e.family_summary ? html`<span class="quote">${e.summary_released ? 'Resumo liberado para a família' : 'Resumo ainda não liberado'}: “${e.family_summary}”</span>` : ''}
        </div>
        ${e.status === 'aberta' ? html`<a class="btn ghost small" href="#/consulta/${e.id}">Continuar</a>` : html`<a class="linkbtn t-small" href="#/consulta/${e.id}">Abrir</a>`}
      </div>`) : html`<p class="empty">Nenhuma consulta registrada ainda.</p>`}
    </section>`);
  },

  async arquivos(body, r, app, refresh) {
    body.innerHTML = String(html`<section class="glass card">
      <div class="phead"><h2 class="t-h2">Arquivos</h2><button class="btn ghost small" type="button" data-act="upload">${icon('upload')}Enviar arquivo</button></div>
      ${r.files.length ? r.files.map((f) => html`<div class="li top">
        <span class="tick sq">${icon(fileIcon(f.kind))}</span>
        <div class="grow"><b>${f.title}</b><p class="t-small muted">${f.kind_label} · ${f.uploader_name || f.uploader_role} · ${dateFull(f.created_at)}${f.visibility === 'internal' ? ' · só no prontuário' : ''}</p>
          ${f.note ? html`<p class="quote">“${f.note}”</p>` : ''}
          ${f.review_note ? html`<p class="quote">Revisão: ${f.review_note}</p>` : f.needs_review && !f.reviewed_at ? html`<p style="margin-top:6px"><span class="pill todo">Esperando a revisão</span></p>` : ''}</div>
        <a class="linkbtn t-small" href="/api/files/${f.id}" target="_blank" rel="noopener">Abrir</a>
      </div>`) : html`<p class="empty">Nenhum arquivo ainda.</p>`}
    </section>`);
    actions(body, { upload: () => staffUpload(r, app, refresh) });
  },

  async agenda(body, r, app) {
    const now = `${app.today}T00:00`;
    const next = r.appointments.filter((a) => a.start_at >= now && !['cancelado', 'faltou', 'atendido'].includes(a.status)).reverse();
    const past = r.appointments.filter((a) => !next.includes(a)).slice(0, 25);
    const item = (a) => html`<div class="li"><span class="tick">${icon('calendar')}</span><div class="grow"><b>${a.service}</b><p class="t-small muted">${dateLong(a.date)}, às ${a.time}${a.covered ? ' · plano' : a.price_cents ? ` · ${money(a.price_cents)}` : ''}</p></div>${statusPill(a.status, a.status_label)}</div>`;
    body.innerHTML = String(html`<div class="cols">
      <section class="glass card colmain"><div class="phead"><h2 class="t-h2">Próximas consultas</h2></div>${next.length ? next.map(item) : html`<p class="empty">Nenhuma consulta marcada.</p>`}</section>
      <section class="glass card colside"><div class="phead"><h2 class="t-h2">Histórico</h2></div>${past.length ? past.map(item) : html`<p class="empty">Sem histórico.</p>`}</section></div>`);
  },

  async cobrancas(body, r) {
    body.innerHTML = String(html`<section class="glass card"><div class="phead"><h2 class="t-h2">Cobranças</h2></div>
      ${r.charges.length ? html`<div class="tblbox"><table class="tbl"><thead><tr><th>Vencimento</th><th>O quê</th><th class="r">Valor</th><th>Situação</th><th>Nota</th></tr></thead><tbody>
        ${r.charges.map((c) => html`<tr><td class="num">${dateBR(c.due_on)}</td><td>${c.description}</td><td class="r">${money(c.amount_cents)}</td><td>${c.status === 'paga' ? html`<span class="pill ok">Paga</span>` : c.due_on < r.charges[0].due_on ? html`<span class="pill late">Em aberto</span>` : html`<span class="pill todo">Em aberto</span>`}</td><td>${c.invoice === 'emitida' ? 'Emitida' : c.invoice === 'emitir' ? 'Emitir' : '—'}</td></tr>`)}
      </tbody></table></div>` : html`<p class="empty">Nenhuma cobrança.</p>`}</section>`);
  },
};

function editPatient(p, done) {
  dialog({
    title: `Ficha de ${p.first_name}`,
    body: html`<div class="group"><label class="t-cap" for="ed-al">Alergias</label><textarea class="area" id="ed-al" data-f="allergies" rows="2">${p.allergies || ''}</textarea></div>
      <div class="group"><label class="t-cap" for="ed-co">Condições crônicas e remédios em uso</label><textarea class="area" id="ed-co" data-f="conditions" rows="2">${p.conditions || ''}</textarea></div>
      <div class="rows">
        <label class="row"><span class="lbl">Semanas de gestação</span><input class="inline" data-f="gestational_weeks" inputmode="numeric" value="${p.gestational_weeks || ''}"></label>
        <label class="row"><span class="lbl">Peso ao nascer (g)</span><input class="inline" data-f="birth_weight_g" inputmode="numeric" value="${p.birth_weight_g || ''}"></label>
        <label class="row"><span class="lbl">Comprimento ao nascer (cm)</span><input class="inline" data-f="birth_length_cm" inputmode="decimal" value="${p.birth_length_cm || ''}"></label>
        <label class="row"><span class="lbl">Perímetro cefálico ao nascer (cm)</span><input class="inline" data-f="birth_head_cm" inputmode="decimal" value="${p.birth_head_cm || ''}"></label>
        <label class="row"><span class="lbl">Parto</span><input class="inline" data-f="birth_type" value="${p.birth_type || ''}"></label>
      </div>
      <p class="note">Alergia aparece em destaque em toda tela da criança.</p>`,
    actions: [{ label: 'Salvar', run: async (dlg) => {
      const v = (k) => dlg.querySelector(`[data-f="${k}"]`).value.trim();
      const num = (k) => (v(k) ? Number(v(k).replace(',', '.')) : null);
      await api(`/api/staff/patients/${p.id}`, { method: 'PUT', body: { allergies: v('allergies') || null, conditions: v('conditions') || null,
        gestational_weeks: num('gestational_weeks'), birth_weight_g: num('birth_weight_g'), birth_length_cm: num('birth_length_cm'), birth_head_cm: num('birth_head_cm'), birth_type: v('birth_type') || null } });
      toast('Ficha salva.'); done();
    } }],
  });
}

function addCareItem(patient, encounterId, done) {
  let kind = 'exame';
  dialog({
    title: 'Pedir ou orientar',
    body: html`<div class="seg" role="group" aria-label="Tipo">${Object.entries(KIND_LABEL).map(([k, l]) => html`<button type="button" data-kind="${k}" aria-pressed="${k === kind}">${l}</button>`)}</div>
      <div class="rows">
        <label class="row"><span class="lbl">O quê</span><input class="inline" data-f="title" placeholder="Hemograma e ferritina"></label>
        <label class="row"><span class="lbl">Detalhe</span><input class="inline" data-f="detail" placeholder="antes da próxima consulta"></label>
        <label class="row"><span class="lbl">Prazo</span><input class="inline" type="date" data-f="due"></label>
        <label class="row"><span class="lbl">A família vê</span><input class="switch" type="checkbox" data-f="family" checked></label>
      </div>
      <p class="note">O item entra no "a fazer" da família, com lembrete. O exame se fecha quando a família manda o resultado e você revisa.</p>`,
    onMount: (dlg) => dlg.addEventListener('click', (ev) => {
      const b = ev.target.closest('[data-kind]');
      if (b) { kind = b.dataset.kind; dlg.querySelectorAll('[data-kind]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }
    }),
    actions: [{ label: 'Adicionar', run: async (dlg) => {
      const v = (k) => dlg.querySelector(`[data-f="${k}"]`);
      await api(`/api/staff/patients/${patient.id}/care-items`, { method: 'POST', body: {
        kind, title: v('title').value, detail: v('detail').value || null, due_to: v('due').value || null,
        visibility: v('family').checked ? 'family' : 'internal', owner: 'familia', encounter_id: encounterId } });
      toast('Adicionado à linha do cuidado.'); done();
    } }],
  });
}

function addMeasure(patient, app, done) {
  dialog({
    title: 'Registrar medida',
    body: html`<div class="rows">
      <label class="row"><span class="lbl">Data</span><input class="inline" type="date" data-f="on" value="${app.today}" max="${app.today}"></label>
      <label class="row"><span class="lbl">Peso (kg)</span><input class="inline num" data-f="weight" inputmode="decimal"></label>
      <label class="row"><span class="lbl">Comprimento (cm)</span><input class="inline num" data-f="length" inputmode="decimal"></label>
      <label class="row"><span class="lbl">Perímetro cefálico (cm)</span><input class="inline num" data-f="head" inputmode="decimal"></label></div>`,
    actions: [{ label: 'Registrar', run: async (dlg) => {
      const n = (k) => { const t = dlg.querySelector(`[data-f="${k}"]`).value.trim().replace(',', '.'); return t ? Number(t) : null; };
      await api(`/api/staff/patients/${patient.id}/measurements`, { method: 'POST', body: { taken_on: dlg.querySelector('[data-f="on"]').value, weight: n('weight'), length: n('length'), head: n('head') } });
      toast('Medida registrada.'); done();
    } }],
  });
}

function staffUpload(r, app, done) {
  const clin = r.clinical;
  const kinds = clin ? [['exame', 'Exame'], ['receita', 'Receita'], ['atestado', 'Atestado'], ['pedido', 'Pedido de exame'], ['foto', 'Foto'], ['documento', 'Documento'], ['nota', 'Nota fiscal'], ['recibo', 'Recibo']]
    : [['nota', 'Nota fiscal'], ['recibo', 'Recibo'], ['comprovante', 'Comprovante'], ['documento', 'Documento']];
  dialog({
    title: 'Enviar arquivo',
    body: html`<div class="rows">
      <label class="row"><span class="lbl">Tipo</span><select class="inline" data-f="kind">${kinds.map(([k, l]) => html`<option value="${k}">${l}</option>`)}</select></label>
      <label class="row"><span class="lbl">Título</span><input class="inline" data-f="title" placeholder="Receita · amoxicilina"></label>
      ${clin ? html`<label class="row"><span class="lbl">A família vê</span><input class="switch" type="checkbox" data-f="family" checked></label>` : ''}
    </div>
    <label class="field" style="border-radius:18px;padding:12px 16px">${icon('upload')}<input type="file" data-f="file" accept="image/*,application/pdf,video/mp4,video/quicktime" style="height:auto"></label>`,
    actions: [{ label: 'Enviar', run: async (dlg) => {
      const file = dlg.querySelector('[data-f="file"]').files[0];
      if (!file) throw new Error('Escolha o arquivo.');
      const fd = new FormData();
      fd.append('patient_id', r.patient.id);
      fd.append('kind', dlg.querySelector('[data-f="kind"]').value);
      fd.append('title', dlg.querySelector('[data-f="title"]').value);
      fd.append('visibility', clin && !dlg.querySelector('[data-f="family"]').checked ? 'internal' : 'family');
      fd.append('upload', file);
      await api('/api/staff/files', { method: 'POST', form: fd });
      toast('Arquivo enviado.'); done();
    } }],
  });
}

// ---- a consulta -------------------------------------------------------------------------------------------------------
export async function encounter(view, params, app) {
  const r = await api(`/api/staff/encounters/${params.id}`);
  const p = r.patient, e = r.encounter, t = r.template;
  const notes = { ...e.notes };
  const m = r.measurement || {};
  const band = r.milestones.bands.find((b) => b.current);
  const done = e.status === 'finalizada';
  const measures = [['weight', 'Peso', 'kg', 'wfa', m.weight_kg], ['length', 'Comprimento', 'cm', 'lhfa', m.length_cm], ['head', 'Perímetro cefálico', 'cm', 'hcfa', m.head_cm]].filter((x) => t.measures.includes(x[0]));
  const last = r.last_measurement;
  const minutes = Math.max(0, Math.round((Date.now() - new Date(e.started_at)) / 60000));
  view.innerHTML = String(html`
    <div class="topbar">
      <a class="linkbtn" href="#/hoje" style="display:inline-flex;align-items:center;gap:4px">${icon('chevL')}Hoje</a>
      <span class="grow"></span>
      <span class="saved" data-saved></span>
      ${done ? html`<span class="pill ok">${icon('check')}Finalizada</span>` : html`<span class="pill strong">${icon('clock')}Em consulta · ${minutes} min</span>`}
    </div>
    <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
      <div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px 18px">
        <span class="av xl">${initials(p.name)}</span>
        <div class="grow" style="display:flex;flex-direction:column;gap:4px;min-width:240px">
          <h1 class="t-title">${p.name}</h1>
          <p class="muted">${p.age} (${dateFull(p.birth_date)})${p.gestational_weeks ? ` · nasceu com ${p.gestational_weeks} semanas` : ''}${p.birth_weight_g ? ` e ${p.birth_weight_g.toLocaleString('pt-BR')} g` : ''}</p>
        </div>
        <a class="btn ghost" href="#/paciente/${p.id}">Abrir a ficha</a>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        ${p.allergies ? html`<span class="pill late long">${icon('alert')}${p.allergies}</span>` : ''}
        ${p.plan ? html`<span class="pill long">Plano ${p.plan.plan} · ${p.plan.summary}</span>` : ''}
        ${p.guardians.length ? html`<span class="pill long">Responsáveis: ${p.guardians.map((g) => `${g.name.split(' ')[0]} (${g.relation})`).join(' e ')}</span>` : ''}
      </div>
    </section>
    <div class="cols">
      <div class="colmain">
        <section class="glass card" style="display:flex;flex-direction:column;gap:20px" data-form>
          <div class="phead"><div><h2 class="t-h2">${r.title}</h2><span class="t-small muted">Modelo ${t.label} · só no prontuário</span></div></div>
          ${measures.length ? html`<div class="group"><span class="t-cap">Medidas</span>
            <div class="rows">${measures.map(([k, label, unit, ind, val]) => html`<div class="row"><label class="lbl" for="m-${k}">${label}</label>
              <input class="inline num" id="m-${k}" data-measure="${k}" inputmode="decimal" value="${val ? String(val).replace('.', ',') : ''}" placeholder="—" style="flex:0 1 100px">
              <span class="unit">${unit}</span><span class="pill" data-pct="${ind}">—</span></div>`)}</div>
            <p class="note">Percentis da OMS para ${p.sex === 'F' ? 'meninas' : 'meninos'}, na hora.${last ? ` Na última medida (${dateBR(last.taken_on)}): ${[last.weight_kg && `${String(last.weight_kg).replace('.', ',')} kg`, last.length_cm && `${String(last.length_cm).replace('.', ',')} cm`].filter(Boolean).join(' e ')}.` : ''}</p></div>` : ''}
          ${t.fields.map((fl) => fieldHtml(fl, notes, band))}
          <div class="group"><label class="t-cap" for="f-cid">Hipóteses · CID-10</label>
            <label class="field"><input id="f-cid" data-cid value="${e.cid || ''}" placeholder="Z00.1 · Exame de rotina de saúde da criança"></label></div>
          <div class="group"><label class="t-cap" for="f-conduct">Conduta</label><textarea class="area" id="f-conduct" data-conduct rows="3">${e.conduct || ''}</textarea></div>
        </section>
      </div>
      <div class="colside">
        <section class="glass card" style="display:flex;flex-direction:column;gap:12px">
          <div class="phead center"><h2 class="t-h2">Para a família</h2><span class="pill">${icon('eye')}A família vê isto</span></div>
          <p class="t-small muted pretty">O registro ao lado fica só no prontuário. Daqui, a família recebe o resumo e os próximos passos.</p>
          <label class="t-cap" for="f-summary">Resumo da consulta</label>
          <textarea class="area" id="f-summary" data-summary rows="6" placeholder="Em palavras simples: como a criança está, o que fazer em casa e o que vem.">${e.family_summary || ''}</textarea>
          <div class="rows"><label class="row"><span class="lbl">Liberar ao finalizar</span><input class="switch" type="checkbox" data-release ${e.summary_released || !done ? raw('checked') : ''}></label></div>
        </section>
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">Próximos passos</h2><span class="t-small muted">vão para a linha do cuidado</span></div>
          <div style="margin-top:4px">
            ${r.todo.map((i) => html`<div class="li">${careTick(i)}<div class="grow"><b>${i.title}</b><p class="t-small muted">${i.detail}</p></div>${carePill(i, app.today)}</div>`)}
            ${r.care_items.map((c) => html`<div class="li"><span class="tick">${icon(c.kind === 'exame' ? 'flask' : c.kind === 'orientacao' ? 'book' : 'flag')}</span><div class="grow"><b>${c.title}</b><p class="t-small muted">${KIND_LABEL[c.kind]}${c.due_to ? ` · até ${dateBR(c.due_to)}` : ''}${c.visibility === 'internal' ? ' · só no prontuário' : ''}</p></div><span class="pill todo">Pedido</span></div>`)}
          </div>
          <button class="linkbtn t-small" type="button" data-act="add-step" style="margin-top:6px">+ Pedir exame, tarefa ou orientação</button>
        </section>
        ${r.vaccines_due.length ? html`<section class="glass card">
          <div class="phead"><h2 class="t-h2">Vacinas para hoje</h2></div>
          ${r.vaccines_due.slice(0, 6).map((v) => html`<div class="li"><span class="tick">${icon('syringe')}</span><div class="grow"><b>${v.vaccine}</b><p class="t-small muted">${v.dose} · ${v.status === 'atrasado' ? 'atrasada' : `a partir de ${dateBR(v.due)}`}</p></div>
            <button class="btn ghost small" type="button" data-act="vaccine" data-code="${v.code}">Aplicada hoje</button></div>`)}
        </section>` : ''}
        ${done ? html`<a class="btn big wide" href="#/hoje">Voltar ao dia</a>` : html`<button class="btn big wide" type="button" data-act="finish">Finalizar a consulta</button>`}
      </div>
    </div>`);

  const read = () => {
    const out = { notes: { ...notes }, cid: view.querySelector('[data-cid]').value.trim() || null, conduct: view.querySelector('[data-conduct]').value.trim() || null,
      family_summary: view.querySelector('[data-summary]').value.trim() || null, summary_released: view.querySelector('[data-release]').checked };
    view.querySelectorAll('[data-field]').forEach((el) => { out.notes[el.dataset.field] = el.value; });
    view.querySelectorAll('[data-check-group]').forEach((g) => { out.notes[g.dataset.checkGroup] = [...g.querySelectorAll('input:checked')].map((i) => i.value); });
    view.querySelectorAll('[data-measure]').forEach((el) => { const v = el.value.trim().replace(',', '.'); out[el.dataset.measure] = v ? Number(v) : null; });
    const ms = view.querySelector('[data-milestones]');
    if (ms) out.milestones = [...ms.querySelectorAll('input:checked')].map((i) => i.value);
    return out;
  };
  const savedEl = view.querySelector('[data-saved]');
  const save = debounce(async () => {
    if (done) return;
    try {
      await api(`/api/staff/encounters/${e.id}`, { method: 'PUT', body: read() });
      savedEl.textContent = `Salvo às ${new Date().toTimeString().slice(0, 5)}`;
    } catch (err) { savedEl.textContent = 'Não salvou'; fail(err); }
  }, 1200);
  const assess = debounce(async () => {
    const q = new URLSearchParams({ patient_id: p.id });
    view.querySelectorAll('[data-measure]').forEach((el) => { const v = el.value.trim().replace(',', '.'); if (v && Number(v) > 0) q.set(el.dataset.measure, v); });
    if ([...q.keys()].length === 1) return;
    try {
      const a = await api(`/api/staff/growth?${q}`);
      Object.entries(a.measures || {}).forEach(([ind, mm]) => {
        const pill = view.querySelector(`[data-pct="${ind}"]`);
        if (pill) { pill.textContent = mm.label; pill.className = `pill ${Math.abs(mm.z) > 2 ? 'late' : ''}`; pill.title = mm.reading; }
      });
    } catch (err) { /* medida pela metade: sem percentil ainda */ }
  }, 350);
  view.addEventListener('input', (ev) => {
    if (ev.target.closest('[data-measure]')) assess();
    savedEl.textContent = done ? '' : 'Salvando…';
    save();
  });
  view.addEventListener('change', () => save());
  assess();
  actions(view, {
    'add-step': async () => { if (!done) await api(`/api/staff/encounters/${e.id}`, { method: 'PUT', body: read() }); addCareItem(p, e.id, refresh); },
    vaccine: async (el) => {
      await api(`/api/staff/patients/${p.id}/immunizations`, { method: 'POST', body: { code: el.dataset.code, applied_on: app.today, place: 'Consultório' } });
      toast('Vacina registrada na caderneta.');
      el.closest('.li').remove();
    },
    finish: async () => {
      const body = read();
      if (!body.family_summary && body.summary_released && !await ask('Finalizar sem resumo para a família?', 'A família vai ver a consulta no app, mas sem o resumo.', 'Finalizar assim')) return;
      await api(`/api/staff/encounters/${e.id}/finish`, { method: 'POST', body });
      toast(body.summary_released && body.family_summary ? `Consulta finalizada. O resumo foi para a família de ${p.first_name}.` : 'Consulta finalizada.');
      location.hash = '#/hoje';
    },
  });
}

function fieldHtml(fl, notes, band) {
  const v = notes[fl.key] ?? '';
  if (fl.type === 'textarea') return html`<div class="group"><label class="t-cap" for="f-${fl.key}">${fl.label}</label><textarea class="area" id="f-${fl.key}" data-field="${fl.key}" rows="3">${v}</textarea></div>`;
  if (fl.type === 'text') return html`<div class="group"><label class="t-cap" for="f-${fl.key}">${fl.label}</label><label class="field"><input id="f-${fl.key}" data-field="${fl.key}" value="${v}" placeholder="${fl.placeholder || ''}"></label></div>`;
  if (fl.type === 'checks') {
    const on = Array.isArray(v) ? v : [];
    return html`<div class="group"><span class="t-cap">${fl.label}</span><div class="rows" data-check-group="${fl.key}">${fl.options.map((o) => html`<label class="row"><span class="lbl">${o}</span><input class="switch" type="checkbox" value="${o}" ${on.includes(o) ? raw('checked') : ''}></label>`)}</div></div>`;
  }
  if (fl.type === 'milestones') {
    if (!band) return '';
    return html`<div class="group"><span class="t-cap">${fl.label} · ${band.title.toLowerCase()}</span><div class="rows" data-milestones>${band.items.map((it) => html`<label class="row"><span class="lbl">${it.label}${it.checked && it.marked_by ? html`<span class="sub">marcado por ${it.marked_by} em ${dateBR(it.achieved_on)}</span>` : ''}</span><input class="switch" type="checkbox" value="${it.code}" ${it.checked ? raw('checked') : ''}></label>`)}</div></div>`;
  }
  return '';
}

// ---- a caixa de revisão ---------------------------------------------------------------------------------------------
export async function review(view, params, app) {
  const r = await api('/api/staff/review');
  const pending = r.files.filter((f) => !f.reviewed_at);
  const doneList = r.files.filter((f) => f.reviewed_at).slice(0, 12);
  setCount('revisar', pending.length);
  view.innerHTML = String(html`
    <div class="topbar"><div class="titles"><h1 class="t-title">Revisar</h1><p class="t-small muted">O que as famílias mandaram: exames, fotos e vídeos. Revisar com um comentário avisa a família.</p></div></div>
    ${pending.length ? pending.map((f) => html`<section class="glass card" style="display:flex;flex-wrap:wrap;gap:16px" data-file="${f.id}">
      ${f.mime && f.mime.startsWith('image/') ? html`<a href="/api/files/${f.id}" target="_blank" rel="noopener"><img class="thumb" src="/api/files/${f.id}" alt="${f.title}" style="width:120px;height:120px"></a>` : html`<a class="tick sq" href="/api/files/${f.id}" target="_blank" rel="noopener" style="width:120px;height:120px" aria-label="Abrir ${f.title}">${icon(fileIcon(f.kind))}</a>`}
      <div class="grow" style="display:flex;flex-direction:column;gap:8px;min-width:240px">
        <div><b class="t-h3">${f.title}</b><p class="t-small muted">${f.patient || ''}${f.age_short ? `, ${f.age_short}` : ''} · ${f.uploader_name || 'família'} · ${ago(f.created_at)}</p></div>
        ${f.note ? html`<p class="quote">“${f.note}”</p>` : ''}
        <textarea class="area" rows="2" data-note placeholder="O que dizer à família (opcional)"></textarea>
        <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center"><button class="btn ghost" type="button" data-act="done" data-id="${f.id}">Marcar como revisado</button><a class="linkbtn t-small" href="/api/files/${f.id}" target="_blank" rel="noopener">Abrir o arquivo</a></div>
      </div></section>`) : html`<section class="glass card empty"><b>Nada para revisar.</b>Quando a família mandar um exame ou uma foto, aparece aqui.</section>`}
    ${doneList.length ? html`<section class="glass card"><div class="phead"><h2 class="t-h2">Revisados</h2></div>
      ${doneList.map((f) => html`<div class="li"><span class="tick sq">${icon(fileIcon(f.kind))}</span><div class="grow"><b>${f.title}</b><p class="t-small muted">${f.patient || ''} · revisado ${ago(f.reviewed_at)}${f.review_note ? ` · “${f.review_note}”` : ''}</p></div><a class="linkbtn t-small" href="/api/files/${f.id}" target="_blank" rel="noopener">Abrir</a></div>`)}</section>` : ''}`);
  actions(view, {
    done: async (el) => {
      const card = el.closest('[data-file]');
      await api(`/api/staff/files/${el.dataset.id}/review`, { method: 'POST', body: { note: card.querySelector('[data-note]').value } });
      toast('Revisado. A família foi avisada.');
      refresh();
    },
  });
}


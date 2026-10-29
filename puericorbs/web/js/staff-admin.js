// A configuração e o dinheiro: o catálogo de serviços (cada serviço do jeito do pediatra), os planos de acompanhamento e
// o financeiro da prática.
import { api, html, raw, icon, toast, fail, dialog, ask, askFields, shareLink, money, dateBR, dateFull, initials, actions, centsInput, toCents, debounce, monthName } from './lib.js';
import { revenueBars, bindBars, revenueTable } from './charts.js';
import { isClinician } from './staff-common.js';
import { refresh } from './staff.js';

const get = (obj, path) => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
function set(obj, path, value) {
  const keys = path.split('.');
  let o = obj;
  keys.slice(0, -1).forEach((k) => { o[k] = o[k] && typeof o[k] === 'object' ? o[k] : {}; o = o[k]; });
  o[keys[keys.length - 1]] = value;
}

// ---- serviços -------------------------------------------------------------------------------------------------------
export async function services(view, params, app) {
  const r = await api('/api/staff/services');
  const sel = r.services.find((s) => s.id === Number(params.query.s)) || r.services[0];
  const svc = JSON.parse(JSON.stringify(sel));
  const cfg = svc.config;
  const cats = Object.entries(r.categories);
  const WD = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'];
  const fmt = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
  const sw = (path, label, sub = '') => html`<label class="row"><span class="lbl">${label}${sub ? html`<span class="sub">${sub}</span>` : ''}</span><input class="switch" type="checkbox" data-path="${path}" data-type="bool" ${get(svc, path) ? raw('checked') : ''}></label>`;
  const numRow = (path, label, unit) => html`<label class="row"><span class="lbl">${label}</span><input class="inline num" data-path="${path}" data-type="num" inputmode="numeric" value="${get(svc, path) ?? ''}" placeholder="—" style="flex:0 1 80px"><span class="unit">${unit}</span></label>`;
  const moneyRow = (path, label) => html`<label class="row"><span class="lbl">${label}</span><span class="muted">R$</span><input class="inline num" data-path="${path}" data-type="money" inputmode="decimal" value="${centsInput(get(svc, path))}" style="flex:0 1 110px"></label>`;
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Serviços</h1><p class="t-small muted">O que você oferece, como se agenda e quanto custa. Cada serviço do seu jeito.</p></div>
      <button class="btn ghost" type="button" data-act="new">${icon('plus')}Novo serviço</button>
    </div>
    <div class="cols">
      <div class="colside" style="flex:1 1 280px;max-width:380px">
        <section class="glass" style="padding:12px;display:flex;flex-direction:column;gap:4px" aria-label="Catálogo">
          ${cats.map(([ck, cl]) => {
            const items = r.services.filter((s) => s.category === ck);
            if (!items.length) return '';
            return html`<span class="t-cap" style="padding:10px 12px 4px">${cl}</span>
              ${items.map((s) => html`<a class="opt" href="#/servicos?s=${s.id}" aria-pressed="${s.id === svc.id}" style="min-height:56px;padding:9px 12px;background:${s.id === svc.id ? '' : 'transparent'};box-shadow:${s.id === svc.id ? '' : 'none'};text-decoration:none">
                <span class="grow"><b style="display:block;font-size:14px">${s.name}</b><span class="t-small muted">${s.duration_min} min · ${s.price_cents ? money(s.price_cents) : 'sem custo'}${s.config.booking.family ? '' : ' · só recepção'}</span></span>
                ${s.active ? '' : html`<span class="pill">Desligado</span>`}</a>`)}`;
          })}
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:12px">
          <h2 class="t-h2">Como a família vê</h2>
          <div class="opt" aria-pressed="true" style="cursor:default"><span class="radio" aria-hidden="true"></span>
            <span class="grow"><b style="display:block" data-preview="name">${svc.kind === 'well_child' ? 'Consulta dos 6 meses' : svc.name}</b><span class="t-small muted" data-preview="meta">${svc.kind_label} · ${svc.duration_min} min</span></span>
            <span class="t-small" style="font-weight:700" data-preview="price">${cfg.plan_mode === 'cota' ? 'No plano' : money(svc.price_cents)}</span></div>
          <p class="t-small muted pretty">${svc.kind === 'well_child' ? 'O nome acompanha a idade pelo protocolo, e o app só oferece os dias dentro da janela da criança.' : cfg.booking.family ? 'A família marca pelo app, dentro das regras ao lado.' : 'Este serviço não aparece no app: só a recepção marca.'}</p>
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:10px">
          <h2 class="t-h2">Grade de atendimento</h2>
          <div class="rows">${[0, 1, 2, 3, 4, 5, 6].map((wd) => {
            const win = r.schedule.availability.filter((a) => a.weekday === wd);
            const res = r.schedule.reserved.filter((a) => a.weekday === wd);
            return html`<div class="row"><span class="lbl">${WD[wd]}</span><span class="t-small muted" style="text-align:right">${win.length ? win.map((w) => `${fmt(w.start_min)}–${fmt(w.end_min)}`).join(' · ') : 'sem atendimento'}${res.length ? html`<br>${res.length} vaga${res.length > 1 ? 's' : ''} para doença: ${res.map((x) => fmt(x.start_min)).join(', ')}` : ''}</span></div>`;
          })}</div>
          <p class="note">As vagas para a criança doente só abrem no próprio dia.</p>
        </section>
      </div>
      <section class="glass card colmain" style="display:flex;flex-direction:column;gap:22px" data-editor>
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px">
          <h2 class="t-title grow">${svc.name}</h2>
          <span class="pill ${svc.active ? 'ok' : ''}">${svc.active ? 'Ativo' : 'Desligado'}</span>
        </div>
        <p class="t-small muted" style="margin-top:-14px">Versão ${svc.version} · o que já foi marcado guarda a versão do dia em que foi marcado.</p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(min(320px, 100%), 1fr));gap:22px 18px;align-items:start">
          <div class="group"><span class="t-cap">Identidade</span>
            <div class="rows">
              <label class="row"><span class="lbl">Nome</span><input class="inline" data-path="name" value="${svc.name}"></label>
              <label class="row"><span class="lbl">Categoria</span><select class="inline" data-path="category">${cats.map(([k, l]) => html`<option value="${k}" ${k === svc.category ? raw('selected') : ''}>${l}</option>`)}</select></label>
              <label class="row"><span class="lbl">Tipo</span><select class="inline" data-path="kind">${Object.entries(r.kinds).map(([k, l]) => html`<option value="${k}" ${k === svc.kind ? raw('selected') : ''}>${l}</option>`)}</select></label>
              ${numRow('config.age_min_m', 'Idade mínima', 'meses')}
              ${numRow('config.age_max_m', 'Idade máxima', 'meses')}
            </div>
            <label class="t-cap" for="sv-text" style="margin-top:6px">Texto para a família</label>
            <textarea class="area" id="sv-text" rows="2" data-path="config.family_text">${cfg.family_text}</textarea>
          </div>
          <div class="group"><span class="t-cap">Tempo</span>
            <div class="rows">
              <div class="row"><span class="lbl">Duração</span><div class="stepper"><button type="button" data-act="dur" data-d="-5" aria-label="Menos 5 minutos">${icon('minus')}</button><output data-dur>${svc.duration_min} min</output><button type="button" data-act="dur" data-d="5" aria-label="Mais 5 minutos">${icon('plus')}</button></div></div>
              <label class="row"><span class="lbl">De manhã</span><input class="switch" type="checkbox" data-shift="manha" ${cfg.shifts.includes('manha') ? raw('checked') : ''}></label>
              <label class="row"><span class="lbl">À tarde</span><input class="switch" type="checkbox" data-shift="tarde" ${cfg.shifts.includes('tarde') ? raw('checked') : ''}></label>
            </div>
          </div>
          <div class="group"><span class="t-cap">Quem agenda</span>
            <div class="rows">
              ${sw('config.booking.reception', 'A recepção')}
              ${sw('config.booking.family', 'A família, pelo app')}
              ${sw('config.booking.public', 'Pela página pública')}
              ${numRow('config.booking.min_notice_h', 'Antecedência mínima', 'h')}
              ${numRow('config.booking.max_days', 'Até', 'dias')}
              ${sw('config.booking.squeeze', 'Aceita encaixe')}
            </div>
          </div>
          <div class="group"><span class="t-cap">Preço</span>
            <div class="rows">
              <label class="row"><span class="lbl">Particular</span><span class="muted">R$</span><input class="inline num" data-path="price_cents" data-type="money" inputmode="decimal" value="${centsInput(svc.price_cents)}" style="flex:0 1 110px"></label>
              <label class="row"><span class="lbl">No plano</span><select class="inline" data-path="config.plan_mode"><option value="cota" ${cfg.plan_mode === 'cota' ? raw('selected') : ''}>Entra na cota</option><option value="desconto" ${cfg.plan_mode === 'desconto' ? raw('selected') : ''}>Só o desconto</option><option value="fora" ${cfg.plan_mode === 'fora' ? raw('selected') : ''}>Fora do plano</option></select></label>
              ${sw('config.return_free', 'Retorno sem custo')}
              ${numRow('config.return_days', 'Prazo do retorno', 'dias')}
              ${moneyRow('config.no_show_fee_cents', 'Taxa de falta')}
              ${sw('config.prepay', 'Pagamento antecipado')}
              ${numRow('config.cancel_hours', 'Cancelar sem custo até', 'h antes')}
            </div>
          </div>
          <div class="group"><span class="t-cap">Na consulta</span>
            <div class="rows">
              <label class="row"><span class="lbl">Modelo de registro</span><select class="inline" data-path="config.template">${Object.entries(r.templates).map(([k, l]) => html`<option value="${k}" ${k === cfg.template ? raw('selected') : ''}>${l}</option>`)}</select></label>
            </div>
            <label class="t-cap" for="sv-q" style="margin-top:6px">Perguntas antes da consulta (uma por linha)</label>
            <textarea class="area" id="sv-q" rows="3" data-path="config.questions" data-type="lines">${(cfg.questions || []).join('\n')}</textarea>
          </div>
          <div class="group"><span class="t-cap">Depois da consulta</span>
            <div class="rows">
              ${sw('config.after.next_by_protocol', 'Próxima consulta pelo protocolo')}
              ${sw('config.after.guidance', 'Orientações pela idade')}
              ${sw('config.after.attendance_statement', 'Declaração de comparecimento')}
              ${sw('config.after.survey', 'Pesquisa de satisfação')}
            </div>
          </div>
          <div class="group"><span class="t-cap">Nota fiscal</span>
            <div class="rows">
              <label class="row"><span class="lbl">Código do serviço</span><input class="inline" data-path="config.invoice.code" value="${cfg.invoice.code}"></label>
              <label class="row"><span class="lbl">Descrição na nota</span><input class="inline" data-path="config.invoice.description" value="${cfg.invoice.description}" placeholder="${svc.name}"></label>
              ${sw('config.invoice.auto', 'Emitir sozinha')}
            </div>
          </div>
        </div>
        ${isClinician(app) ? html`<div style="display:flex;flex-wrap:wrap;align-items:center;gap:12px;padding-top:12px;border-top:.5px solid var(--hair)">
          <button class="linkbtn ${svc.active ? 'danger' : ''}" type="button" data-act="toggle">${svc.active ? 'Desligar o serviço' : 'Ligar o serviço'}</button>
          <span class="grow"></span>
          <button class="btn ghost big" type="button" data-act="dup">Duplicar</button>
          <button class="btn big" type="button" data-act="save">Salvar</button></div>` : html`<p class="note">Só o pediatra muda o catálogo.</p>`}
      </section>
    </div>`);
  let duration = svc.duration_min;
  const collect = () => {
    const out = JSON.parse(JSON.stringify(svc));
    out.duration_min = duration;
    view.querySelectorAll('[data-editor] [data-path]').forEach((el) => {
      const type = el.dataset.type;
      let v = el.value;
      if (type === 'bool') v = el.checked;
      else if (type === 'num') v = v.trim() === '' ? null : Number(v.replace(',', '.'));
      else if (type === 'money') v = toCents(v);
      else if (type === 'lines') v = v.split('\n').map((x) => x.trim()).filter(Boolean);
      set(out, el.dataset.path, v);
    });
    out.config.shifts = [...view.querySelectorAll('[data-shift]:checked')].map((x) => x.dataset.shift);
    return out;
  };
  const send = async (body, id = svc.id) => api(`/api/staff/services/${id}`, { method: 'PUT', body: {
    name: body.name, category: body.category, kind: body.kind, duration_min: body.duration_min, price_cents: body.price_cents, active: body.active, config: body.config } });
  view.querySelector('[data-editor]').addEventListener('input', debounce(() => {
    const c = collect();
    view.querySelector('[data-preview="name"]').textContent = c.kind === 'well_child' ? 'Consulta dos 6 meses' : c.name;
    view.querySelector('[data-preview="meta"]').textContent = `${r.kinds[c.kind]} · ${c.duration_min} min`;
    view.querySelector('[data-preview="price"]').textContent = c.config.plan_mode === 'cota' ? 'No plano' : money(c.price_cents);
  }, 150));
  actions(view, {
    dur: (el) => { duration = Math.max(5, Math.min(240, duration + Number(el.dataset.d))); view.querySelector('[data-dur]').textContent = `${duration} min`; },
    save: async () => { const r2 = await send(collect()); toast(`Serviço salvo (versão ${r2.version}).`); refresh(); },
    toggle: async () => { const c = collect(); c.active = !svc.active; await send(c); toast(c.active ? 'Serviço ligado.' : 'Serviço desligado: ele some do app da família.'); refresh(); },
    dup: async () => {
      const c = collect();
      const r2 = await api('/api/staff/services', { method: 'POST', body: { name: `${c.name} (cópia)`, category: c.category, kind: c.kind, duration_min: c.duration_min, price_cents: c.price_cents, active: false, config: c.config } });
      toast('Cópia criada, desligada até você revisar.'); location.hash = `#/servicos?s=${r2.id}`;
    },
    new: async () => {
      const r2 = await api('/api/staff/services', { method: 'POST', body: { name: 'Novo serviço', category: 'consulta', kind: 'well_child', duration_min: 30, price_cents: 0, active: false, config: {} } });
      location.hash = `#/servicos?s=${r2.id}`;
    },
  });
}

// ---- planos ----------------------------------------------------------------------------------------------------------
export async function plans(view, params, app) {
  const r = await api('/api/staff/plans');
  const clin = isClinician(app);
  const svcName = (id) => (r.services.find((s) => s.id === id) || {}).name || 'serviço';
  const status = (m) => m.status === 'cancelado' ? html`<span class="pill">Cancelado</span>`
    : m.status === 'pausado' ? html`<span class="pill">Pausado${m.paused_until ? ` até ${dateBR(m.paused_until)}` : ''}</span>`
    : m.late_days ? html`<span class="pill late">Atrasado há ${m.late_days} dia${m.late_days > 1 ? 's' : ''}</span>`
    : m.renews_today ? html`<span class="pill todo">Renova hoje</span>` : html`<span class="pill ok">Em dia</span>`;
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Planos de acompanhamento</h1><p class="t-small muted">Pacotes dos seus serviços, cobrados todo mês.</p></div>
      <button class="btn ghost" type="button" data-act="member">${icon('plus')}Nova adesão</button>
      ${clin ? html`<button class="btn" type="button" data-act="new">${icon('plus')}Novo plano</button>` : ''}
    </div>
    <div class="grid-auto">
      <div class="glass stat"><span class="lbl">Assinantes</span><span class="val">${r.subscribers}</span><span class="sub">${r.new_this_month} novo${r.new_this_month === 1 ? '' : 's'} este mês</span></div>
      <div class="glass stat"><span class="lbl">Receita recorrente</span><span class="val">${money(r.mrr_cents)}</span><span class="sub">por mês</span></div>
      <div class="glass stat"><span class="lbl">Pagamentos atrasados</span><span class="val">${r.overdue.n}</span><span class="sub">${money(r.overdue.s)} · a régua já avisou</span></div>
      <div class="glass stat"><span class="lbl">Cancelamentos</span><span class="val">${r.cancelled}</span><span class="sub">desde o começo</span></div>
    </div>
    <div class="grid-cards">
      ${r.plans.map((p) => html`<section class="glass card" style="display:flex;flex-direction:column;gap:14px">
        <div class="phead center"><h2 class="t-h2">${p.name}</h2><span class="pill ${p.active ? 'ok' : ''}">${p.active ? 'Ativo' : 'Desligado'}</span></div>
        <p class="t-small muted">${[p.entry_rule, `${p.months} meses`, p.auto_renew ? 'renova sozinho' : 'sem renovação'].filter(Boolean).join(' · ')}</p>
        <p><span class="t-hero">${money(p.price_cents).replace(',00', '')}</span><span class="muted"> por mês</span></p>
        <ul style="display:flex;flex-direction:column;gap:8px">
          ${p.benefits.map((b) => html`<li style="display:flex;gap:10px;font-size:14px">${icon('check', 'muted')}${b.qty} ${b.label || svcName(b.service_id)}</li>`)}
          ${p.perks.map((t) => html`<li style="display:flex;gap:10px;font-size:14px">${icon('check', 'muted')}${t}</li>`)}
          ${p.discount_pct ? html`<li style="display:flex;gap:10px;font-size:14px">${icon('check', 'muted')}${p.discount_pct}% de desconto nos outros serviços</li>` : ''}
        </ul>
        <div class="well" style="padding:12px 14px;display:flex;flex-direction:column;gap:8px">
          <div style="display:flex;justify-content:space-between;gap:8px"><b>${p.subscribers} assinante${p.subscribers === 1 ? '' : 's'}</b><span class="t-small muted">usam ${p.usage_pct}% da cota</span></div>
          <div class="meter"><i style="width:${p.usage_pct}%"></i></div>
        </div>
        ${clin ? html`<div><button class="btn ghost small" type="button" data-act="edit" data-id="${p.id}">Editar</button></div>` : ''}
      </section>`)}
    </div>
    <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
      <div class="phead"><h2 class="t-h2">Assinantes</h2><span class="t-small muted">${r.members.length}</span></div>
      <div class="tblbox"><table class="tbl" style="min-width:820px"><thead><tr><th>Criança · responsável</th><th>Plano</th><th>Desde</th><th>Cota usada</th><th>Cobrança</th><th>Situação</th><th></th></tr></thead><tbody>
        ${r.members.map((m) => {
          const u = m.usage[0];
          const pct = u && u.qty ? Math.round(100 * u.used / u.qty) : 0;
          return html`<tr><td><a href="#/paciente/${m.patient_id}" style="text-decoration:none"><b>${m.patient}</b></a><span class="t-small muted"> · ${m.guardian}</span></td><td>${m.plan}</td><td class="num">${dateFull(m.started_on)}</td>
            <td>${u ? html`<span class="usage"><span class="meter"><i style="width:${pct}%"></i></span><span class="t-small num">${u.used} de ${u.qty}</span></span>` : '—'}</td>
            <td>${m.billing_label} · dia ${m.due_day}</td><td>${status(m)}</td>
            <td>${m.status === 'ativo' ? html`<button class="linkbtn t-small" type="button" data-act="pause" data-id="${m.id}">Pausar</button>` : m.status === 'pausado' ? html`<button class="linkbtn t-small" type="button" data-act="resume" data-id="${m.id}">Reativar</button>` : ''}</td></tr>`;
        })}
      </tbody></table></div>
    </section>
    <p class="t-small muted pretty" style="display:flex;gap:8px;align-items:flex-start">${icon('info')}O plano de acompanhamento é um pacote dos seus próprios serviços. Ele não cobre urgência, internação nem exames de outros profissionais.</p>`);
  actions(view, {
    new: () => planEditor(r, null),
    edit: (el) => planEditor(r, r.plans.find((p) => p.id === Number(el.dataset.id))),
    member: () => newMembership(r),
    pause: async (el) => {
      if (!await ask('Pausar o plano?', 'Os benefícios ficam suspensos e a cobrança para até reativar.', 'Pausar')) return;
      await api(`/api/staff/memberships/${el.dataset.id}/status`, { method: 'POST', body: { status: 'pausado' } });
      toast('Plano pausado.'); refresh();
    },
    resume: async (el) => { await api(`/api/staff/memberships/${el.dataset.id}/status`, { method: 'POST', body: { status: 'ativo' } }); toast('Plano reativado.'); refresh(); },
  });
}

function planEditor(r, plan) {
  const p = plan || { name: '', description: '', price_cents: 0, months: 12, entry_rule: '', discount_pct: 15, sibling_discount_pct: 10, auto_renew: true, active: true, benefits: [], perks: [] };
  const benefitRow = (b) => html`<div class="row" data-benefit>
    <select class="inline" data-b="service_id" style="text-align:left;text-align-last:left">${r.services.map((s) => html`<option value="${s.id}" ${s.id === b.service_id ? raw('selected') : ''}>${s.name}</option>`)}</select>
    <input class="inline num" data-b="qty" inputmode="numeric" value="${b.qty || 1}" style="flex:0 0 46px" aria-label="Quantidade">
    <button class="iconbtn small" type="button" data-rm aria-label="Tirar">${icon('x')}</button></div>`;
  dialog({
    title: plan ? `Editar ${plan.name}` : 'Novo plano',
    wide: true,
    body: html`<div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" data-f="name" value="${p.name}" placeholder="Primeiro Ano"></label>
        <label class="row"><span class="lbl">Preço por mês</span><span class="muted">R$</span><input class="inline num" data-f="price" inputmode="decimal" value="${centsInput(p.price_cents)}" style="flex:0 1 110px"></label>
        <label class="row"><span class="lbl">Vigência</span><input class="inline num" data-f="months" inputmode="numeric" value="${p.months}" style="flex:0 1 60px"><span class="unit">meses</span></label>
        <label class="row"><span class="lbl">Quem pode entrar</span><input class="inline" data-f="entry" value="${p.entry_rule || ''}" placeholder="entrada até os 3 meses"></label>
        <label class="row"><span class="lbl">Desconto nos outros serviços</span><input class="inline num" data-f="discount" inputmode="numeric" value="${p.discount_pct}" style="flex:0 1 60px"><span class="unit">%</span></label>
        <label class="row"><span class="lbl">Desconto de irmão</span><input class="inline num" data-f="sibling" inputmode="numeric" value="${p.sibling_discount_pct}" style="flex:0 1 60px"><span class="unit">%</span></label>
        <label class="row"><span class="lbl">Renova sozinho</span><input class="switch" type="checkbox" data-f="renew" ${p.auto_renew ? raw('checked') : ''}></label>
        <label class="row"><span class="lbl">Ativo (aceita adesões)</span><input class="switch" type="checkbox" data-f="active" ${p.active ? raw('checked') : ''}></label>
      </div>
      <span class="t-cap">Serviços incluídos (a cota na vigência)</span>
      <div class="rows" data-benefits>${p.benefits.map(benefitRow)}</div>
      <button class="linkbtn t-small" type="button" data-add-benefit>+ Incluir um serviço</button>
      <label class="t-cap" for="pl-perks">O que mais vem junto (um por linha)</label>
      <textarea class="area" id="pl-perks" data-f="perks" rows="3" placeholder="Mensagens em horário comercial, resposta em até 4 h">${p.perks.join('\n')}</textarea>
      <p class="note">Plano de acompanhamento não é plano de saúde: só os seus serviços, sem urgência, internação nem exames de terceiros.</p>`,
    onMount: (dlg) => dlg.addEventListener('click', (ev) => {
      if (ev.target.closest('[data-add-benefit]')) dlg.querySelector('[data-benefits]').insertAdjacentHTML('beforeend', String(benefitRow({ service_id: r.services[0].id, qty: 1 })));
      const rm = ev.target.closest('[data-rm]');
      if (rm) rm.closest('[data-benefit]').remove();
    }),
    actions: [{ label: plan ? 'Salvar' : 'Criar o plano', run: async (dlg) => {
      const f = (k) => dlg.querySelector(`[data-f="${k}"]`);
      const benefits = [...dlg.querySelectorAll('[data-benefit]')].map((row) => ({ service_id: Number(row.querySelector('[data-b="service_id"]').value), qty: Number(row.querySelector('[data-b="qty"]').value) }));
      const body = { name: f('name').value, description: plan?.description || null, price_cents: toCents(f('price').value), months: Number(f('months').value) || 12,
        entry_rule: f('entry').value || null, discount_pct: Number(f('discount').value) || 0, sibling_discount_pct: Number(f('sibling').value) || 0,
        auto_renew: f('renew').checked, active: f('active').checked, benefits, perks: f('perks').value.split('\n').map((x) => x.trim()).filter(Boolean),
        max_entry_age_m: plan?.max_entry_age_m ?? null };
      if (plan) await api(`/api/staff/plans/${plan.id}`, { method: 'PUT', body });
      else await api('/api/staff/plans', { method: 'POST', body });
      toast('Plano salvo.'); refresh();
    } }],
  });
}

function newMembership(r) {
  let patient = null;
  const d = dialog({
    title: 'Nova adesão',
    body: html`<label class="field">${icon('search')}<input data-q placeholder="Buscar a criança" aria-label="Buscar a criança" autocomplete="off"></label>
      <div class="opts" data-results></div>
      <div class="rows">
        <label class="row"><span class="lbl">Plano</span><select class="inline" data-f="plan">${r.plans.filter((p) => p.active).map((p) => html`<option value="${p.id}">${p.name} · ${money(p.price_cents)}</option>`)}</select></label>
        <label class="row"><span class="lbl">Cobrança</span><select class="inline" data-f="billing">${Object.entries(r.billing).map(([k, l]) => html`<option value="${k}">${l}</option>`)}</select></label>
        <label class="row"><span class="lbl">Dia do vencimento</span><input class="inline num" data-f="due" inputmode="numeric" value="10" style="flex:0 1 60px"></label>
      </div>
      <p class="note">A primeira mensalidade entra no financeiro do mês; o termo de adesão e a cobrança automática vêm com o gateway de pagamento.</p>`,
    actions: [{ label: 'Criar a adesão', run: async (dlg) => {
      if (!patient) throw new Error('Escolha a criança.');
      const f = (k) => dlg.querySelector(`[data-f="${k}"]`).value;
      await api('/api/staff/memberships', { method: 'POST', body: { patient_id: patient.id, plan_id: Number(f('plan')), billing: f('billing'), due_day: Number(f('due')) || 10 } });
      toast(`${patient.first_name} entrou no plano.`); refresh();
    } }],
  });
  const q = d.el.querySelector('[data-q]');
  const box = d.el.querySelector('[data-results]');
  let results = [];
  const search = debounce(async () => {
    try {
      const res = await api(`/api/staff/patients?q=${encodeURIComponent(q.value)}`);
      results = res.patients.filter((p) => !p.plan).slice(0, 5);
      box.innerHTML = String(html`${results.map((p) => html`<button class="opt" type="button" data-pick="${p.id}" aria-pressed="${patient && patient.id === p.id}" style="min-height:52px"><span class="radio" aria-hidden="true"></span><span class="grow"><b>${p.name}</b><span class="t-small muted" style="display:block">${p.age_short} · ${p.family}</span></span></button>`)}`);
    } catch (e) { fail(e); }
  }, 220);
  q.addEventListener('input', search);
  box.addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-pick]');
    if (!b) return;
    patient = results.find((p) => p.id === Number(b.dataset.pick));
    box.querySelectorAll('[data-pick]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  });
  search();
}

// ---- financeiro ---------------------------------------------------------------------------------------------------------
export async function finance(view, params, app) {
  const ym = params.query.m || app.today.slice(0, 7);
  const r = await api(`/api/staff/finance?month=${ym}`);
  const shift = (n) => { const [y, m] = ym.split('-').map(Number); const d = new Date(y, m - 1 + n, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`; };
  let table = false;
  const pct = r.received ? Math.round(100 * r.result / r.received) : 0;
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Financeiro</h1><p class="t-small muted">${r.label} · só a sua prática</p></div>
      <button class="iconbtn" type="button" data-act="month" data-m="${shift(-1)}" aria-label="Mês anterior">${icon('chevL')}</button>
      <button class="iconbtn" type="button" data-act="month" data-m="${shift(1)}" aria-label="Próximo mês" ${ym >= app.today.slice(0, 7) ? raw('disabled') : ''}>${icon('chevR')}</button>
      <a class="btn ghost" href="/api/staff/finance/export?month=${ym}" download>${icon('download')}Exportar para o contador</a>
    </div>
    <div class="grid-auto">
      <div class="glass stat"><span class="lbl">Recebido</span><span class="val">${money(r.received)}</span>
        ${r.delta_pct == null ? html`<span class="sub">primeiro mês com dados</span>` : html`<span class="sub ${r.delta_pct >= 0 ? 'up' : 'down'}">${icon(r.delta_pct >= 0 ? 'arrowUp' : 'arrowDown')}${Math.abs(r.delta_pct).toLocaleString('pt-BR')}% sobre ${monthName(Number(shift(-1).slice(5)))}</span>`}</div>
      <div class="glass stat"><span class="lbl">A receber</span><span class="val">${money(r.receivable)}</span><span class="sub">${r.overdue ? `${money(r.overdue)} em atraso` : 'nada em atraso'}</span></div>
      <div class="glass stat"><span class="lbl">Despesas</span><span class="val">${money(r.spent)}</span><span class="sub">${r.expenses.length} lançamento${r.expenses.length === 1 ? '' : 's'}</span></div>
      <div class="glass stat"><span class="lbl">Resultado</span><span class="val">${money(r.result)}</span><span class="sub">${r.received ? `${pct}% do recebido` : '—'}</span></div>
    </div>
    <section class="glass card">
      <div class="phead center"><div><h2 class="t-h2">Receita por mês</h2><span class="t-small muted">o recebido nos últimos seis meses</span></div>
        <div style="display:flex;flex-wrap:wrap;gap:8px 18px"><span class="key"><i style="background:var(--s1)"></i>Planos</span><span class="key"><i style="background:var(--s2)"></i>Consultas avulsas</span></div></div>
      ${revenueBars(r.series)}
      <div style="display:flex;justify-content:flex-end;margin-top:8px"><button class="linkbtn t-small" type="button" data-act="table">Ver tabela</button></div>
      <div data-table hidden>${revenueTable(r.series)}</div>
    </section>
    <div class="cols">
      <section class="glass card colmain">
        <div class="phead"><h2 class="t-h2">Recebimentos</h2><span class="t-small muted">${r.invoices_pending ? `${r.invoices_pending} nota${r.invoices_pending > 1 ? 's' : ''} para emitir` : 'notas em dia'}</span></div>
        <div class="tblbox" style="margin-top:10px"><table class="tbl" style="min-width:640px"><thead><tr><th>Data</th><th>Família</th><th>O quê</th><th>Forma</th><th class="r">Valor</th><th>Nota</th></tr></thead><tbody>
          ${r.recent.length ? r.recent.map((c) => html`<tr><td class="num">${dateBR(c.paid_on)}</td><td>${(c.family || '').replace('Família ', '')}${c.patient ? html`<span class="t-small muted"> · ${c.patient.split(' ')[0]}</span>` : ''}</td><td>${c.description}</td><td>${r.methods[c.method] || c.method || '—'}</td><td class="r">${money(c.amount_cents)}</td>
            <td>${c.invoice === 'emitida' ? html`<span class="pill ok">Emitida</span>` : c.invoice === 'emitir' ? html`<button class="btn ghost small" type="button" data-act="invoice" data-id="${c.id}">Já emiti</button>` : html`<span class="pill">Sem nota</span>`}</td></tr>`)
            : html`<tr><td colspan="6" class="muted">Nada recebido neste mês.</td></tr>`}
        </tbody></table></div>
      </section>
      <div class="colside">
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">A receber</h2><span class="t-small muted">${money(r.receivable)}</span></div>
          ${r.open.length ? r.open.map((c) => html`<div class="li" style="flex-wrap:wrap"><div class="grow" style="flex-basis:100%"><b>${c.patient || c.family}</b><p class="t-small muted">${c.description} · ${c.due_on < app.today ? 'venceu' : 'vence'} ${dateBR(c.due_on)}</p></div><span class="t-small grow" style="font-weight:700">${money(c.amount_cents)}</span>
            ${c.due_on < app.today ? html`<span class="pill late">${Math.round((new Date(app.today) - new Date(c.due_on)) / 86400000)} d</span>` : ''}<button class="btn ghost small" type="button" data-act="pay" data-id="${c.id}">Recebida</button></div>`)
            : html`<p class="t-small muted" style="margin-top:8px">Nada em aberto.</p>`}
        </section>
        <section class="glass card">
          <div class="phead"><h2 class="t-h2">Despesas</h2><button class="linkbtn t-small" type="button" data-act="expense">+ Lançar</button></div>
          ${r.expenses.map((e) => html`<div class="li"><span class="grow">${e.description}</span><span class="t-small" style="font-weight:700">${money(e.amount_cents)}</span><button class="iconbtn small" type="button" data-act="del-exp" data-id="${e.id}" aria-label="Apagar ${e.description}">${icon('x')}</button></div>`)}
          <div class="li"><b class="grow">Total</b><b>${money(r.spent)}</b></div>
        </section>
      </div>
    </div>`);
  bindBars(view);
  actions(view, {
    month: (el) => { location.hash = `#/financeiro?m=${el.dataset.m}`; },
    table: (el) => { table = !table; view.querySelector('[data-table]').hidden = !table; el.textContent = table ? 'Esconder a tabela' : 'Ver tabela'; },
    invoice: async (el) => { await api(`/api/staff/charges/${el.dataset.id}/invoice`, { method: 'POST', body: { status: 'emitida' } }); toast('Nota marcada como emitida.'); refresh(); },
    pay: async (el) => {
      const d = dialog({
        title: 'Registrar o pagamento',
        body: html`<div class="seg" role="group" aria-label="Forma">${Object.entries({ pix: 'PIX', cartao: 'Cartão', boleto: 'Boleto', dinheiro: 'Dinheiro' }).map(([k, l], i) => html`<button type="button" data-m="${k}" aria-pressed="${i === 0}">${l}</button>`)}</div>`,
        onMount: (dlg) => dlg.addEventListener('click', (ev) => { const b = ev.target.closest('[data-m]'); if (b) dlg.querySelectorAll('[data-m]').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }),
        actions: [{ label: 'Recebida', run: async (dlg) => {
          await api(`/api/staff/charges/${el.dataset.id}/pay`, { method: 'POST', body: { method: dlg.querySelector('[data-m][aria-pressed="true"]').dataset.m } });
          toast('Pagamento registrado.'); refresh();
        } }],
      });
      return d;
    },
    expense: () => dialog({
      title: 'Lançar despesa',
      body: html`<div class="rows">
        <label class="row"><span class="lbl">O quê</span><input class="inline" data-f="desc" placeholder="Aluguel da sala"></label>
        <label class="row"><span class="lbl">Valor</span><span class="muted">R$</span><input class="inline num" data-f="value" inputmode="decimal" style="flex:0 1 110px"></label>
        <label class="row"><span class="lbl">Dia</span><input class="inline" type="date" data-f="day" value="${app.today}"></label></div>`,
      actions: [{ label: 'Lançar', run: async (dlg) => {
        const f = (k) => dlg.querySelector(`[data-f="${k}"]`).value;
        await api('/api/staff/expenses', { method: 'POST', body: { description: f('desc'), amount_cents: toCents(f('value')), spent_on: f('day') } });
        toast('Despesa lançada.'); refresh();
      } }],
    }),
    'del-exp': async (el) => {
      if (!await ask('Apagar esta despesa?', '', 'Apagar', true)) return;
      await api(`/api/staff/expenses/${el.dataset.id}`, { method: 'DELETE' });
      refresh();
    },
  });
}


// ---- o consultório (como ele aparece no site) ----------------------------------------------------------------------
const ACCENTS = { agua: ['Verde-água', '#08746b'], azul: ['Azul', '#1f5fbf'], coral: ['Coral', '#b8452a'], lavanda: ['Lavanda', '#5b47c4'] };

export async function practice(view, params, app) {
  const [r, team] = await Promise.all([api('/api/staff/practice'), api('/api/staff/team')]);
  const p = r.practice;
  const invs = team.invites.filter((i) => i.status === 'pendente' || i.status === 'aceito').slice(0, 8);
  const invText = (i) => (i.status === 'pendente' ? `link enviado, vale até ${dateBR(i.expires_at)}`
    : i.kind === 'practice' ? `aceito${i.new_practice ? `: criou ${i.new_practice}` : ''}` : `aceito em ${dateBR(i.used_at)}`);
  let accent = p.accent;
  const field = (name, label, value, placeholder, extra = '') => html`<label class="row"><span class="lbl">${label}</span><input class="inline" name="${name}" value="${value || ''}" placeholder="${placeholder}" ${raw(extra)}></label>`;
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Consultório</h1><p class="t-small muted">Como o seu consultório aparece no site e para as famílias.</p></div>
    </div>
    <div class="cols">
      <form class="colmain" data-form style="gap:16px">
        <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
          <h2 class="t-h2">No alto do site</h2>
          <div class="rows">
            ${field('name', html`Nome<span class="sub">o título do site</span>`, p.name, 'Dra. Nome Sobrenome', 'required maxlength="80"')}
            ${field('title', html`Acima do nome<span class="sub">a especialidade, curta</span>`, p.title, 'Pediatra', 'maxlength="40"')}
            ${field('registry', 'CRM e RQE', p.registry, 'CRM-UF 000000 · RQE 00000', 'maxlength="80"')}
          </div>
          <label style="display:flex;flex-direction:column;gap:8px"><span class="t-cap">Apresentação</span>
            <textarea class="area" name="bio" maxlength="600" placeholder="Duas ou três frases para as famílias: como você atende e o que valoriza.">${p.bio || ''}</textarea></label>
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:14px">
          <h2 class="t-h2">Onde encontrar</h2>
          <div class="rows">
            ${field('address', 'Endereço', p.address, 'Rua, número, bairro, cidade', 'maxlength="160" autocomplete="street-address"')}
            ${field('phone', 'Telefone', p.phone, '(00) 00000-0000', 'maxlength="40" inputmode="tel"')}
          </div>
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:12px">
          <h2 class="t-h2">Cor do destaque</h2>
          <div data-accents role="group" aria-label="Cor do destaque" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px">
            ${Object.entries(ACCENTS).map(([k, [label, hex]]) => html`<button class="opt" type="button" data-accent="${k}" aria-pressed="${k === accent}" style="min-height:48px;padding:10px 14px"><span class="swatch" style="--sw:${hex}"></span><b style="font-size:14px">${label}</b></button>`)}
          </div>
          <p class="note" style="padding:0">A cor dos botões e dos destaques no site, no app da família e aqui.</p>
        </section>
        <div style="display:flex;justify-content:flex-end"><button class="btn big" type="submit">Salvar</button></div>
      </form>
      <div class="colside" style="max-width:380px">
        <section class="glass card" style="display:flex;flex-direction:column;gap:12px">
          <h2 class="t-h2">O endereço do site</h2>
          ${r.domains.length
            ? html`<div class="domains">${r.domains.map((d) => html`<span class="pill strong">${icon('globe')}${d}</span>`)}</div>
                <p class="t-small muted pretty">É por ele que as famílias entram e marcam. Para trocar de domínio ou usar mais um, fale com a plataforma.</p>`
            : html`<p class="t-small muted pretty">O consultório ainda não tem domínio próprio. Fale com a plataforma para ligar um.</p>`}
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:6px">
          <div class="phead center"><h2 class="t-h2">Equipe</h2><button class="btn ghost small" type="button" data-team="invite">${icon('plus')}Convidar atendente</button></div>
          <div>${team.members.map((m) => html`<div class="li"><span class="av sm">${initials(m.name)}</span>
            <span class="grow" style="min-width:0"><b>${m.name}${m.me ? ' (você)' : ''}</b><span class="t-small muted" style="display:block">${m.role_label} · ${m.last_login ? `entrou ${dateBR(m.last_login)}` : 'ainda não entrou'}</span></span>
            ${m.role === 'receptionist' ? html`<button class="linkbtn t-small" type="button" data-team="remove" data-id="${m.id}" data-name="${m.name}">Tirar o acesso</button>` : ''}</div>`)}</div>
          ${invs.length ? html`<span class="t-cap" style="margin-top:8px">Convites</span>
            <div>${invs.map((i) => html`<div class="li"><span class="grow" style="min-width:0"><b>${i.kind === 'practice' ? 'Colega' : 'Atendente'}${i.label ? ` · ${i.label}` : ''}</b><span class="t-small muted" style="display:block">${invText(i)}</span></span>
              ${i.status === 'pendente' ? html`<button class="linkbtn t-small" type="button" data-team="revoke" data-id="${i.id}">Cancelar</button>` : ''}</div>`)}</div>` : ''}
        </section>
        <section class="glass card" style="display:flex;flex-direction:column;gap:10px">
          <h2 class="t-h2">Convidar um colega</h2>
          <p class="t-small muted pretty">Um colega pediatra ganha o próprio consultório, com o site e os pacientes dele. Você não vê os pacientes dele, nem ele os seus.</p>
          <div><button class="btn ghost" type="button" data-team="colleague">${icon('users')}Convidar um colega</button></div>
        </section>
      </div>
    </div>`);
  view.querySelector('.colside').addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-team]');
    if (!b) return;
    const what = b.dataset.team;
    try {
      if (what === 'invite' || what === 'colleague') {
        const colleague = what === 'colleague';
        const v = await askFields(colleague ? 'Convidar um colega' : 'Convidar atendente',
          [['label', colleague ? 'Nome do colega' : 'Nome da atendente', 'Nome e sobrenome', 'para você reconhecer o convite']], 'Gerar o link',
          colleague ? 'O link cria um consultório só do colega, separado do seu. O domínio, a plataforma liga depois.'
            : 'A pessoa cria a senha e entra na agenda, no cadastro e no dinheiro deste consultório. Nada clínico.');
        if (!v) return;
        const x = await api('/api/staff/invites', { method: 'POST', body: { kind: colleague ? 'colleague' : 'receptionist', label: v.label || null } });
        const hi = v.label ? `Olá, ${v.label.split(' ')[0]}!` : 'Olá!';
        shareLink({
          title: colleague ? 'Convite: um colega' : 'Convite: atendente', link: x.link,
          text: colleague
            ? `${hi} Estou usando o Puericorbs no consultório: agenda, acompanhamento das crianças, planos e o app das famílias, num site com o nosso domínio. Este link cria o seu consultório, com os seus pacientes só seus. Vale 7 dias: ${x.link}`
            : `${hi} Este é o seu acesso ao consultório de ${p.name} no Puericorbs. Crie a sua senha por este link (vale 7 dias): ${x.link}`,
          note: 'O link vale 7 dias e uma vez só. Se mandar para a pessoa errada, cancele aqui.',
        }).el.addEventListener('close', refresh);
      }
      if (what === 'remove' && await ask(`Tirar o acesso de ${b.dataset.name}?`, 'A pessoa deixa de entrar neste consultório na hora. O que foi registrado continua no histórico.', 'Tirar o acesso', true)) {
        await api(`/api/staff/team/${b.dataset.id}`, { method: 'DELETE' });
        toast('Acesso tirado.');
        refresh();
      }
      if (what === 'revoke' && await ask('Cancelar este convite?', 'O link deixa de abrir na hora.', 'Cancelar o convite', true)) {
        await api(`/api/staff/invites/${b.dataset.id}/revoke`, { method: 'POST' });
        refresh();
      }
    } catch (e) { fail(e); }
  });
  view.querySelector('[data-accents]').addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-accent]');
    if (!b) return;
    accent = b.dataset.accent;
    view.querySelectorAll('[data-accent]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  });
  view.querySelector('[data-form]').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const body = { ...Object.fromEntries(new FormData(ev.target)), accent };
    try {
      const saved = await api('/api/staff/practice', { method: 'PUT', body });
      Object.assign(app.site.practice, saved.practice);
      document.documentElement.dataset.accent = saved.practice.accent;
      document.title = saved.practice.name;
      const brand = document.querySelector('.brand .practice');
      if (brand) brand.textContent = saved.practice.name;
      toast('Salvo. O site já mostra assim.');
    } catch (e) { fail(e); }
  });
}

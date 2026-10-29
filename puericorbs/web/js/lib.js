// O básico da página: o html seguro (tudo o que vem de fora é escapado), a API, os formatos, os ícones, os diálogos e
// os avisos. Sem framework e sem build: cada tela é uma função que monta HTML e liga os eventos por delegação.

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s ?? ''));
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const part = (v) => (v instanceof Raw ? v.s : Array.isArray(v) ? v.map(part).join('') : v === false || v == null ? '' : esc(v));
export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += part(v) + strings[i + 1]; });
  return new Raw(out);
}

export async function api(path, { method = 'GET', body, form } = {}) {
  const opts = { method, headers: { 'X-PC': '1' }, credentials: 'same-origin' };
  if (form) opts.body = form;
  else if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, opts); } catch { throw new Error('Sem conexão com o servidor. Confira a internet e tente de novo.'); }
  let data = null;
  try { data = await res.json(); } catch { /* resposta sem corpo */ }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `Algo deu errado (${res.status}). Tente de novo.`);
    err.status = res.status;
    throw err;
  }
  return data;
}

// ---- formatos -----------------------------------------------------------------------------------------------------
const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
export const money = (cents) => BRL.format((cents || 0) / 100).replace(/ /g, ' ');
export const moneyShort = (cents) => {
  const v = (cents || 0) / 100;
  if (v >= 1000) return `R$ ${(v / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil`;
  return money(cents);
};
export const toCents = (text) => {
  const clean = String(text || '').replace(/[^\d,.-]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.');
  const v = parseFloat(clean);
  return Number.isFinite(v) ? Math.round(v * 100) : 0;
};
export const centsInput = (cents) => ((cents || 0) / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const WD = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
const MO = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
export const parseDate = (iso) => { const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number); return new Date(y, m - 1, d); };
export const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export const dateBR = (iso) => { if (!iso) return ''; const d = parseDate(iso); return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`; };
export const dateFull = (iso) => { if (!iso) return ''; const d = parseDate(iso); return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`; };
export const dateLong = (iso) => { const d = parseDate(iso); return `${WD[d.getDay()]}, ${d.getDate()} de ${MO[d.getMonth()]}`; };
export const weekday = (iso) => WD[parseDate(iso).getDay()];
export const monthName = (m) => MO[m - 1];
export const addDays = (iso, n) => { const d = parseDate(iso); d.setDate(d.getDate() + n); return isoDate(d); };
export function relDay(iso, todayIso) {
  const days = Math.round((parseDate(iso) - parseDate(todayIso)) / 86400000);
  if (days === 0) return 'hoje';
  if (days === 1) return 'amanhã';
  if (days === -1) return 'ontem';
  if (days > 0) return `em ${days} dias`;
  return `há ${-days} dias`;
}
export function ago(isoDateTime, now = new Date()) {
  const t = new Date(isoDateTime.replace(' ', 'T'));
  const min = Math.max(0, Math.round((now - t) / 60000));
  if (min < 1) return 'agora';
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `há ${h} h`;
  const d = Math.round(h / 24);
  return d === 1 ? 'ontem' : `há ${d} dias`;
}
export const initials = (name) => {
  const parts = String(name || '').replace(/^(Dra?\.)\s+/, '').split(/\s+/).filter(Boolean);
  return ((parts[0] || '?')[0] + (parts.length > 1 && /^(Dra?\.)/.test(name || '') ? parts[parts.length - 1][0] : '')).toUpperCase();
};
export const firstName = (name) => String(name || '').split(/\s+/)[0];

// ---- ícones (traço, como no protótipo) ------------------------------------------------------------------------------
const P = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h14V9.5"/><path d="M10 20v-6h4v6"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="16" rx="3"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20Z"/>',
  folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2.5h6.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5Z"/>',
  message: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.5 4v-4h-1A.5.5 0 0 1 4 15.5Z"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15Z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.7 2.7L16 9.7"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  alert: '<path d="M10.3 4.3 2.8 17.5a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z"/><path d="M12 9.5v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  syringe: '<path d="m14.5 3.5 6 6"/><path d="m17.5 6.5-9.5 9.5H5v-3l9.5-9.5"/><path d="m5 19 3-3"/><path d="m9.5 10.5 2 2M12 8l2 2"/>',
  camera: '<path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.8L10 3.5h4L15.7 6h1.8A2.5 2.5 0 0 1 20 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5Z"/><circle cx="12" cy="12.5" r="3.5"/>',
  upload: '<path d="M12 15V4M7.5 8.5 12 4l4.5 4.5"/><path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5"/><path d="M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16"/>',
  flag: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
  doc: '<path d="M7 3h7l5 5v11.5a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 19.5v-15A1.5 1.5 0 0 1 7.5 3Z"/><path d="M14 3v5h5M9 13h6M9 16.5h6"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><circle cx="9" cy="9.5" r="1.8"/><path d="m21 15.5-5-5L5 20"/>',
  receipt: '<path d="M6 3h12v18l-2.5-1.5L13 21l-2.5-1.5L8 21l-2-1.5Z"/><path d="M9 8h6M9 11.5h6M9 15h4"/>',
  flask: '<path d="M9 3h6M10 3v6.5L4.8 18.3A1.8 1.8 0 0 0 6.4 21h11.2a1.8 1.8 0 0 0 1.6-2.7L14 9.5V3"/><path d="M7.5 15h9"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M6 12h12"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevR: '<path d="m9 6 6 6-6 6"/>',
  chevL: '<path d="m15 6-6 6 6 6"/>',
  chevD: '<path d="m6 9 6 6 6-6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.2a6.5 6.5 0 0 1 3.5 5.8"/>',
  card: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18M7 15h3"/>',
  sliders: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2"/><circle cx="10" cy="17" r="2"/>',
  repeat: '<path d="M17 2.5 20.5 6 17 9.5"/><path d="M3.5 11V9.5A3.5 3.5 0 0 1 7 6h13.5"/><path d="M7 21.5 3.5 18 7 14.5"/><path d="M20.5 13v1.5A3.5 3.5 0 0 1 17 18H3.5"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  inbox: '<path d="M3 13.5 5.5 5h13l2.5 8.5V19a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19Z"/><path d="M3 13.5h5l1.5 2.5h5l1.5-2.5h5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z"/>',
  phone: '<path d="M5 4h3.5l1.5 4.5-2 1.5a12 12 0 0 0 6 6l1.5-2 4.5 1.5V19a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  pin: '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.3"/>',
  book: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v16H6.5A1.5 1.5 0 0 0 5 20.5v-16Z"/><path d="M5 20.5A1.5 1.5 0 0 0 6.5 22H19"/>',
  logout: '<path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15"/><path d="M10 16.5 14.5 12 10 7.5M14.5 12H4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z"/>',
  arrowUp: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  arrowDown: '<path d="M12 5v14M6 13l6 6 6-6"/>',
  stetho: '<path d="M6 3v5a4 4 0 0 0 8 0V3"/><path d="M10 12v2.5a4.5 4.5 0 0 0 9 0V13"/><circle cx="19" cy="11" r="2"/>',
  cash: '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v5M18 9.5v5"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.2 1.2"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.2-1.2"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/>',
};
export const icon = (name, extra = '') => raw(`<svg class="ic ${extra}" viewBox="0 0 24 24" aria-hidden="true">${P[name] || ''}</svg>`);

// ---- avisos e diálogos ----------------------------------------------------------------------------------------------
export function toast(message, kind = '') {
  let box = document.querySelector('.toasts');
  if (!box) { box = document.createElement('div'); box.className = 'toasts'; box.setAttribute('role', 'status'); document.body.append(box); }
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  box.append(el);
  setTimeout(() => el.remove(), kind === 'err' ? 6000 : 3200);
}
export const fail = (err) => toast(err.message || String(err), 'err');

// Um diálogo de vidro. `render(body)` monta o miolo; `actions`: [{label, kind, run}] — `run` devolve false para não fechar.
export function dialog({ title, body, actions = [], onMount, wide = false }) {
  const dlg = document.createElement('dialog');
  dlg.className = 'dlg';
  if (wide) dlg.style.width = 'min(760px, calc(100vw - 24px))';
  dlg.innerHTML = String(html`
    <div class="dlg-head"><h2 class="t-h2">${title}</h2>
      <button class="iconbtn small" type="button" data-close aria-label="Fechar">${icon('x')}</button></div>
    <div class="dlg-body">${body}</div>
    ${actions.length ? html`<div class="dlg-foot">${actions.map((a, i) => html`<button class="btn ${a.kind || ''}" type="button" data-i="${i}" ${a.disabled ? raw('disabled') : ''}>${a.label}</button>`)}</div>` : ''}`);
  document.body.append(dlg);
  const close = () => { dlg.close(); dlg.remove(); };
  dlg.addEventListener('click', async (ev) => {
    if (ev.target === dlg || ev.target.closest('[data-close]')) { close(); return; }
    const b = ev.target.closest('.dlg-foot [data-i]');
    if (!b) return;
    const act = actions[Number(b.dataset.i)];
    if (!act.run) { close(); return; }
    b.disabled = true;
    try {
      const keep = await act.run(dlg);
      if (keep !== false) close();
    } catch (e) { fail(e); }
    finally { b.disabled = false; }
  });
  dlg.addEventListener('cancel', () => dlg.remove());
  dlg.showModal();
  if (onMount) onMount(dlg, close);
  return { el: dlg, close };
}

export function ask(title, text, verb = 'Confirmar', danger = false) {
  return new Promise((resolve) => {
    const d = dialog({
      title, body: text ? html`<p class="muted pretty">${text}</p>` : '',
      actions: [{ label: 'Cancelar', kind: 'ghost', run: () => resolve(false) }, { label: verb, kind: danger ? 'danger' : '', run: () => resolve(true) }],
    });
    d.el.addEventListener('close', () => resolve(false));
  });
}

// liga os cliques de [data-act] de um elemento a um objeto de ações
export function actions(root, map) {
  root.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-act]');
    if (!el || !root.contains(el)) return;
    const fn = map[el.dataset.act];
    if (fn) { ev.preventDefault(); Promise.resolve(fn(el, ev)).catch(fail); }
  });
}

export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

export function fileIcon(kind) {
  return { exame: 'flask', pedido: 'flask', foto: 'image', video: 'camera', caderneta: 'image', receita: 'doc', atestado: 'doc',
    resumo: 'doc', nota: 'receipt', recibo: 'receipt', comprovante: 'receipt', documento: 'doc' }[kind] || 'doc';
}

export function statusPill(status, label) {
  const cls = { agendado: 'booked', confirmado: 'booked', chegou: 'todo', em_atendimento: 'strong', atendido: '', faltou: 'late', cancelado: '' }[status] ?? '';
  return html`<span class="pill ${cls}">${status === 'atendido' ? icon('check') : ''}${label}</span>`;
}

export function careTick(item) {
  const ic = { consulta: 'calendar', vacina: 'syringe', marco: 'flag', exame: 'flask', tarefa: 'camera', orientacao: 'book', retorno: 'calendar' }[item.type] || 'check';
  return html`<span class="tick">${icon(item.status === 'feito' ? 'check' : ic)}</span>`;
}

export function carePill(item, todayIso) {
  if (item.status === 'feito') return '';
  if (item.status === 'atrasado') return html`<span class="pill late">${icon('alert')}Atrasado</span>`;
  if (item.status === 'agendado') return html`<span class="pill booked">${icon('calendar')}Agendado</span>`;
  if (item.type === 'marco') return '';
  if (item.date && item.date > todayIso) return html`<span class="pill todo">${relDay(item.date, todayIso).replace(/^em /, 'Em ')}</span>`;
  return html`<span class="pill todo">A fazer</span>`;
}

// O número para o WhatsApp: o do Brasil ganha o 55 (com o DDD, 10 ou 11 dígitos); com +, vale como está. Sem DDD, ''.
export function waNumber(phone) {
  const intl = /^\s*\+/.test(String(phone || ''));
  let d = String(phone || '').replace(/\D/g, '');
  if (!intl) d = d.replace(/^0+/, '');
  if (!intl && (d.length === 10 || d.length === 11)) d = `55${d}`;
  return d.length >= (intl ? 8 : 12) && d.length <= 15 ? d : '';
}
// a conversa do WhatsApp já com a mensagem escrita (sem número, a pessoa escolhe o contato)
export const waLink = (phone, text) => `https://wa.me/${waNumber(phone)}?text=${encodeURIComponent(text)}`;

// O link de um convite: copiar, mandar pelo WhatsApp (já com a mensagem e, se houver, o telefone) ou pelo compartilhar
// do celular. Quem gera o link é quem manda: nada sai do Puericorbs sozinho.
export function shareLink({ title, intro, link, text, phone, note }) {
  const message = text || link;
  const wa = waLink(phone, message);
  const d = dialog({
    title,
    body: html`${intro ? html`<p class="muted pretty">${intro}</p>` : ''}
      <label class="field">${icon('link')}<input data-link readonly value="${link}" aria-label="O link" style="font-size:13px"></label>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        <button class="btn" type="button" data-share="copy">${icon('copy')}Copiar o link</button>
        <a class="btn ghost" href="${wa}" target="_blank" rel="noopener">${icon('message')}Mandar pelo WhatsApp</a>
        ${navigator.share ? html`<button class="btn ghost" type="button" data-share="native">${icon('upload')}Outro app</button>` : ''}
      </div>
      ${note ? html`<p class="note" style="padding:0">${note}</p>` : ''}`,
  });
  const input = d.el.querySelector('[data-link]');
  d.el.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-share]');
    if (!b) return;
    if (b.dataset.share === 'native') {
      try { await navigator.share({ title, text: message }); } catch { /* a pessoa desistiu */ }
      return;
    }
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      input.select();
      document.execCommand('copy');
    }
    toast('Link copiado.');
  });
  input.addEventListener('focus', () => input.select());
  return d;
}

// Um formulário curto num diálogo: rows = [[name, rótulo, exemplo, explicação?]]. Devolve os valores ou null.
export function askFields(title, rows, verb, intro = '') {
  return new Promise((resolve) => {
    let done = false;
    const d = dialog({
      title,
      body: html`${intro ? html`<p class="muted pretty">${intro}</p>` : ''}<div class="rows">${rows.map(([name, label, placeholder, sub]) => html`<label class="row"><span class="lbl">${label}${sub ? html`<span class="sub">${sub}</span>` : ''}</span><input class="inline" name="${name}" placeholder="${placeholder}"></label>`)}</div>`,
      actions: [{ label: 'Cancelar', kind: 'ghost' }, { label: verb, run: (el) => {
        done = true;
        resolve(Object.fromEntries([...el.querySelectorAll('[name]')].map((i) => [i.name, i.value.trim()])));
      } }],
    });
    d.el.addEventListener('close', () => { if (!done) resolve(null); });
    d.el.querySelector('[name]')?.focus();
  });
}

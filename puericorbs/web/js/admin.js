// O painel da administração da plataforma (#/admin, em qualquer site nosso): os consultórios em números, a equipe de
// cada um, os convites e o que aconteceu. A ficha e o app da família, a administração vê entrando no consultório
// "vendo como" alguém dele (a faixa no topo da página é do main.js); tudo o que ela faz lá fica no registro dele.
import { api, html, icon, fail, toast, dialog, ask, askFields, initials, dateBR, shareLink, debounce } from './lib.js';

const ACCENT_HEX = { agua: '#08746b', azul: '#1f5fbf', coral: '#b8452a', lavanda: '#5b47c4' };
const STATUS = { pendente: ['Pendente', 'booked'], aceito: ['Aceito', 'ok'], cancelado: ['Cancelado', ''], vencido: ['Venceu', 'todo'] };
const ACTION = {
  convite_gerado: 'Convite gerado', convite_aceito: 'Convite aceito', convite_cancelado: 'Convite cancelado',
  consultorio_criado: 'Consultório criado', dominio_ligado: 'Domínio ligado', equipe_removida: 'Acesso tirado',
  admin_entrou: 'Nova pessoa na administração', vendo_como: 'Entrou vendo como',
};

export async function route(app) {
  const root = document.getElementById('app');
  if (location.hash === '#/admin/entrada-vencida') {
    history.replaceState(null, '', '#/admin');
    toast('O link de entrada venceu ou já foi usado. Entre de novo pelo painel.', 'err');
  }
  if (!app.me || !app.me.is_platform_admin) { login(app, root); return; }
  let d;
  try {
    d = await api('/api/admin/overview');
  } catch (e) {
    root.innerHTML = String(html`<div class="platform"><div class="glass error-box"><h1 class="t-title">Não deu para abrir o painel</h1><p class="muted">${e.message}</p><button class="btn ghost" type="button" onclick="location.reload()">Tentar de novo</button></div></div>`);
    return;
  }
  render(app, root, d);
}

function login(app, root) {
  root.innerHTML = String(html`
    <div class="platform" style="max-width:480px">
      <header style="display:flex;align-items:center;gap:12px"><span class="logo" style="width:40px;height:40px"></span><span class="wordmark" style="font-size:28px">puericorbs</span></header>
      <div class="glass card" style="display:flex;flex-direction:column;gap:14px">
        <h1 class="t-h2">Administração da plataforma</h1>
        ${app.me ? html`<p class="pill late long">Esta conta não é da administração.</p><button class="btn ghost" type="button" data-act="logout">Sair desta conta</button>` : html`
          <form data-login style="display:flex;flex-direction:column;gap:10px">
            <label class="field">${icon('message')}<input name="email" type="email" autocomplete="username" placeholder="E-mail" aria-label="E-mail" required></label>
            <label class="field">${icon('eye')}<input name="password" type="password" autocomplete="current-password" placeholder="Senha" aria-label="Senha" required></label>
            <button class="btn big wide" type="submit">Entrar</button>
          </form>`}
        <p class="t-small muted pretty">A conta da administração nasce de um convite. Daqui se acompanham os consultórios e se entra em cada um, vendo como quem usa.</p>
      </div>
    </div>`);
  root.querySelector('[data-act="logout"]')?.addEventListener('click', () => app.logout());
  root.querySelector('[data-login]')?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    try {
      await api('/api/auth/login', { method: 'POST', body: { email: fd.get('email'), password: fd.get('password') } });
      location.reload();
    } catch (e) { fail(e); }
  });
}

const n = (value, one, many) => `${value} ${value === 1 ? one : many}`;
const when = (iso) => (iso ? `${dateBR(iso)} ${iso.slice(11, 16)}` : '');

function practiceCard(p) {
  const m = p.metrics;
  return html`<article class="glass pcard">
    <div style="display:flex;align-items:center;gap:12px">
      <span class="av lg">${initials(p.name)}</span>
      <div class="grow" style="min-width:0"><h3 class="t-h3">${p.name}</h3><p class="t-small muted">${p.clinic && p.clinic !== p.name ? `${p.clinic} · ` : ''}${p.title}${p.registry ? ` · ${p.registry}` : ''} · desde ${dateBR(p.created_at)}</p></div>
      <span class="swatch" style="--sw:${ACCENT_HEX[p.accent] || ACCENT_HEX.agua}" title="Cor do destaque"></span>
    </div>
    <div class="domains">
      ${p.domains.map((d) => html`<a class="pill strong" href="https://${d}" target="_blank" rel="noopener">${icon('globe')}${d}</a>`)}
      ${p.domains.length ? '' : html`<span class="pill todo long">${icon('alert')}Sem domínio${p.requested_domain ? `: pediu ${p.requested_domain}` : ''}</span>`}
    </div>
    <div class="rows">
      ${p.members.length ? p.members.map((x) => html`<div class="row"><span class="lbl">${x.name}<span class="sub">${x.role_label} · ${x.email} · ${x.last_login ? `entrou ${dateBR(x.last_login)}` : 'não entrou'}</span></span>
          ${p.can_enter ? html`<button class="btn ghost small" type="button" data-act="as-user" data-id="${p.id}" data-user="${x.id}">${icon('eye')}Ver como</button>` : ''}</div>`)
        : html`<div class="row"><span class="lbl">Ninguém ainda<span class="sub">quem atende entra pelo convite</span></span></div>`}
    </div>
    <p class="t-small pretty">${n(m.patients, 'criança', 'crianças')} · ${n(m.families, 'família', 'famílias')} (${m.family_accounts} no app) · ${n(m.visits_30d, 'consulta', 'consultas')} em 30 dias · ${m.next_7d} nos próximos 7${p.pending_invites ? ` · ${n(p.pending_invites, 'convite pendente', 'convites pendentes')}` : ''}</p>
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px">
      ${p.can_enter && m.families ? html`<button class="btn ghost small" type="button" data-act="as-family" data-id="${p.id}">${icon('users')}Ver como uma família</button>` : ''}
      <button class="btn ghost small" type="button" data-act="domain" data-id="${p.id}">${icon('globe')}Ligar domínio</button>
      ${p.has_clinician ? '' : html`<button class="btn ghost small" type="button" data-act="inv-clinician" data-id="${p.id}">${icon('link')}Convite: pediatra</button>`}
      ${p.can_enter ? '' : html`<span class="t-small muted">Para entrar nele, ligue um domínio.</span>`}
    </div>
  </article>`;
}

function inviteRow(i) {
  const [label, cls] = STATUS[i.status] || [i.status, ''];
  // a equipe: o papel e onde (a pediatra de um consultório criado vazio, ou alguém da equipe de um consultório)
  const what = i.kind !== 'staff' ? i.kind_label : i.practice && i.role === 'clinician' ? `Pediatra de ${i.practice}` : `${i.role_label} · ${i.clinic}`;
  const meta = [i.label, i.new_practice ? `criou ${i.new_practice}` : null, i.created_by ? `por ${i.created_by}` : null,
    i.status === 'pendente' ? `vence ${dateBR(i.expires_at)}` : i.used_at ? `${dateBR(i.used_at)}${i.used_by ? ` · ${i.used_by}` : ''}` : `de ${dateBR(i.created_at)}`];
  return html`<div class="li">
    <span class="grow" style="min-width:0"><b>${what}</b><span class="t-small muted" style="display:block">${meta.filter(Boolean).join(' · ')}</span></span>
    <span class="pill ${cls}">${label}</span>
    ${i.status === 'pendente' ? html`<button class="linkbtn t-small" type="button" data-act="revoke" data-id="${i.id}">Cancelar</button>` : ''}
  </div>`;
}

function render(app, root, d) {
  const t = d.totals;
  const theme = app.theme();
  root.innerHTML = String(html`
    <div class="platform">
      <header style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px">
        <div style="display:flex;align-items:center;gap:12px"><span class="logo" style="width:40px;height:40px"></span>
          <div><span class="wordmark" style="font-size:28px">puericorbs</span><p class="t-small muted">Administração · ${app.me.name}</p></div></div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="iconbtn small" type="button" data-act="theme" aria-label="Tema: ${theme}" title="Tema: ${theme}">${icon(theme === 'escuro' ? 'moon' : 'sun')}</button>
          <button class="btn ghost small" type="button" data-act="logout">Sair</button></div>
      </header>
      <div class="grid-auto">
        <div class="glass stat"><span class="lbl">Consultórios</span><span class="val">${t.practices}</span><span class="sub">${t.clinicians} com pediatra</span></div>
        <div class="glass stat"><span class="lbl">Crianças</span><span class="val">${t.patients}</span><span class="sub">${n(t.families, 'família', 'famílias')}</span></div>
        <div class="glass stat"><span class="lbl">Consultas em 30 dias</span><span class="val">${t.visits_30d}</span><span class="sub">${t.next_7d} marcadas para os próximos 7</span></div>
      </div>
      <section class="glass card" style="display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between">
        <div style="flex:1 1 260px"><h2 class="t-h2">Convidar</h2><p class="t-small muted pretty">O link vale 7 dias e uma vez só. Quem manda é você: nada sai daqui sozinho.</p></div>
        <div style="display:flex;flex-wrap:wrap;gap:8px">
          <button class="btn" type="button" data-act="inv-practice">${icon('plus')}Pediatra com consultório próprio</button>
          <button class="btn ghost" type="button" data-act="new-practice">Consultório vazio</button>
          <button class="btn ghost" type="button" data-act="inv-admin">Administração</button>
        </div>
      </section>
      <section style="display:flex;flex-direction:column;gap:14px">
        <h2 class="t-h2">Consultórios</h2>
        <div class="grid-cards">${d.practices.map(practiceCard)}</div>
      </section>
      <div class="cols">
        <section class="glass card colmain" style="display:flex;flex-direction:column;gap:4px">
          <h2 class="t-h2">Convites</h2>
          ${d.invites.length ? d.invites.map(inviteRow) : html`<p class="empty">Nenhum convite ainda.</p>`}
          <p class="note" style="padding:8px 0 0">Os convites das famílias ficam com cada consultório: aqui não aparecem.</p>
        </section>
        <section class="glass card colside" style="display:flex;flex-direction:column;gap:4px">
          <h2 class="t-h2">O que aconteceu</h2>
          ${d.log.length ? d.log.map((l) => html`<div class="li"><span class="grow" style="min-width:0"><b>${ACTION[l.action] || l.action}</b><span class="t-small muted" style="display:block">${[l.detail, l.practice && !(l.detail || '').includes(l.practice) ? l.practice : null, l.user].filter(Boolean).join(' · ')}</span></span><span class="t-small muted" style="white-space:nowrap">${when(l.at)}</span></div>`) : html`<p class="empty">Nada ainda.</p>`}
        </section>
      </div>
      <p class="t-small muted">Na administração: ${d.admins.map((a) => a.name).join(', ')}.</p>
    </div>`);
  root.onclick = (ev) => {
    const b = ev.target.closest('[data-act]');
    if (b) act(app, b.dataset.act, Number(b.dataset.id) || null, d, b);
  };
}

// entrar no consultório vendo como alguém: o link de entrada abre no endereço dele (cada domínio tem a própria sessão)
async function enter(body) {
  const r = await api('/api/admin/view-as', { method: 'POST', body });
  location.href = r.url;
}

function pickFamily(p) {
  const d = dialog({
    title: 'Ver como uma família',
    body: html`<p class="t-small muted pretty">De ${p.name}. Com conta ou ainda sem: você vê o app como a família vê (ou vai ver).</p>
      <label class="field">${icon('search')}<input name="q" type="search" placeholder="Nome do responsável ou da criança" aria-label="Buscar a família" autocomplete="off"></label>
      <div class="opts" data-list style="margin-top:12px"><p class="empty">Carregando…</p></div>`,
  });
  const list = d.el.querySelector('[data-list]');
  const load = async (q) => {
    try {
      const r = await api(`/api/admin/practices/${p.id}/families?q=${encodeURIComponent(q)}`);
      list.innerHTML = String(html`${r.guardians.length ? r.guardians.map((g) => html`<button class="opt" type="button" data-g="${g.id}">
          <span class="av sm">${initials(g.name)}</span>
          <span class="grow" style="min-width:0"><b>${g.name}</b> <span class="t-small muted">${g.relation}</span>
            <span class="t-small muted" style="display:block">${[g.children.join(', '), g.account ? 'entra no app' : 'ainda sem conta'].filter(Boolean).join(' · ')}</span></span>
        </button>`) : html`<p class="empty">Nenhuma família com esse nome.</p>`}`);
    } catch (e) { fail(e); }
  };
  d.el.querySelector('input').addEventListener('input', debounce((ev) => load(ev.target.value.trim()), 250));
  list.addEventListener('click', async (ev) => {
    const b = ev.target.closest('[data-g]');
    if (!b) return;
    b.disabled = true;
    try { await enter({ practice_id: p.id, guardian_id: Number(b.dataset.g) }); } catch (e) { b.disabled = false; fail(e); }
  });
  load('');
}

async function act(app, what, id, d, el) {
  const again = () => route(app);
  try {
    if (what === 'logout') return app.logout();
    if (what === 'as-user') {
      el.disabled = true;
      try { await enter({ practice_id: id, user_id: Number(el.dataset.user) }); } finally { el.disabled = false; }
    }
    if (what === 'as-family') pickFamily(d.practices.find((x) => x.id === id));
    if (what === 'theme') {
      app.setTheme({ claro: 'escuro', escuro: 'auto', auto: 'claro' }[app.theme()]);
      return again();
    }
    if (what === 'inv-practice') {
      const v = await askFields('Pediatra com consultório próprio', [['label', 'Para quem', 'nome e sobrenome', 'só para você se lembrar']], 'Gerar o link',
        'Quem receber cria a conta e o próprio consultório; o domínio você liga depois, aqui mesmo.');
      if (!v) return;
      const r = await api('/api/admin/invites', { method: 'POST', body: { kind: 'practice', label: v.label || null } });
      shareLink({ title: 'Convite: consultório próprio', link: r.link,
        text: `Olá! Este é o convite para você ter o seu consultório no Puericorbs: agenda, acompanhamento das crianças, planos e o app das famílias, no seu domínio. Vale 7 dias: ${r.link}`,
        note: 'Quando o convite for aceito, o consultório aparece aqui, esperando o domínio.' }).el.addEventListener('close', again);
    }
    if (what === 'inv-admin') {
      if (!await ask('Convidar alguém para a administração?', 'Quem aceitar acompanha todos os consultórios, entra em cada um vendo como quem usa, liga domínios e gera convites, inclusive outros de administração.', 'Gerar o link')) return;
      const r = await api('/api/admin/invites', { method: 'POST', body: { kind: 'admin' } });
      shareLink({ title: 'Convite: administração', link: r.link, note: 'A senha da administração tem 12 ou mais caracteres.' }).el.addEventListener('close', again);
    }
    if (what === 'inv-clinician') {
      const p = d.practices.find((x) => x.id === id);
      const r = await api('/api/admin/invites', { method: 'POST', body: { kind: 'clinician', practice_id: id } });
      shareLink({ title: `Convite: pediatra de ${p.name}`, link: r.link,
        text: `Olá! Este é o link para você entrar no seu consultório no Puericorbs e criar a sua senha. Vale 7 dias: ${r.link}`,
        note: r.warning || 'Quem receber cria a senha, diz como o nome aparece no site e entra.' }).el.addEventListener('close', again);
    }
    if (what === 'new-practice') {
      const v = await askFields('Consultório vazio', [['name', 'Nome no site', 'Dra. Nome Sobrenome'], ['domain', 'Domínio', 'drnome.com.br', 'se já tiver']], 'Criar',
        'Nasce com o catálogo de serviços e a grade de segunda a sexta. Depois, o convite de quem atende.');
      if (!v) return;
      await api('/api/admin/practices', { method: 'POST', body: { name: v.name, domain: v.domain || null } });
      toast('Consultório criado.');
      again();
    }
    if (what === 'domain') {
      const p = d.practices.find((x) => x.id === id);
      const v = await askFields(`Domínio de ${p.name}`, [['host', 'Domínio', p.requested_domain || 'drnome.com.br']], 'Ligar',
        'Primeiro o Puericorbs passa a reconhecer o domínio; depois o DNS no Cloudflare aponta para o túnel.');
      if (!v) return;
      const r = await api(`/api/admin/practices/${id}/domains`, { method: 'POST', body: { host: v.host || p.requested_domain } });
      const target = r.tunnel_target || 'o endereço do túnel (cloudflared tunnel list)';
      dialog({
        title: `Falta o DNS de ${r.host}`,
        body: html`<p class="pretty">No Cloudflare, na zona <b>${r.host}</b>, dois registros:</p>
          <div class="rows">
            <div class="row"><span class="lbl">CNAME <code>@</code><span class="sub">proxy ligado (nuvem laranja)</span></span><span class="t-small" style="text-align:right;word-break:break-all">${target}</span></div>
            <div class="row"><span class="lbl">CNAME <code>www</code><span class="sub">proxy ligado (nuvem laranja)</span></span><span class="t-small" style="text-align:right;word-break:break-all">${target}</span></div>
          </div>
          <p class="t-small muted pretty">O domínio precisa estar na conta do Cloudflare da plataforma (servidores DNS trocados no registro.br). O passo a passo está em docs/dominios.md.</p>`,
        actions: [{ label: 'Entendi' }],
      }).el.addEventListener('close', again);
    }
    if (what === 'revoke') {
      if (!await ask('Cancelar este convite?', 'O link deixa de abrir na hora.', 'Cancelar o convite', true)) return;
      await api(`/api/admin/invites/${id}/revoke`, { method: 'POST' });
      toast('Convite cancelado.');
      again();
    }
  } catch (e) { fail(e); }
}

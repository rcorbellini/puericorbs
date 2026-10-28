// O que se vê antes de entrar: a plataforma (o endereço que não é de nenhum consultório) e o site de cada pediatra,
// aberto pelo domínio dele, com a entrada da equipe e da família.
import { api, html, icon, fail, toast, dialog, ask, initials, dateFull } from './lib.js';

const ACCENT_HEX = { agua: '#08746b', azul: '#1f5fbf', coral: '#b8452a', lavanda: '#5b47c4' };
const ROLE_ORDER = { clinician: 0, receptionist: 1, guardian: 2 };

export async function platform(app) {
  const root = document.getElementById('app');
  let data;
  try { data = await api('/api/platform'); } catch (e) { root.innerHTML = String(html`<div class="platform"><div class="glass error-box"><p>${e.message}</p></div></div>`); return; }
  const me = data.me;
  const local = /localhost$|127\.0\.0\.1/.test(location.hostname);
  root.innerHTML = String(html`
    <div class="platform">
      <header style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:18px">
        <div style="display:flex;flex-direction:column;gap:12px;max-width:720px">
          <div style="display:flex;align-items:center;gap:14px"><span class="logo" style="width:52px;height:52px"></span><h1 class="wordmark" style="font-size:46px">puericorbs</h1></div>
          <p class="t-h2 muted" style="font-weight:500">Cada pediatra tem o próprio domínio, e todos apontam para este servidor: o endereço decide de qual consultório é o site.</p>
        </div>
        ${me ? html`<div class="who glass" style="padding:8px 8px 8px 14px">${me.name}<button class="btn ghost small" type="button" data-act="logout">Sair</button></div>`
          : data.demo ? html`<button class="btn ghost" type="button" data-act="admin">${icon('gear')}Entrar como a administração</button>` : ''}
      </header>
      ${data.demo ? html`<div class="glass card" style="display:flex;gap:12px;align-items:flex-start">${icon('info')}<p class="pretty"><b>Esta é a demonstração.</b> Pelo endereço da plataforma (o do ngrok), escolha abaixo o site de um pediatra: ele abre como se você tivesse digitado o domínio dele. Lá, a tela de entrada mostra quem você pode ser: a pediatra, a recepção ou uma família. Tudo é fictício.</p></div>` : ''}
      <section class="grid-cards">
        ${data.practices.map((p) => html`
          <article class="glass pcard">
            <div style="display:flex;align-items:center;gap:12px">
              <span class="av lg">${initials(p.name)}</span>
              <div class="grow"><h2 class="t-h2">${p.name}</h2><p class="t-small muted">${p.clinic || 'Consultório próprio'} · ${p.registry || ''}</p></div>
              <span class="swatch" style="--sw:${ACCENT_HEX[p.accent] || ACCENT_HEX.agua}" title="Cor do destaque"></span>
            </div>
            <div class="domains">${p.domains.map((d) => html`<span class="pill strong">${icon('globe')}${d}</span>`)}${p.subdomain ? html`<span class="pill">${p.subdomain}</span>` : ''}</div>
            <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
              ${data.demo ? html`<button class="btn" type="button" data-act="open" data-slug="${p.slug}">Abrir o site</button>` : ''}
              ${local && p.subdomain ? html`<a class="linkbtn t-small" href="${location.protocol}//${p.subdomain}${location.port ? ':' + location.port : ''}/">${p.subdomain}</a>` : ''}
            </div>
          </article>`)}
      </section>
      ${me && me.is_platform_admin ? html`<div><button class="btn ghost" type="button" data-act="new">${icon('plus')}Novo consultório</button></div>` : ''}
      ${data.demo ? html`<section class="glass card" style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between">
          <div><h2 class="t-h3">Começar a demonstração de novo</h2><p class="t-small muted">Apaga o que foi feito nos testes e volta ao dia de hoje montado do zero.</p></div>
          <button class="btn danger" type="button" data-act="reset">Reiniciar a demonstração</button></section>` : ''}
      <p class="t-small muted">Para pôr um domínio no ar: o domínio do pediatra aponta (CNAME) para o endereço deste servidor e é cadastrado aqui. O passo a passo está em docs/dominios.md.</p>
    </div>`);
  root.onclick = async (ev) => {
    const b = ev.target.closest('[data-act]');
    if (!b) return;
    const act = b.dataset.act;
    try {
      if (act === 'open') await app.switchSite(b.dataset.slug);
      if (act === 'logout') await app.logout();
      if (act === 'admin') { await api('/api/auth/demo', { method: 'POST', body: { email: 'admin@demo.test' } }); location.reload(); }
      if (act === 'reset' && await ask('Reiniciar a demonstração?', 'Tudo o que foi feito nos testes some, e o dia de hoje volta ao começo.', 'Reiniciar', true)) {
        await api('/api/platform/reset', { method: 'POST' });
        toast('A demonstração voltou ao começo.');
        setTimeout(() => location.reload(), 600);
      }
      if (act === 'new') newPractice();
    } catch (e) { fail(e); }
  };
}

function newPractice() {
  dialog({
    title: 'Novo consultório',
    body: html`
      <div class="rows">
        <label class="row"><span class="lbl">Nome</span><input class="inline" name="name" placeholder="Dra. Fulana de Tal"></label>
        <label class="row"><span class="lbl">Endereço curto</span><input class="inline" name="slug" placeholder="drafulana"></label>
        <label class="row"><span class="lbl">Domínio próprio</span><input class="inline" name="domain" placeholder="drafulana.com.br"></label>
        <label class="row"><span class="lbl">CRM e RQE</span><input class="inline" name="registry" placeholder="CRM-SP 000000 · RQE 00000"></label>
        <label class="row"><span class="lbl">Cor</span><select class="inline" name="accent"><option value="agua">Verde-água</option><option value="azul">Azul</option><option value="coral">Coral</option><option value="lavanda">Lavanda</option></select></label>
      </div>
      <div class="rows">
        <label class="row"><span class="lbl">Nome do pediatra</span><input class="inline" name="clinician_name"></label>
        <label class="row"><span class="lbl">E-mail</span><input class="inline" name="clinician_email" type="email"></label>
        <label class="row"><span class="lbl">Senha</span><input class="inline" name="password" type="password" placeholder="8 ou mais caracteres"></label>
      </div>
      <p class="note">O consultório nasce com o catálogo de serviços, a grade de segunda a sexta e as vagas para a criança doente; tudo se edita depois.</p>`,
    actions: [{ label: 'Criar o consultório', run: async (dlg) => {
      const v = Object.fromEntries([...dlg.querySelectorAll('[name]')].map((i) => [i.name, i.value.trim()]));
      if (!v.domain) delete v.domain;
      await api('/api/platform/practices', { method: 'POST', body: v });
      toast('Consultório criado.');
      setTimeout(() => location.reload(), 500);
    } }],
  });
}

export function unknown() {
  document.getElementById('app').innerHTML = String(html`
    <div class="platform"><div class="glass error-box">
      <span class="logo" style="width:44px;height:44px"></span>
      <h1 class="t-title">Domínio não configurado</h1>
      <p class="muted pretty">Este endereço ainda não está ligado a nenhum consultório. Se ele é seu, peça para cadastrar o domínio na plataforma.</p>
    </div></div>`);
}

export function publicSite(app) {
  const s = app.site;
  const p = s.practice;
  const root = document.getElementById('app');
  const accounts = (s.demo_accounts || []).slice().sort((a, b) => ROLE_ORDER[a.role] - ROLE_ORDER[b.role]);
  const noAccess = app.me && !app.me.role;
  root.innerHTML = String(html`
    <div class="site">
      <header style="display:flex;align-items:center;gap:12px"><span class="logo"></span><span class="t-small muted">${s.domains?.[0] || s.host}</span></header>
      <section class="site-hero">
        <div class="intro">
          <span class="t-cap">${p.title}${s.clinic ? ` · ${s.clinic}` : ''}</span>
          <h1 class="site-name">${p.name}</h1>
          ${p.registry ? html`<p class="muted">${p.registry}</p>` : ''}
          ${p.bio ? html`<p class="t-h2 pretty" style="font-weight:500;max-width:46ch">${p.bio}</p>` : ''}
          ${p.address ? html`<p class="muted" style="display:flex;gap:8px;align-items:center">${icon('pin')}${p.address}</p>` : ''}
        </div>
        <div class="enter glass card" style="display:flex;flex-direction:column;gap:14px">
          <h2 class="t-h2">Entrar</h2>
          ${noAccess ? html`<p class="pill late" style="height:auto;padding:8px 12px;white-space:normal">Sua conta não tem acesso a este consultório.</p>` : ''}
          <form data-login style="display:flex;flex-direction:column;gap:10px">
            <label class="field">${icon('message')}<input name="email" type="email" autocomplete="username" placeholder="E-mail" aria-label="E-mail" required></label>
            <label class="field">${icon('eye')}<input name="password" type="password" autocomplete="current-password" placeholder="Senha" aria-label="Senha" required></label>
            <button class="btn big wide" type="submit">Entrar</button>
          </form>
          ${s.demo && accounts.length ? html`
            <div style="display:flex;flex-direction:column;gap:8px">
              <span class="t-cap">Na demonstração, entre como</span>
              <div class="demo-list">
                ${accounts.map((a) => html`<button class="demo-who" type="button" data-email="${a.email}">
                  <span class="av sm">${initials(a.name)}</span><span class="grow"><b>${a.name}</b><span class="t-small muted">${a.label}</span></span>${icon('chevR', 'muted')}</button>`)}
              </div>
              <p class="t-small muted">A senha de todas as contas da demonstração é <b>demo1234</b>.</p>
            </div>` : ''}
        </div>
      </section>
      ${s.services?.length ? html`
        <section style="display:flex;flex-direction:column;gap:14px">
          <h2 class="t-h2">O que o consultório oferece</h2>
          <div class="grid-cards">
            ${s.services.map((sv) => html`<article class="glass svc-card"><span class="t-cap">${sv.kind_label}</span><h3 class="t-h3">${sv.name}</h3>
              ${sv.text ? html`<p class="t-small muted pretty">${sv.text}</p>` : ''}<p class="t-small">${sv.duration_min} min</p></article>`)}
          </div>
        </section>` : ''}
      <footer class="t-small muted" style="display:flex;align-items:center;gap:8px"><span class="logo" style="width:20px;height:20px"></span>Feito com Puericorbs</footer>
    </div>`);
  root.querySelector('[data-login]').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    try {
      await api('/api/auth/login', { method: 'POST', body: { email: fd.get('email'), password: fd.get('password') } });
      location.reload();
    } catch (e) { fail(e); }
  });
  root.querySelectorAll('[data-email]').forEach((b) => b.addEventListener('click', async () => {
    try {
      await api('/api/auth/demo', { method: 'POST', body: { email: b.dataset.email } });
      location.hash = '';
      location.reload();
    } catch (e) { fail(e); }
  }));
}

// O convite: o link de primeiro acesso, aberto no domínio do consultório. A pessoa cria a conta com o e-mail e a senha
// dela; a pediatra diz também como o consultório aparece no site.
export async function invite(app) {
  const s = app.site;
  const root = document.getElementById('app');
  const token = decodeURIComponent(location.hash.replace(/^#\/convite\//, ''));
  let inv;
  try {
    inv = await api(`/api/invite/${encodeURIComponent(token)}`);
  } catch (e) {
    root.innerHTML = String(html`
      <div class="platform"><div class="glass error-box">
        <span class="logo" style="width:44px;height:44px"></span>
        <h1 class="t-title">Este convite não abre</h1>
        <p class="muted pretty">${e.message}</p>
        <button class="btn ghost" type="button" data-act="home">Ir para a entrada</button>
      </div></div>`);
    root.querySelector('[data-act="home"]').addEventListener('click', () => { location.hash = ''; location.reload(); });
    return;
  }
  const p = inv.practice;
  const doc = inv.role === 'clinician';
  const domain = s.domains?.[0] || s.host;
  root.innerHTML = String(html`
    <div class="site">
      <header style="display:flex;align-items:center;gap:12px"><span class="logo"></span><span class="t-small muted">${domain}</span></header>
      <section class="site-hero">
        <div class="intro">
          <span class="t-cap">Convite · ${inv.role_label}</span>
          <h1 class="site-name">Crie o seu acesso</h1>
          ${doc
            ? html`<p class="t-h2 pretty" style="font-weight:500;max-width:46ch">Este é o site do seu consultório, em <b>${domain}</b>. Crie a sua senha e diga como o consultório aparece para as famílias.</p>
                <p class="muted pretty" style="max-width:52ch">O resto (o texto de apresentação, o endereço, o telefone, a cor, os serviços e a grade) se ajusta depois, lá dentro, em Consultório e Serviços.</p>`
            : html`<p class="t-h2 pretty" style="font-weight:500;max-width:46ch">Você vai cuidar da agenda, do cadastro e do dinheiro de <b>${p.name}</b>. Crie a sua senha para entrar.</p>`}
        </div>
        <div class="enter glass card" style="display:flex;flex-direction:column;gap:14px">
          <h2 class="t-h2">Seus dados</h2>
          <form data-invite style="display:flex;flex-direction:column;gap:12px">
            <div class="rows">
              <label class="row"><span class="lbl">Seu nome</span><input class="inline" name="name" autocomplete="name" placeholder="Nome e sobrenome" required></label>
              ${doc ? html`
                <label class="row"><span class="lbl">Nome no site<span class="sub">o título do site</span></span><input class="inline" name="practice_name" value="${p.name}" required></label>
                <label class="row"><span class="lbl">CRM e RQE</span><input class="inline" name="registry" value="${p.registry || ''}" placeholder="CRM-UF 000000"></label>` : ''}
            </div>
            <div class="rows">
              <label class="row"><span class="lbl">E-mail<span class="sub">para entrar</span></span><input class="inline" name="email" type="email" autocomplete="username" placeholder="seu@email.com" required></label>
              <label class="row"><span class="lbl">Senha<span class="sub">8 ou mais caracteres</span></span><input class="inline" name="password" type="password" autocomplete="new-password" minlength="8" placeholder="crie uma senha" required></label>
            </div>
            <button class="btn big wide" type="submit">Criar meu acesso</button>
            <p class="t-small muted">O link vale uma vez só, até ${dateFull(inv.expires_at.slice(0, 10))}.</p>
          </form>
        </div>
      </section>
    </div>`);
  root.querySelector('[data-invite]').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const body = Object.fromEntries(new FormData(ev.target));
    const button = ev.target.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await api(`/api/invite/${encodeURIComponent(token)}`, { method: 'POST', body });
      location.hash = '';
      location.reload();
    } catch (e) {
      button.disabled = false;
      fail(e);
    }
  });
}

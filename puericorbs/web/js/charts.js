// Os gráficos: a curva de crescimento (a criança sobre as faixas da OMS) e a receita por mês (barras empilhadas).
// Regras da skill de visualização: linha de 2 px, pontos de 8 px com anel da cor do fundo, grade fina e contínua, texto
// nunca na cor da série, tooltip que só complementa (a tabela está a um clique) e legenda quando há duas séries.
import { html, raw, esc, money, moneyShort, dateFull } from './lib.js';

const f = (n) => n.toFixed(1);

function niceStep(range, target = 5) {
  const rough = range / target;
  const pow = 10 ** Math.floor(Math.log10(rough));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * pow >= rough) return m * pow;
  return 10 * pow;
}

function smooth(p) {
  let d = `M${f(p[0][0])},${f(p[0][1])}`;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] || p[i], b = p[i], c = p[i + 1], e = p[i + 2] || c;
    d += ` C${f(b[0] + (c[0] - a[0]) / 6)},${f(b[1] + (c[1] - a[1]) / 6)} ${f(c[0] - (e[0] - b[0]) / 6)},${f(c[1] - (e[1] - b[1]) / 6)} ${f(c[0])},${f(c[1])}`;
  }
  return d;
}

// chart: o que /api/.../chart devolve (curves {3,15,50,85,97}: [[dia, valor]], points [{day, value, pct, label, date}])
export function growthChart(chart, { name = '', wide = false } = {}) {
  const W = wide ? 640 : 340, H = wide ? 300 : 222, X0 = 34, X1 = W - 34, Y0 = 10, Y1 = H - 30;
  const span = chart.span_days;
  const all = [...chart.curves['3'].map((p) => p[1]), ...chart.curves['97'].map((p) => p[1]), ...chart.points.map((p) => p.value)];
  let lo = Math.min(...all), hi = Math.max(...all);
  const step = niceStep(hi - lo, 5);
  lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
  const sx = (d) => X0 + (d / span) * (X1 - X0);
  const sy = (v) => Y1 - ((v - lo) / (hi - lo)) * (Y1 - Y0);
  const pts = (arr) => arr.map(([d, v]) => [sx(d), sy(v)]);
  const band = (up, dn) => `${smooth(pts(chart.curves[up]))} L${smooth(pts(chart.curves[dn]).reverse()).slice(1)} Z`;
  const yTicks = [];
  for (let v = lo + step; v < hi; v += step) yTicks.push(v);
  const months = span / 30.44;
  const years = months > 30;
  const unitDays = years ? 365.25 : 30.44;
  const total = span / unitDays;
  const every = years ? 1 : total <= 8 ? 1 : total <= 14 ? 2 : total <= 26 ? 3 : 6;
  const xTicks = [];
  for (let t = 0; t <= total + 0.01; t += every) xTicks.push(t);
  const last = (k) => chart.curves[k][chart.curves[k].length - 1];
  const labels = ['97', '85', '50', '15', '3'].map((k) => ({ k, y: sy(last(k)[1]) }));
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 12) labels[i].y = labels[i - 1].y + 12;
  const kid = chart.points.map((p) => [sx(p.day), sy(p.value)]);
  const fmt = (v) => v.toLocaleString('pt-BR', { maximumFractionDigits: chart.unit === 'kg' ? 1 : 0 });
  const aria = chart.points.length
    ? `${chart.label} de ${name} na curva da OMS: ${chart.points.map((p) => `${p.label}, ${fmt(p.value)} ${chart.unit} (${p.pct || ''})`).join('; ')}.`
    : `${chart.label} de ${name}: ainda sem medidas.`;
  return html`
    <div class="chartbox" data-chart data-w="${W}" data-h="${H}">
      <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${aria}">
        <path class="band" d="${band('97', '3')}"></path>
        <path class="band" d="${band('85', '15')}"></path>
        ${yTicks.map((v) => raw(`<line class="grid" x1="${X0}" x2="${X1}" y1="${f(sy(v))}" y2="${f(sy(v))}"></line><text class="ylab" x="${X0 - 6}" y="${f(sy(v) + 4)}">${esc(fmt(v))}</text>`))}
        <line class="axis" x1="${X0}" x2="${X1}" y1="${Y1}" y2="${Y1}"></line>
        ${xTicks.map((t) => raw(`<text class="xlab" x="${f(sx(t * unitDays))}" y="${Y1 + 17}">${t}</text>`))}
        <path class="p50" d="${smooth(pts(chart.curves['50']))}"></path>
        ${labels.map((l) => raw(`<text class="plab" x="${X1 + 5}" y="${f(l.y + 4)}">P${l.k}</text>`))}
        ${kid.length > 1 ? raw(`<path class="kid" d="${kid.map((p, i) => `${i ? 'L' : 'M'}${f(p[0])},${f(p[1])}`).join(' ')}"></path>`) : ''}
        ${kid.map((p, i) => raw(`<circle class="hit" tabindex="0" data-i="${i}" cx="${f(p[0])}" cy="${f(p[1])}" r="13"></circle><circle class="pt${i === kid.length - 1 ? ' on' : ''}" cx="${f(p[0])}" cy="${f(p[1])}" r="${i === kid.length - 1 ? 5.5 : 4.5}"></circle>`))}
      </svg>
      <div class="tip" hidden></div>
    </div>
    <p class="t-small muted" style="margin-top:4px">Curvas da OMS para ${chart.sex === 'F' ? 'meninas' : 'meninos'} · idade em ${years ? 'anos' : 'meses'}, ${chart.label.toLowerCase()} em ${chart.unit}${chart.corrected ? ' · idade corrigida (prematuro)' : ''}</p>`;
}

export function bindGrowth(root, chart) {
  const box = root.querySelector('[data-chart]');
  if (!box) return;
  const tip = box.querySelector('.tip');
  const W = Number(box.dataset.w), H = Number(box.dataset.h);
  const fmt = (v) => v.toLocaleString('pt-BR', { maximumFractionDigits: chart.unit === 'kg' ? 2 : 1 });
  const show = (i) => {
    const p = chart.points[i];
    if (!p) return;
    const c = box.querySelectorAll('.hit')[i];
    const x = Number(c.getAttribute('cx')) / W * 100, y = Number(c.getAttribute('cy')) / H * 100;
    tip.innerHTML = String(html`<b>${fmt(p.value)} ${chart.unit} · ${p.pct || ''}</b><span class="muted">${p.label} · ${dateFull(p.date)}</span>`);
    tip.hidden = false;
    tip.style.left = `${Math.max(18, Math.min(82, x))}%`;
    tip.style.top = `${y}%`;
    tip.style.transform = 'translate(-50%, calc(-100% - 14px))';
  };
  box.addEventListener('mouseover', (e) => { const h = e.target.closest('.hit'); if (h) show(Number(h.dataset.i)); });
  box.addEventListener('focusin', (e) => { const h = e.target.closest('.hit'); if (h) show(Number(h.dataset.i)); });
  box.addEventListener('click', (e) => { const h = e.target.closest('.hit'); if (h) show(Number(h.dataset.i)); });
  box.addEventListener('mouseleave', () => { tip.hidden = true; });
  if (chart.points.length) show(chart.points.length - 1);
}

export function growthTable(chart) {
  const fmt = (v) => v.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
  return html`<div class="dtable" style="--cols:4" role="table" aria-label="${chart.label}">
    <div class="dtr dth" role="row"><span role="columnheader">Data</span><span role="columnheader">Idade</span><span role="columnheader" class="r">${chart.label}</span><span role="columnheader" class="r">Percentil</span></div>
    ${chart.points.slice().reverse().map((p) => html`<div class="dtr" role="row"><span role="cell">${dateFull(p.date)}</span><span role="cell">${p.label}</span><span role="cell" class="r">${fmt(p.value)} ${chart.unit}</span><span role="cell" class="r">${p.pct || '—'}</span></div>`)}
  </div>`;
}

// series: [{label, full, plans, visits}] em centavos
export function revenueBars(series) {
  const max = Math.max(1, ...series.map((m) => m.plans + m.visits));
  const step = niceStep(max / 100, 4) * 100;
  const top = Math.ceil(max / step) * step;
  const Hh = 200;
  const ticks = [];
  for (let v = step; v <= top; v += step) ticks.push(v);
  return html`
    <div class="bars" data-bars>
      <div class="yax" aria-hidden="true">
        <span style="bottom:0px">0</span>
        ${ticks.map((v) => raw(`<span style="bottom:${f(v / top * Hh)}px">${esc(moneyShort(v).replace('R$ ', ''))}</span>`))}
      </div>
      <div class="plot">
        ${ticks.map((v) => raw(`<span class="gl" style="bottom:${f(26 + v / top * Hh)}px" aria-hidden="true"></span>`))}
        <span class="gl base" style="bottom:26px" aria-hidden="true"></span>
        <div class="colsx">
          ${series.map((m, i) => {
            const h1 = m.plans / top * Hh, h2 = m.visits / top * Hh;
            const total = m.plans + m.visits;
            return html`<button class="bcol" type="button" data-i="${i}" aria-label="${m.full}: planos ${money(m.plans)}, avulsas ${money(m.visits)}, total ${money(total)}">
              ${i === series.length - 1 ? html`<span class="capl">${moneyShort(total)}</span>` : ''}
              <span class="stack" style="height:${f(h1 + h2 + (h1 && h2 ? 2 : 0))}px">
                ${h2 ? raw(`<span class="s2" style="height:${f(h2)}px"></span>`) : ''}
                ${h1 ? raw(`<span class="s1" style="height:${f(h1)}px"></span>`) : ''}
              </span>
              <span class="bx">${m.label}</span>
              <span class="tip ${i < series.length - 2 ? 'r' : 'l'}" hidden>
                <b>${m.full}</b>
                <span class="tr"><i style="background:var(--s1)"></i><span>Planos</span><b>${money(m.plans)}</b></span>
                <span class="tr"><i style="background:var(--s2)"></i><span>Avulsas</span><b>${money(m.visits)}</b></span>
                <span class="tr"><i></i><span>Total</span><b>${money(total)}</b></span>
              </span>
            </button>`;
          })}
        </div>
      </div>
    </div>`;
}

export function bindBars(root) {
  const box = root.querySelector('[data-bars]');
  if (!box) return;
  const cols = [...box.querySelectorAll('.bcol')];
  const show = (el) => { cols.forEach((c) => { c.classList.toggle('on', c === el); c.querySelector('.tip').hidden = c !== el; const cap = c.querySelector('.capl'); if (cap) cap.style.visibility = el ? 'hidden' : ''; }); };
  box.addEventListener('mouseover', (e) => { const c = e.target.closest('.bcol'); if (c) show(c); });
  box.addEventListener('focusin', (e) => { const c = e.target.closest('.bcol'); if (c) show(c); });
  box.addEventListener('click', (e) => { const c = e.target.closest('.bcol'); if (c) show(c); });
  box.addEventListener('mouseleave', () => show(null));
}

export function revenueTable(series) {
  return html`<div class="dtable" style="--cols:4" role="table" aria-label="Receita por mês">
    <div class="dtr dth" role="row"><span role="columnheader">Mês</span><span role="columnheader" class="r">Planos</span><span role="columnheader" class="r">Avulsas</span><span role="columnheader" class="r">Total</span></div>
    ${series.map((m) => html`<div class="dtr" role="row"><span role="cell">${m.full}</span><span role="cell" class="r">${money(m.plans)}</span><span role="cell" class="r">${money(m.visits)}</span><span role="cell" class="r">${money(m.plans + m.visits)}</span></div>`)}
  </div>`;
}

// ---- CPF ou CNPJ: quanto a empresa deixa a mais (acima de zero) ou a menos (abaixo) por mês, pelo faturamento -------
// Uma série só (sem legenda: o título a nomeia); a linha do zero é o ponto em que os dois caminhos empatam, e o
// cruzamento é marcado e escrito. A tabela está a um clique.
const kShort = (cents) => {
  const v = Math.abs(cents) / 100;
  const s = v >= 1000 ? `${(v / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil` : v.toLocaleString('pt-BR', { maximumFractionDigits: 0 });
  return `${cents < 0 ? '−' : cents > 0 ? '+' : ''}${s}`;
};
const revShort = (cents) => moneyShort(cents).replace('R$ ', '');

function crossings(curve) {
  const out = [];
  for (let i = 1; i < curve.length; i++) {
    const a = curve[i - 1], b = curve[i];
    if ((a.gain_cents > 0) !== (b.gain_cents > 0)) {
      const t = a.gain_cents / (a.gain_cents - b.gain_cents);
      out.push({ revenue_cents: a.revenue_cents + t * (b.revenue_cents - a.revenue_cents), up: b.gain_cents > 0 });
    }
  }
  return out;
}

export function gainChart(curve, current, even = null) {
  // no celular, uma geometria própria: o SVG não encolhe o texto abaixo de 11 px
  const narrow = typeof matchMedia === 'function' && matchMedia('(max-width: 640px)').matches;
  const W = narrow ? 360 : 640, H = narrow ? 250 : 260, X0 = narrow ? 48 : 58, X1 = W - 14, Y0 = 26, Y1 = H - 30;
  const xs = curve.map((p) => p.revenue_cents), ys = curve.map((p) => p.gain_cents);
  let lo = Math.min(0, ...ys), hi = Math.max(0, ...ys);
  const step = niceStep((hi - lo) || 100000, 4);
  lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
  if (hi === lo) hi = lo + step;
  const sx = (v) => X0 + (v - xs[0]) / (xs[xs.length - 1] - xs[0]) * (X1 - X0);
  const sy = (v) => Y1 - (v - lo) / (hi - lo) * (Y1 - Y0);
  const yTicks = [];
  for (let v = lo; v <= hi + 1; v += step) yTicks.push(v);
  const xStep = niceStep(xs[xs.length - 1] - xs[0], narrow ? 3 : 5);
  const xTicks = [];
  for (let v = Math.ceil(xs[0] / xStep) * xStep; v <= xs[xs.length - 1]; v += xStep) xTicks.push(v);
  const line = curve.map((p, i) => `${i ? 'L' : 'M'}${f(sx(p.revenue_cents))},${f(sy(p.gain_cents))}`).join(' ');
  const cross = crossings(curve);
  // o ponto de virada escrito no texto (a conta de R$ 250 em R$ 250) é o que o gráfico marca: um número só na tela
  const firstUp = cross.find((c) => c.up);
  if (firstUp && even) firstUp.revenue_cents = even;
  const cur = current && current.revenue_cents >= xs[0] && current.revenue_cents <= xs[xs.length - 1] ? current : null;
  const aria = `Quanto a empresa deixa a mais ou a menos por mês, do faturamento de ${moneyShort(xs[0])} a ${moneyShort(xs[xs.length - 1])}. `
    + (cross.length ? cross.map((c) => `${c.up ? 'A empresa passa a deixar mais' : 'A pessoa física volta a deixar mais'} a partir de ${moneyShort(c.revenue_cents)} por mês.`).join(' ') : 'Os dois caminhos não se cruzam neste trecho.')
    + (cur ? ` Hoje, com ${moneyShort(cur.revenue_cents)}, a diferença é de ${kShort(cur.gain_cents)} por mês.` : '');
  return html`
    <div class="chartbox" data-gain data-w="${W}" data-h="${H}" data-x0="${X0}" data-x1="${X1}">
      <svg class="chart gain" viewBox="0 0 ${W} ${H}" role="img" aria-label="${aria}">
        ${yTicks.map((v) => raw(`<line class="${v === 0 ? 'axis' : 'grid'}" x1="${X0}" x2="${X1}" y1="${f(sy(v))}" y2="${f(sy(v))}"></line><text class="ylab" x="${X0 - 6}" y="${f(sy(v) + 4)}">${esc(kShort(v))}</text>`))}
        ${xTicks.map((v) => raw(`<text class="xlab" x="${f(sx(v))}" y="${Y1 + 18}">${esc(revShort(v))}</text>`))}
        ${hi > 0 ? raw(`<text class="zone" x="${X1 - 4}" y="${f(Math.max(Y0 + 12, sy(0) - 8))}">↑ a empresa deixa mais</text>`) : ''}
        ${lo < 0 ? raw(`<text class="zone" x="${X1 - 4}" y="${f(Math.min(Y1 - 4, sy(0) + 16))}">↓ a pessoa física deixa mais</text>`) : ''}
        ${cross.map((c) => raw(`<line class="even" x1="${f(sx(c.revenue_cents))}" x2="${f(sx(c.revenue_cents))}" y1="${Y0 - 6}" y2="${Y1}"></line><text class="evlab" x="${f(sx(c.revenue_cents))}" y="${Y0 - 10}">${esc(moneyShort(c.revenue_cents))}</text>`))}
        <path class="gl" d="${line}"></path>
        ${cur ? raw(`<circle class="pt on" cx="${f(sx(cur.revenue_cents))}" cy="${f(sy(cur.gain_cents))}" r="5.5"></circle><text class="you" x="${f(sx(cur.revenue_cents))}" y="${f(sy(cur.gain_cents) + (cur.gain_cents >= 0 ? -12 : 20))}">você hoje</text>`) : ''}
        <line class="xh" x1="0" x2="0" y1="${Y0}" y2="${Y1}" visibility="hidden"></line>
        <circle class="pt hov" r="4.5" cx="0" cy="0" visibility="hidden"></circle>
        <rect class="hitarea" x="${X0}" y="${Y0}" width="${X1 - X0}" height="${Y1 - Y0}" tabindex="0" aria-label="Percorrer a curva com as setas"></rect>
      </svg>
      <div class="tip" hidden></div>
    </div>
    <p class="t-small muted" style="margin-top:4px">Faturamento por mês, em reais · a diferença por mês entre o que fica com você na empresa e na pessoa física, com a mesma parte do faturamento em despesas</p>`;
}

export function bindGain(root, curve) {
  const box = root.querySelector('[data-gain]');
  if (!box) return;
  const svg = box.querySelector('svg'), tip = box.querySelector('.tip');
  const xh = box.querySelector('.xh'), dot = box.querySelector('.hov');
  const W = Number(box.dataset.w), H = Number(box.dataset.h), X0 = Number(box.dataset.x0), X1 = Number(box.dataset.x1);
  const pts = [...box.querySelector('.gl').getAttribute('d').matchAll(/[ML]([\d.-]+),([\d.-]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
  let at = -1;
  const show = (i) => {
    at = Math.max(0, Math.min(curve.length - 1, i));
    const p = curve[at], [x, y] = pts[at];
    xh.setAttribute('x1', x); xh.setAttribute('x2', x); xh.setAttribute('visibility', 'visible');
    dot.setAttribute('cx', x); dot.setAttribute('cy', y); dot.setAttribute('visibility', 'visible');
    const g = p.gain_cents;
    tip.innerHTML = String(html`<b>${money(p.revenue_cents)} por mês</b>
      <span class="tr"><i></i><span>Pessoa física</span><b>${money(p.pf_cents)}</b></span>
      <span class="tr"><i></i><span>Empresa</span><b>${money(p.pj_cents)}</b></span>
      <span class="muted">${g > 0 ? `a empresa deixa ${money(g)} a mais` : g < 0 ? `a pessoa física deixa ${money(-g)} a mais` : 'empatam'}</span>`);
    tip.hidden = false;
    tip.style.left = `${Math.max(22, Math.min(78, x / W * 100))}%`;
    tip.style.top = `${y / H * 100}%`;
    tip.style.transform = 'translate(-50%, calc(-100% - 14px))';
  };
  const hide = () => { xh.setAttribute('visibility', 'hidden'); dot.setAttribute('visibility', 'hidden'); tip.hidden = true; at = -1; };
  const nearest = (ev) => {
    const r = svg.getBoundingClientRect();
    const x = (ev.clientX - r.left) / r.width * W;
    return Math.round((x - X0) / (X1 - X0) * (curve.length - 1));
  };
  svg.addEventListener('pointermove', (ev) => show(nearest(ev)));
  svg.addEventListener('pointerdown', (ev) => show(nearest(ev)));
  box.addEventListener('mouseleave', hide);
  const hit = box.querySelector('.hitarea');
  hit.addEventListener('blur', hide);
  hit.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') {
      ev.preventDefault();
      show((at < 0 ? 0 : at) + (ev.key === 'ArrowRight' ? 1 : -1));
    }
  });
}

export function gainTable(curve) {
  const rows = curve.filter((_, i) => i % 4 === 0 || i === curve.length - 1);
  return html`<div class="dtable" style="--cols:4" role="table" aria-label="Pessoa física e empresa, pelo faturamento">
    <div class="dtr dth" role="row"><span role="columnheader">Recebe por mês</span><span role="columnheader" class="r">Pessoa física</span><span role="columnheader" class="r">Empresa</span><span role="columnheader" class="r">Diferença</span></div>
    ${rows.map((p) => html`<div class="dtr" role="row"><span role="cell">${money(p.revenue_cents)}</span><span role="cell" class="r">${money(p.pf_cents)}</span><span role="cell" class="r">${money(p.pj_cents)}</span><span role="cell" class="r">${kShort(p.gain_cents)}</span></div>`)}
  </div>`;
}

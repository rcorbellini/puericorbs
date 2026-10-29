// Horários: os dias e os períodos em que a pediatra atende (só ela muda) e a agenda fechada (férias, congresso, folga),
// que a pediatra e a recepção fecham e reabrem. Nada que já estava marcado é desmarcado sozinho: depois da mudança, a
// tela mostra o que ficou para remarcar, com o aviso pronto para cada família.
import { api, html, raw, icon, toast, dialog, ask, actions, dateBR, weekday } from './lib.js';
import { rescheduleDialog } from './staff-common.js';
import { closureRange } from './staff-day.js';
import { refresh } from './staff.js';

const DAYS = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
const DEFAULT = [['08:00', '12:00'], ['14:00', '18:00']];
const toMin = (t) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
// "sexta, 13/11" ou "13/11 a 20/11"
const closureLong = (c) => (c.start === c.end ? `${weekday(c.start)}, ${dateBR(c.start)}` : `${dateBR(c.start)} a ${dateBR(c.end)}`);

// a hora digitada: "8" → "08:00", "1720" → "17:20"; sempre 24 h, em qualquer celular (o campo de hora do navegador
// segue o idioma do aparelho e às vezes vira AM/PM). Inválida, devolve ''.
function clock(text) {
  const d = String(text || '').replace(/\D/g, '').slice(0, 4);
  if (!d) return '';
  const [h, m] = d.length <= 2 ? [d, '00'] : [d.slice(0, d.length - 2), d.slice(-2)];
  return Number(h) <= 23 && Number(m) <= 59 ? `${h.padStart(2, '0')}:${m}` : '';
}

function weekHtml(week, edit) {
  return html`${DAYS.map((name, wd) => {
    const ps = week[wd];
    return html`<div class="wday">
      <div class="wday-name"><b>${name}</b>${edit ? html`<input class="switch" type="checkbox" data-day="${wd}" aria-label="${name}: atende" ${ps.length ? raw('checked') : ''}>` : ''}</div>
      <div class="wday-periods">
        ${ps.length ? ps.map(([s, e], i) => (edit
          ? html`<div class="period"><label class="field tfield"><input inputmode="numeric" maxlength="5" placeholder="08:00" value="${s}" data-t="${wd}.${i}.0" aria-label="${name}, período ${i + 1}: começo"></label>
              <span class="muted">às</span><label class="field tfield"><input inputmode="numeric" maxlength="5" placeholder="12:00" value="${e}" data-t="${wd}.${i}.1" aria-label="${name}, período ${i + 1}: fim"></label>
              <button class="iconbtn small" type="button" data-act="del" data-wd="${wd}" data-i="${i}" aria-label="Tirar o período ${s}–${e}">${icon('x')}</button></div>`
          : (i ? '' : html`<span>${ps.map(([a, b]) => `${a} às ${b}`).join(' · ')}</span>`))) : html`<span class="muted">Não atende</span>`}
        ${edit && ps.length && ps.length < 6 ? html`<button class="linkbtn t-small" type="button" data-act="add" data-wd="${wd}">+ Outro período</button>` : ''}
      </div>
    </div>`;
  })}`;
}

export async function hours(view, params, app) {
  const r = await api('/api/staff/schedule');
  const edit = r.can_edit_hours;
  // o rascunho da semana: por dia, os períodos [começo, fim]
  const week = DAYS.map((_, wd) => r.periods.filter((p) => p.weekday === wd).map((p) => [p.start, p.end]));
  view.innerHTML = String(html`
    <div class="topbar">
      <div class="titles"><h1 class="t-title">Horários</h1><p class="t-small muted">${edit ? 'Quando você atende e os dias em que a agenda fica fechada.' : `Quando ${r.practice.name} atende e os dias em que a agenda fica fechada.`}</p></div>
      <a class="btn ghost" href="#/agenda">${icon('calendar')}Ver a agenda</a>
    </div>
    <div class="cols">
      <section class="glass card colmain" style="display:flex;flex-direction:column;gap:12px">
        <div class="phead"><h2 class="t-h2">Dias e horários</h2><span class="t-small muted">${edit ? 'a família só marca dentro deles' : 'só a pediatra muda'}</span></div>
        <div data-week></div>
        ${edit ? html`<div class="rows"><label class="row"><span class="lbl">Vaga para a criança doente<span class="sub">O fim de cada período (${r.sick_duration} min) fica guardado e só abre no próprio dia.</span></span><input class="switch" type="checkbox" data-sick ${r.sick_slots ? raw('checked') : ''}></label></div>
          <div style="display:flex;justify-content:flex-end"><button class="btn big" type="button" data-act="save">Salvar os horários</button></div>`
          : html`<p class="t-small muted">${r.reserved.length ? `Vaga para a criança doente: o fim de cada período (${r.sick_duration} min), que só abre no próprio dia.` : 'Sem vaga guardada para a criança doente.'}</p>`}
      </section>
      <section class="glass card colside" style="display:flex;flex-direction:column;gap:10px">
        <div class="phead center"><h2 class="t-h2">Agenda fechada</h2><button class="btn ghost small" type="button" data-act="close">${icon('plus')}Fechar dias</button></div>
        <p class="t-small muted pretty">Férias, congresso, um dia de folga: ninguém marca nesses dias, nem a família pelo app.</p>
        <div>${r.closures.length ? r.closures.map((c, i) => html`<div class="li" style="flex-wrap:wrap"><span class="tick">${icon('calendar')}</span>
            <div class="grow" style="min-width:140px"><b style="display:block">${closureLong(c)}</b>
              <span class="t-small muted">${[c.reason, c.by && `por ${c.by}`].filter(Boolean).join(' · ') || 'sem motivo'}</span>
              ${c.appointments.length ? html`<button class="linkbtn t-small" type="button" data-act="warn" data-i="${i}" style="display:block;margin-top:4px">${plural(c.appointments.length, 'consulta marcada', 'consultas marcadas')}: avisar</button>` : ''}</div>
            <button class="linkbtn t-small" type="button" data-act="reopen" data-i="${i}">Reabrir</button></div>`)
          : html`<p class="empty">Nenhum dia fechado daqui para a frente.</p>`}</div>
      </section>
    </div>`);
  const box = view.querySelector('[data-week]');
  const draw = () => { box.innerHTML = String(weekHtml(week, edit)); };
  draw();
  if (edit) {
    box.addEventListener('change', (ev) => {
      const sw = ev.target.closest('[data-day]');
      if (!sw) return;
      const wd = Number(sw.dataset.day);
      // ao ligar um dia, ele começa igual ao dia ligado mais perto (quem atende seg, ter e qua das 8 às 16 só liga)
      const near = [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6].map((k) => week[wd - k]).find((ps) => ps && ps.length);
      week[wd] = sw.checked ? (near || DEFAULT).map((p) => [...p]) : [];
      draw();
    });
    // enquanto digita, só os dois-pontos no lugar; ao sair do campo, a hora inteira (ou o aviso de que não vale)
    box.addEventListener('input', (ev) => {
      const t = ev.target.closest('[data-t]');
      if (!t) return;
      const d = t.value.replace(/\D/g, '').slice(0, 4);
      t.value = d.length > 2 ? `${d.slice(0, 2)}:${d.slice(2)}` : d;
      const [wd, i, k] = t.dataset.t.split('.').map(Number);
      week[wd][i][k] = clock(t.value) || t.value;
    });
    box.addEventListener('focusout', (ev) => {
      const t = ev.target.closest('[data-t]');
      if (!t) return;
      const v = clock(t.value);
      if (v) t.value = v;
      t.closest('.field').classList.toggle('bad', !v);
    });
  }
  actions(view, {
    add: (el) => {
      const ps = week[Number(el.dataset.wd)];
      const start = Math.min(toMin(clock(ps[ps.length - 1][1]) || '12:00') + 60, 22 * 60);
      ps.push([hhmm(start), hhmm(Math.min(start + 4 * 60, 23 * 60 + 55))]);
      draw();
    },
    del: (el) => { week[Number(el.dataset.wd)].splice(Number(el.dataset.i), 1); draw(); },
    save: async () => {
      const periods = week.flatMap((ps, wd) => ps.map(([start, end]) => ({ weekday: wd, start: clock(start), end: clock(end) })));
      const typo = periods.find((p) => !p.start || !p.end);
      if (typo) throw new Error(`${DAYS[typo.weekday]}: escreva a hora como 08:00.`);
      const bad = periods.find((p) => toMin(p.end) <= toMin(p.start));
      if (bad) throw new Error(`${DAYS[bad.weekday]}: o fim (${bad.end}) precisa vir depois do começo (${bad.start}).`);
      if (!periods.length && !await ask('Ficar sem nenhum horário?', 'Ninguém consegue marcar consulta, nem a recepção (só encaixe).', 'Salvar assim')) return;
      const x = await api('/api/staff/schedule', { method: 'PUT', body: { periods, sick_slots: view.querySelector('[data-sick]').checked } });
      if (!x.outside.length) { toast('Horários salvos. A agenda e o app da família já seguem os novos.'); refresh(); return; }
      rescheduleDialog(app, 'Consultas fora do horário novo',
        `Os horários foram salvos. ${plural(x.outside.length, 'consulta já marcada ficou', 'consultas já marcadas ficaram')} fora deles: avise a família para remarcar.`,
        x.outside, refresh);
    },
    close: () => closeDays(app, r),
    warn: (el) => {
      const c = r.closures[Number(el.dataset.i)];
      rescheduleDialog(app, 'Avise as famílias', `A agenda está fechada ${closureRange(c)}. Estas consultas estavam marcadas nesses dias.`, c.appointments, refresh);
    },
    reopen: async (el) => {
      const c = r.closures[Number(el.dataset.i)];
      if (!await ask(`Reabrir a agenda ${closureRange(c)}?`, 'Os horários voltam para a recepção e para o app da família.', 'Reabrir')) return;
      await api(`/api/staff/closures/${c.id}`, { method: 'DELETE' });
      toast('Agenda reaberta.'); refresh();
    },
  });
}

function closeDays(app, r) {
  dialog({
    title: 'Fechar a agenda',
    body: html`<div class="rows">
        <label class="row"><span class="lbl">De</span><input class="inline" type="date" data-from value="${r.today}" min="${r.today}"></label>
        <label class="row"><span class="lbl">Até</span><input class="inline" type="date" data-to value="${r.today}" min="${r.today}"></label>
        <label class="row"><span class="lbl">Motivo<span class="sub">só a equipe vê</span></span><input class="inline" data-reason maxlength="80" placeholder="Férias, congresso…"></label>
      </div>
      <p class="note" style="padding:0">Quem já estava marcado nesses dias continua marcado: em seguida aparece quem é, com o aviso pronto para cada família.</p>`,
    onMount: (dlg) => {
      const from = dlg.querySelector('[data-from]');
      const to = dlg.querySelector('[data-to]');
      from.addEventListener('change', () => { to.min = from.value; if (to.value < from.value) to.value = from.value; });
    },
    actions: [{ label: 'Cancelar', kind: 'ghost' }, { label: 'Fechar a agenda', run: async (dlg) => {
      const body = { start: dlg.querySelector('[data-from]').value, end: dlg.querySelector('[data-to]').value || null,
        reason: dlg.querySelector('[data-reason]').value.trim() || null };
      if (!body.start) throw new Error('Escolha o primeiro dia.');
      const x = await api('/api/staff/closures', { method: 'POST', body });
      const range = closureRange({ start: body.start, end: body.end || body.start });
      if (!x.affected.length) { toast(`Agenda fechada ${range}.`); refresh(); return; }
      rescheduleDialog(app, 'Avise as famílias',
        `A agenda ficou fechada ${range}. ${plural(x.affected.length, 'consulta já estava marcada', 'consultas já estavam marcadas')} nesses dias.`,
        x.affected, refresh);
    } }],
  });
}

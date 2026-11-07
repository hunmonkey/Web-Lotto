/* 메인 화면. 번호판 칠하기 · 선 그리기 · 만들기 · 즐겨찾기 · 히스토리.
   상태는 이 안에 두고(state), 바뀔 때마다 render() 가 화면을 다시 그린다. 서버는 JSON 길(/api/...)만 부른다. */
(() => {
  'use strict';

  const LETTERS = ['A', 'B', 'C', 'D', 'E'];
  const NS = 'http://www.w3.org/2000/svg';
  const boot = JSON.parse(document.getElementById('boot').textContent);
  const $ = (sel, root = document) => root.querySelector(sel);
  const range = (a, b) => Array.from({ length: b - a + 1 }, (_, k) => a + k);

  // 게임 하나: nums = 지금 칠해진 번호 · kind = 이름표 · links = 이은 선(null 이면 작은 수부터 자동으로 이음)
  // · wish = 사용자가 직접 칠한 번호('희망번호 포함'은 이것만 두고 나머지를 새로 채운다)
  const blank = () => ({ nums: [], kind: '', links: null, wish: [] });

  const state = {
    mode: 'random', statsKind: 'hot', fillKind: 'random',
    sel: 0,          // 고른 게임(0~4). 용지 두 장이 함께 쓴다
    anchor: null,    // 선을 잇는 중이면 { g, n }: 첫 번호
    games: LETTERS.map(blank),
    favs: boot.favs,
    hist: { open: false, loaded: false, rows: [], total: boot.historyTotal, msg: '', err: false },
    notice: { text: '', err: false },
  };

  // ---------- 도구 ----------
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
    return el;
  }
  const band = (n) => (n <= 10 ? 1 : n <= 20 ? 2 : n <= 30 ? 3 : n <= 40 ? 4 : 5);
  const ball = (n, size) => h('span', { class: `ball ${size} b${band(n)}` }, String(n));

  async function api(path, { method = 'GET', json, form } = {}) {
    const init = { method, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } };
    if (json) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(json); }
    if (form) init.body = form;
    const res = await fetch(path, init);
    let data = null;
    try { data = await res.json(); } catch (_) { /* 본문이 없다 */ }
    if (res.status === 401) { location.href = '/login'; throw new Error('로그인이 필요해요'); }
    if (!res.ok) throw new Error(data && typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했어요');
    return data;
  }

  const setNotice = (text, err = false) => { state.notice = { text, err }; };

  // ---------- 선 ----------
  const effLinks = (g) => {
    if (g.links) return g.links;
    const s = g.nums.slice().sort((a, b) => a - b);
    return s.slice(1).map((n, k) => [s[k], n]);
  };
  const same = (p, a, b) => p[0] === Math.min(a, b) && p[1] === Math.max(a, b);
  const setLinks = (i, links) => { state.anchor = null; state.games[i].links = links; render(); };

  function pointClick(i, n) {
    const a = state.anchor;
    if (!a || a.g !== i) { state.anchor = { g: i, n }; render(); return; }
    if (a.n === n) { state.anchor = null; render(); return; }
    const cur = effLinks(state.games[i]);
    setLinks(i, cur.some((p) => same(p, a.n, n))
      ? cur.filter((p) => !same(p, a.n, n))                       // 이미 이어진 두 번호 → 지움
      : [...cur, [Math.min(a.n, n), Math.max(a.n, n)]]);          // 아니면 이음
  }

  // ---------- 번호판 ----------
  function toggleCell(i, n) {
    let nums = state.games[i].nums;
    if (nums.includes(n)) nums = nums.filter((x) => x !== n);
    else if (nums.length < 6) nums = [...nums, n].sort((a, b) => a - b);
    state.sel = i; state.anchor = null;
    state.games[i] = { nums, kind: nums.length ? '수동' : '', links: null, wish: nums };  // 번호가 바뀌면 선은 자동으로 돌아간다
    render();
  }

  const kindNow = () => (state.mode === 'random' ? 'random' : state.mode === 'stats' ? state.statsKind : state.fillKind);

  async function generate(indices) {
    setNotice('');
    try {
      const res = await api('/api/generate', {
        method: 'POST',
        json: { mode: state.mode, kind: kindNow(), games: indices.map((i) => ({ nums: state.games[i].wish })) },
      });
      res.games.forEach((g, k) => {
        const wish = state.mode === 'wish' ? state.games[indices[k]].wish : [];  // 희망번호가 아닌 방식은 통째로 새로 만든다
        state.games[indices[k]] = { nums: g.nums, kind: g.kind, links: null, wish };
      });
      state.anchor = null;
      if (res.fallback) setNotice('당첨번호가 아직 없어 무작위로 만들었어요. 히스토리에서 엑셀을 올려 주세요.');
    } catch (e) { setNotice(e.message, true); }
    render();
  }

  // ---------- 즐겨찾기 ----------
  async function favCall(path, opts) {
    try { state.favs = (await api(path, opts)).favs; setNotice(''); } catch (e) { setNotice(e.message, true); }
    render();
  }
  const addFav = (i) => favCall('/api/favorites', { method: 'POST', json: { nums: state.games[i].nums } });
  const delFav = (id) => favCall(`/api/favorites/${id}`, { method: 'DELETE' });
  function loadFav(f) {
    state.games[state.sel] = { nums: f.nums.slice(), kind: '수동', links: null, wish: f.nums.slice() };
    state.anchor = null;
    render();
  }

  // ---------- 히스토리 ----------
  async function loadHist() {
    try {
      const r = await api('/api/history?limit=100');
      Object.assign(state.hist, { rows: r.rows, total: r.total, loaded: true });
    } catch (e) { Object.assign(state.hist, { msg: e.message, err: true }); }
    render();
  }
  function toggleHist() {
    state.hist.open = !state.hist.open;
    if (state.hist.open && !state.hist.loaded) loadHist(); else render();
  }
  async function upload(file) {
    Object.assign(state.hist, { msg: '올리는 중…', err: false });
    render();
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await api('/api/history/upload', { method: 'POST', form });
      state.hist.msg = `${r.first}~${r.last}회 읽음 · 새로 ${r.added}회 · 바뀐 ${r.updated}회 · 건너뜀 ${r.skipped}줄 (전체 ${r.total}회)`;
      state.hist.err = false;
    } catch (e) { Object.assign(state.hist, { msg: e.message, err: true }); }
    await loadHist();
  }

  // ---------- 그리기 ----------
  function tabs(el, key) {
    el.replaceChildren(...LETTERS.map((l, i) => h('button', {
      type: 'button', class: 'tab', 'aria-pressed': String(i === state.sel), 'aria-label': `${l} 게임 보기`,
      'data-key': `tab-${key}-${i}`, onclick: () => { state.sel = i; state.anchor = null; render(); },
    }, l)));
  }

  function paperPanel(g, i) {
    const cur = state.sel === i;
    return h('div', { class: 'panel' + (cur ? ' sel cur' : '') },
      h('div', { class: 'panel-head' },
        h('button', {
          type: 'button', class: 'badge', 'aria-pressed': String(cur), 'aria-label': `${LETTERS[i]} 게임 고르기`,
          'data-key': `badge-${i}`, onclick: () => { state.sel = i; state.anchor = null; render(); },
        }, LETTERS[i]),
        h('span', { class: 'tag' }, `${g.kind || '빈칸'} · ${g.nums.length}/6`)),
      h('div', { class: 'grid' }, range(1, 45).map((n) => {
        const on = g.nums.includes(n);
        return h('button', {
          type: 'button', class: 'cell' + (on ? ' on' : ''), 'aria-pressed': String(on),
          'aria-label': `${LETTERS[i]} 게임 ${n}번`, 'data-key': `cell-${i}-${n}`, onclick: () => toggleCell(i, n),
        }, String(n));
      })),
      h('div', { class: 'panel-foot' },
        h('button', { type: 'button', class: 'mini-btn', 'aria-label': `${LETTERS[i]} 게임 다시 만들기`, 'data-key': `regen-${i}`, onclick: () => generate([i]) }, '다시'),
        h('button', {
          type: 'button', class: 'mini-btn fav', disabled: g.nums.length !== 6,
          'aria-label': `${LETTERS[i]} 게임을 즐겨찾기에 담기`, 'data-key': `fav-${i}`, onclick: () => addFav(i),
        }, '★ 담기')));
  }

  function linePanel(g, i) {
    const links = effLinks(g);
    const marked = new Set(g.nums);
    const grid = h('div', { class: 'grid' }, range(1, 45).map((n) => {
      if (!marked.has(n)) return h('span', { class: 'cell off', 'aria-hidden': 'true' }, String(n));  // 안 칠한 번호는 장식 - 읽어 주지 않는다
      const on = !!state.anchor && state.anchor.g === i && state.anchor.n === n;
      return h('button', {
        type: 'button', class: 'cell on' + (on ? ' anchor' : ''), 'aria-pressed': String(on), 'data-key': `mark-${i}-${n}`,
        'aria-label': `${LETTERS[i]} 게임 ${n}번` + (on ? ', 연결 시작 번호로 선택됨. 이을 번호를 누르세요' : ', 누르면 연결을 시작해요'),
        onclick: () => pointClick(i, n),
      }, String(n));
    }));
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'lines');
    svg.setAttribute('aria-hidden', 'true');
    const stage = h('div', {
      class: 'stage', role: 'group',
      'aria-label': `${LETTERS[i]} 게임 ` + (g.nums.length ? `${g.nums.join(', ')}번과 이은 선 ${links.length}개` : '칠한 번호 없음'),
    }, svg, grid);
    stage._links = links;   // 칸 위치는 화면에 붙은 뒤에 재서 선을 긋는다(layoutLines)
    stage._i = i;
    return h('div', { class: 'panel' + (state.sel === i ? ' cur' : '') },
      h('div', { class: 'panel-head' },
        h('span', { class: 'badge' }, LETTERS[i]),
        h('span', { class: 'tag' }, g.links ? '선 직접' : '선 자동')),
      stage,
      h('div', { class: 'panel-foot' },
        h('button', { type: 'button', class: 'mini-btn', disabled: links.length === 0, 'aria-label': `${LETTERS[i]} 게임 선 모두 지우기`, 'data-key': `clr-${i}`, onclick: () => setLinks(i, []) }, '지우기'),
        h('button', { type: 'button', class: 'mini-btn', disabled: !g.links, 'aria-label': `${LETTERS[i]} 게임 선을 작은 수부터 자동으로 다시 잇기`, 'data-key': `auto-${i}`, onclick: () => setLinks(i, null) }, '자동')));
  }

  function layoutLines() {
    for (const stage of document.querySelectorAll('.stage')) {
      const svg = stage.firstChild;
      const cells = stage.lastChild.children;
      svg.replaceChildren();
      if (!cells[0] || !cells[0].offsetWidth) continue;  // 폰에서 숨겨진 게임
      const center = (n) => [cells[n - 1].offsetLeft + cells[n - 1].offsetWidth / 2, cells[n - 1].offsetTop + cells[n - 1].offsetHeight / 2];
      for (const p of stage._links) {
        const [x1, y1] = center(p[0]);
        const [x2, y2] = center(p[1]);
        const line = (cls) => {
          const l = document.createElementNS(NS, 'line');
          for (const [k, v] of Object.entries({ class: cls, x1, y1, x2, y2 })) l.setAttribute(k, v);
          return l;
        };
        const hit = line('hit');   // 굵고 안 보이는 선: 누르면 지운다
        const tip = document.createElementNS(NS, 'title');
        tip.textContent = '누르면 선이 지워져요';
        hit.append(tip);
        hit.addEventListener('click', () => setLinks(stage._i, effLinks(state.games[stage._i]).filter((q) => !same(q, p[0], p[1]))));
        svg.append(line('ln'), hit);
      }
    }
  }

  function renderMaker() {
    document.querySelectorAll('.mode').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === state.mode)));
    document.querySelectorAll('[data-stats]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.stats === state.statsKind)));
    document.querySelectorAll('[data-fill]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.fill === state.fillKind)));
    $('#opt-stats').hidden = state.mode !== 'stats';
    $('#opt-wish').hidden = state.mode !== 'wish';
    const n = $('#notice');
    n.textContent = state.notice.text;
    n.classList.toggle('err', state.notice.err);
  }

  function renderHist() {
    const s = state.hist;
    const toggle = $('#hist-toggle');
    toggle.setAttribute('aria-expanded', String(s.open));
    toggle.textContent = s.open ? '1등 번호 히스토리 닫기' : '1등 번호 히스토리 보기';
    $('#hist').hidden = !s.open;
    $('#hist-count').textContent = `${s.total}회`;
    const msg = $('#hist-msg');
    msg.textContent = s.msg;
    msg.classList.toggle('err', s.err);
    $('#hist-list').replaceChildren(...(s.rows.length ? s.rows.map((r) => h('div', { class: 'hist-row' },
      h('span', { class: 'hist-round' }, `${r.round}회${r.drawn_on ? ' · ' + r.drawn_on : ''}`),
      h('div', { class: 'balls' }, r.nums.map((n) => ball(n, 'md')),
        r.bonus ? [h('span', { class: 'plus' }, '+'), ball(r.bonus, 'md')] : []))) :
      [h('p', { class: 'hint' }, s.loaded ? '아직 올린 당첨번호가 없어요. 위의 엑셀 파일 올리기로 올려 주세요.' : '불러오는 중…')]));
  }

  function renderFavs() {
    $('#fav-count').textContent = `${state.favs.length}개`;
    $('#fav-empty').hidden = state.favs.length > 0;
    $('#fav-list').replaceChildren(...state.favs.map((f) => h('div', { class: 'fav-row' },
      h('div', { class: 'balls' }, f.nums.map((n) => ball(n, 'sm'))),
      h('button', { type: 'button', class: 'mini-btn', 'aria-label': `즐겨찾기 번호를 ${LETTERS[state.sel]} 게임에 넣기`, 'data-key': `favload-${f.id}`, onclick: () => loadFav(f) }, '넣기'),
      h('button', { type: 'button', class: 'mini-btn danger', 'aria-label': `즐겨찾기 ${f.nums.join(', ')} 삭제`, 'data-key': `favdel-${f.id}`, onclick: () => delFav(f.id) }, '삭제'))));
  }

  function render() {
    const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.key : null;
    renderMaker();
    renderHist();
    renderFavs();
    tabs($('#tabs-paper'), 'p');
    tabs($('#tabs-line'), 'l');
    $('#board-paper').replaceChildren(...state.games.map(paperPanel));
    $('#board-line').replaceChildren(...state.games.map(linePanel));
    layoutLines();
    if (focused) {  // 다시 그리며 사라진 단추의 자리로 키보드 초점을 돌려 놓는다
      const el = document.querySelector(`[data-key="${CSS.escape(focused)}"]`);
      if (el && !el.disabled) el.focus({ preventScroll: true });
    }
  }

  // ---------- 처음 연결 ----------
  document.querySelectorAll('.mode').forEach((b) => b.addEventListener('click', () => { state.mode = b.dataset.mode; render(); }));
  document.querySelectorAll('[data-stats]').forEach((b) => b.addEventListener('click', () => { state.statsKind = b.dataset.stats; render(); }));
  document.querySelectorAll('[data-fill]').forEach((b) => b.addEventListener('click', () => { state.fillKind = b.dataset.fill; render(); }));
  $('#make').addEventListener('click', () => generate([0, 1, 2, 3, 4]));
  $('#clear').addEventListener('click', () => {
    state.games = LETTERS.map(blank);
    state.anchor = null; setNotice(''); render();
  });
  $('#hist-toggle').addEventListener('click', toggleHist);
  $('#hist-upload').addEventListener('click', () => $('#hist-file').click());
  $('#hist-file').addEventListener('change', (e) => {
    const file = e.target.files[0];
    e.target.value = '';
    if (file) upload(file);
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && state.anchor) { state.anchor = null; render(); } });
  window.addEventListener('resize', () => { clearTimeout(layoutLines.t); layoutLines.t = setTimeout(layoutLines, 100); });
  render();
})();

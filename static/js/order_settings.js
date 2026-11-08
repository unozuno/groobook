/* 공통설정(관리자) 페이지 */
(() => {
  const { esc, fetchJson, postJson, toast, confirmDialog, uid, isBlank } = OF;
  const $ = id => document.getElementById(id);

  const state = {
    settings: null,
    meta: null,
    loadedUpdatedAt: null,
    selectedTypeId: null,
    dirty: false,
    tab: 'types',
  };

  const fieldLabel = id => (state.meta.fields.find(f => f.id === id) || {}).label || id;
  const selectedType = () => state.settings.types.find(t => t.id === state.selectedTypeId) || null;

  function markDirty() {
    state.dirty = true;
    $('saveBtn').disabled = false;
    $('discardBtn').disabled = false;
    $('dirtyDot').style.display = '';
  }

  function markClean() {
    state.dirty = false;
    $('saveBtn').disabled = true;
    $('discardBtn').disabled = true;
    $('dirtyDot').style.display = 'none';
  }

  function move(arr, i, delta) {
    const j = i + delta;
    if (j < 0 || j >= arr.length) return false;
    [arr[i], arr[j]] = [arr[j], arr[i]];
    return true;
  }

  // ───────────── 제작 종류 목록 ─────────────
  function renderTypeList() {
    const ul = $('typeList');
    ul.innerHTML = '';
    state.settings.types.forEach((t, i) => {
      const li = document.createElement('li');
      li.className = 'type-item' + (t.id === state.selectedTypeId ? ' active' : '');
      li.innerHTML = `<span class="name" title="${esc(t.name)}">${esc(t.name)}</span>
        <button type="button" class="icon-btn" data-act="up" title="위로" ${i === 0 ? 'disabled' : ''}>▲</button>
        <button type="button" class="icon-btn" data-act="down" title="아래로" ${i === state.settings.types.length - 1 ? 'disabled' : ''}>▼</button>`;
      li.addEventListener('click', e => {
        const act = e.target.closest('[data-act]');
        if (act) {
          e.stopPropagation();
          if (move(state.settings.types, i, act.dataset.act === 'up' ? -1 : 1)) { markDirty(); renderTypeList(); }
          return;
        }
        state.selectedTypeId = t.id;
        renderTypeList();
        renderTypeEditor();
      });
      ul.appendChild(li);
    });
  }

  function emptyType(name) {
    const fields = {};
    for (const f of state.meta.fields) fields[f.id] = { options: [], default: null };
    const item_defaults = {};
    for (const k of state.meta.item_default_keys) item_defaults[k] = null;
    return { id: uid('t'), name, fields, item_defaults };
  }

  function uniqueTypeName(base) {
    const names = new Set(state.settings.types.map(t => t.name));
    if (!names.has(base)) return base;
    let n = 2;
    while (names.has(`${base} (${n})`)) n++;
    return `${base} (${n})`;
  }

  // ───────────── 종류 편집기 ─────────────
  function renderTypeEditor() {
    const t = selectedType();
    const box = $('typeEditor');
    if (!t) {
      box.innerHTML = '<p class="hint">왼쪽에서 제작 종류를 선택하세요.</p>';
      return;
    }
    const idx = state.settings.types.indexOf(t);
    let html = `
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
        <p class="section-title" style="margin:0;flex:1;">${esc(t.name)}</p>
        <button type="button" class="btn-small" data-tact="rename">이름 변경</button>
        <button type="button" class="btn-small" data-tact="dup">복제</button>
        <button type="button" class="btn-small danger" data-tact="del">삭제</button>
      </div>
      <p class="group-heading">품목 표 기본값 (품목 행을 추가할 때 자동 입력)</p>
      <div class="form-grid" style="margin-bottom:6px;">
        ${state.meta.item_default_keys.map(k => `
          <div class="field">
            <label>${esc(state.meta.item_default_labels[k])}</label>
            <input type="text" inputmode="numeric" data-idef="${k}" value="${t.item_defaults[k] == null ? '' : esc(t.item_defaults[k])}" placeholder="비움">
          </div>`).join('')}
      </div>`;

    for (const g of state.meta.groups) {
      html += `<p class="group-heading">${esc(g.name)}</p><div class="field-cards">`;
      for (const fid of g.fields) {
        const f = t.fields[fid];
        html += `<div class="field-card" data-field="${fid}">
          <h4>${esc(fieldLabel(fid))}<span class="group">${f.default == null ? '기본값 없음' : '기본값: ' + esc(f.default)}</span></h4>
          <div class="option-rows">
            ${f.options.map((o, i) => optionRowHtml(fid, o, i, f)).join('')}
          </div>
          <div style="display:flex;gap:6px;align-items:center;margin-top:6px;">
            <button type="button" class="btn-small" data-oact="add" data-field="${fid}">+ 선택지</button>
            <label class="radio-wrap" style="font-size:12px;color:var(--text-muted);display:flex;align-items:center;gap:4px;cursor:pointer;">
              <input type="radio" name="def-${fid}" value="" ${f.default == null ? 'checked' : ''} data-defnull="${fid}"> 기본값 없음
            </label>
          </div>
        </div>`;
      }
      html += '</div>';
    }
    box.innerHTML = html;
    bindTypeEditor(t, idx);
  }

  function optionRowHtml(fid, value, i, f) {
    return `<div class="option-row" data-i="${i}">
      <label class="radio-wrap" title="기본값으로 지정"><input type="radio" name="def-${fid}" value="${esc(value)}" ${f.default === value ? 'checked' : ''}>기본</label>
      <input type="text" value="${esc(value)}" data-opt="${fid}" data-i="${i}">
      <button type="button" class="icon-btn" data-oact="up" data-field="${fid}" data-i="${i}" ${i === 0 ? 'disabled' : ''}>▲</button>
      <button type="button" class="icon-btn" data-oact="down" data-field="${fid}" data-i="${i}" ${i === f.options.length - 1 ? 'disabled' : ''}>▼</button>
      <button type="button" class="icon-btn danger" data-oact="del" data-field="${fid}" data-i="${i}" title="삭제">✕</button>
    </div>`;
  }

  function bindTypeEditor(t, idx) {
    const box = $('typeEditor');

    box.querySelector('[data-tact="rename"]').addEventListener('click', () => {
      const name = window.prompt('새 종류 이름', t.name);
      if (name == null) return;
      const v = name.trim();
      if (!v) { toast('이름을 입력해 주세요.', 'error'); return; }
      if (state.settings.types.some(x => x !== t && x.name === v)) { toast('같은 이름의 종류가 이미 있습니다.', 'error'); return; }
      t.name = v;
      markDirty(); renderTypeList(); renderTypeEditor();
    });
    box.querySelector('[data-tact="dup"]').addEventListener('click', () => {
      const copy = JSON.parse(JSON.stringify(t));
      copy.id = uid('t');
      copy.name = uniqueTypeName(`${t.name} 복사`);
      state.settings.types.splice(idx + 1, 0, copy);
      state.selectedTypeId = copy.id;
      markDirty(); renderTypeList(); renderTypeEditor();
      toast(`'${copy.name}' 으로 복제했습니다. 이름을 바꿔 주세요.`);
    });
    box.querySelector('[data-tact="del"]').addEventListener('click', async () => {
      const ok = await confirmDialog({ title: '종류 삭제', message: `'${t.name}' 종류와 그 선택지·기본값을 모두 삭제합니다. 계속할까요?`, okText: '삭제', danger: true });
      if (!ok) return;
      state.settings.types.splice(idx, 1);
      state.selectedTypeId = state.settings.types[Math.min(idx, state.settings.types.length - 1)]?.id ?? null;
      markDirty(); renderTypeList(); renderTypeEditor();
    });

    for (const inp of box.querySelectorAll('[data-idef]')) {
      inp.addEventListener('input', () => {
        const v = inp.value.trim();
        if (v === '') { t.item_defaults[inp.dataset.idef] = null; inp.classList.remove('cell-error'); }
        else if (/^\d+$/.test(v)) { t.item_defaults[inp.dataset.idef] = parseInt(v, 10); inp.classList.remove('cell-error'); }
        else { inp.classList.add('cell-error'); }
        markDirty();
      });
    }

  }

  // 선택지 편집 이벤트는 컨테이너에 한 번만 붙인다.
  // (렌더링마다 붙이면 리스너가 쌓여 클릭 한 번에 선택지가 여러 개 추가되고 렉이 생긴다)
  function bindTypeEditorDelegates() {
    const box = $('typeEditor');

    box.addEventListener('click', e => {
      const t = selectedType();
      const btn = e.target.closest('[data-oact]');
      if (!t || !btn) return;
      const fid = btn.dataset.field;
      const f = t.fields[fid];
      const i = Number(btn.dataset.i);
      if (btn.dataset.oact === 'add') {
        f.options.push('');
        markDirty(); renderTypeEditor();
        const rows = $('typeEditor').querySelector(`.field-card[data-field="${fid}"] .option-rows`).children;
        rows[rows.length - 1]?.querySelector('input[type=text]')?.focus();
        return;
      }
      if (btn.dataset.oact === 'del') {
        const removed = f.options.splice(i, 1)[0];
        if (f.default === removed) { f.default = null; toast(`'${removed}' 이(가) 기본값이어서 기본값이 해제되었습니다.`); }
        markDirty(); renderTypeEditor();
        return;
      }
      if (move(f.options, i, btn.dataset.oact === 'up' ? -1 : 1)) { markDirty(); renderTypeEditor(); }
    });

    box.addEventListener('input', e => {
      const t = selectedType();
      const inp = e.target;
      if (!t || !inp.dataset.opt) return;
      const f = t.fields[inp.dataset.opt];
      const i = Number(inp.dataset.i);
      const old = f.options[i];
      f.options[i] = inp.value;
      if (f.default === old) {
        f.default = inp.value.trim() === '' ? null : inp.value;
        const radio = inp.parentElement.querySelector('input[type=radio]');
        if (radio) radio.value = inp.value;
      }
      markDuplicates(inp.dataset.opt, f);
      markDirty();
    });

    box.addEventListener('change', e => {
      const t = selectedType();
      const r = e.target;
      if (!t || r.type !== 'radio') return;
      if (r.dataset.defnull) { t.fields[r.dataset.defnull].default = null; markDirty(); renderTypeEditor(); return; }
      const m = /^def-(.+)$/.exec(r.name);
      if (!m) return;
      t.fields[m[1]].default = r.value;
      markDirty(); renderTypeEditor();
    });
  }

  function markDuplicates(fid, f) {
    const card = $('typeEditor').querySelector(`.field-card[data-field="${fid}"]`);
    if (!card) return;
    const counts = {};
    for (const o of f.options) { const k = o.trim(); counts[k] = (counts[k] || 0) + 1; }
    for (const inp of card.querySelectorAll('input[data-opt]')) {
      const k = inp.value.trim();
      inp.classList.toggle('dup', k !== '' && counts[k] > 1);
    }
  }

  // ───────────── 전달사항 ─────────────
  function renderMessages() {
    const wrap = $('messageList');
    const msgs = state.settings.messages;
    wrap.innerHTML = msgs.map((m, i) => `<div class="option-row" style="margin-bottom:6px;">
        <span style="width:24px;text-align:right;color:var(--text-faint);font-size:12px;">${i + 1}</span>
        <input type="text" value="${esc(m)}" data-msg="${i}" style="padding:7px 10px;font-size:14px;">
        <button type="button" class="icon-btn" data-mact="up" data-i="${i}" ${i === 0 ? 'disabled' : ''}>▲</button>
        <button type="button" class="icon-btn" data-mact="down" data-i="${i}" ${i === msgs.length - 1 ? 'disabled' : ''}>▼</button>
        <button type="button" class="icon-btn danger" data-mact="del" data-i="${i}" title="삭제">✕</button>
      </div>`).join('') || '<p class="hint">등록된 문구가 없습니다.</p>';
  }

  function bindMessages() {
    $('messageList').addEventListener('input', e => {
      const inp = e.target;
      if (inp.dataset.msg == null) return;
      state.settings.messages[Number(inp.dataset.msg)] = inp.value;
      const counts = {};
      for (const m of state.settings.messages) { const k = m.trim(); counts[k] = (counts[k] || 0) + 1; }
      for (const el of $('messageList').querySelectorAll('input[data-msg]')) el.classList.toggle('dup', el.value.trim() !== '' && counts[el.value.trim()] > 1);
      markDirty();
    });
    $('messageList').addEventListener('click', async e => {
      const btn = e.target.closest('[data-mact]');
      if (!btn) return;
      const i = Number(btn.dataset.i);
      const msgs = state.settings.messages;
      if (btn.dataset.mact === 'del') {
        const ok = await confirmDialog({ title: '문구 삭제', message: `'${msgs[i]}' 문구를 삭제할까요?`, okText: '삭제', danger: true });
        if (!ok) return;
        msgs.splice(i, 1);
      } else if (!move(msgs, i, btn.dataset.mact === 'up' ? -1 : 1)) return;
      markDirty(); renderMessages();
    });
    $('addMessageBtn').addEventListener('click', () => {
      state.settings.messages.push('');
      markDirty(); renderMessages();
      const inputs = $('messageList').querySelectorAll('input[data-msg]');
      inputs[inputs.length - 1]?.focus();
    });
  }

  // ───────────── 주소록 ─────────────
  function renderAddresses() {
    const book = state.settings.address_book;
    $('addressCount').textContent = `${book.length}곳`;
    $('addressBody').innerHTML = book.map((a, i) => `<tr>
        <td class="idx">${i + 1}</td>
        <td><input type="text" value="${esc(a.name)}" data-addr="name" data-i="${i}"></td>
        <td><input type="text" value="${esc(a.address)}" data-addr="address" data-i="${i}"></td>
        <td><input type="text" value="${esc(a.contact)}" data-addr="contact" data-i="${i}"></td>
        <td><input type="text" value="${esc(a.phone)}" data-addr="phone" data-i="${i}"></td>
        <td class="act" style="white-space:nowrap;width:96px;">
          <button type="button" class="icon-btn" data-aact="up" data-i="${i}" ${i === 0 ? 'disabled' : ''}>▲</button>
          <button type="button" class="icon-btn" data-aact="down" data-i="${i}" ${i === book.length - 1 ? 'disabled' : ''}>▼</button>
          <button type="button" class="icon-btn danger" data-aact="del" data-i="${i}" title="삭제">✕</button>
        </td>
      </tr>`).join('');
    markAddressDuplicates();
  }

  function markAddressDuplicates() {
    const counts = {};
    for (const a of state.settings.address_book) { const k = a.name.trim(); counts[k] = (counts[k] || 0) + 1; }
    for (const inp of $('addressBody').querySelectorAll('input[data-addr="name"]')) {
      const k = inp.value.trim();
      inp.classList.toggle('cell-error', k === '' || counts[k] > 1);
    }
  }

  function bindAddresses() {
    $('addressBody').addEventListener('input', e => {
      const inp = e.target;
      if (!inp.dataset.addr) return;
      state.settings.address_book[Number(inp.dataset.i)][inp.dataset.addr] = inp.value;
      if (inp.dataset.addr === 'name') markAddressDuplicates();
      markDirty();
    });
    $('addressBody').addEventListener('click', async e => {
      const btn = e.target.closest('[data-aact]');
      if (!btn) return;
      const i = Number(btn.dataset.i);
      const book = state.settings.address_book;
      if (btn.dataset.aact === 'del') {
        const ok = await confirmDialog({ title: '캠퍼스 삭제', message: `'${book[i].name}' 을(를) 주소록에서 삭제할까요?`, okText: '삭제', danger: true });
        if (!ok) return;
        book.splice(i, 1);
      } else if (!move(book, i, btn.dataset.aact === 'up' ? -1 : 1)) return;
      markDirty(); renderAddresses();
    });
    $('addAddressBtn').addEventListener('click', () => {
      state.settings.address_book.push({ id: uid('a'), name: '', address: '', contact: '', phone: '' });
      markDirty(); renderAddresses();
      const rows = $('addressBody').children;
      rows[rows.length - 1]?.querySelector('input')?.focus();
      rows[rows.length - 1]?.scrollIntoView({ block: 'nearest' });
    });
  }

  // ───────────── 기타 ─────────────
  function renderMisc() {
    $('multiLabel').value = state.settings.multi_label;
  }

  // ───────────── 탭 ─────────────
  function showTab(name) {
    state.tab = name;
    for (const b of document.querySelectorAll('.tab')) b.classList.toggle('active', b.dataset.tab === name);
    for (const p of document.querySelectorAll('.tab-pane')) p.style.display = p.id === `tab-${name}` ? '' : 'none';
  }

  // ───────────── 저장 · 가져오기 · 초기화 ─────────────
  function clientProblems() {
    const problems = [];
    const s = state.settings;
    const typeNames = s.types.map(t => t.name.trim());
    if (typeNames.some(n => !n)) problems.push('이름이 비어 있는 제작 종류가 있습니다.');
    if (new Set(typeNames).size !== typeNames.length) problems.push('제작 종류 이름이 중복됩니다.');
    for (const t of s.types) {
      for (const [fid, f] of Object.entries(t.fields)) {
        const opts = f.options.map(o => o.trim());
        if (opts.some(o => !o)) problems.push(`${t.name} · ${fieldLabel(fid)}: 빈 선택지가 있습니다.`);
        if (new Set(opts).size !== opts.length) problems.push(`${t.name} · ${fieldLabel(fid)}: 중복 선택지가 있습니다.`);
      }
      for (const [k, v] of Object.entries(t.item_defaults)) {
        if (v != null && (!Number.isInteger(v) || v < 0)) problems.push(`${t.name}: 품목 기본값 ${state.meta.item_default_labels[k]} 은(는) 0 이상의 정수여야 합니다.`);
      }
    }
    const msgs = s.messages.map(m => m.trim());
    if (msgs.some(m => !m)) problems.push('빈 전달사항 문구가 있습니다.');
    if (new Set(msgs).size !== msgs.length) problems.push('전달사항 문구가 중복됩니다.');
    const names = s.address_book.map(a => a.name.trim());
    if (names.some(n => !n)) problems.push('캠퍼스명이 비어 있는 주소록 항목이 있습니다.');
    if (new Set(names).size !== names.length) problems.push('주소록 캠퍼스명이 중복됩니다.');
    if (!s.multi_label.trim()) problems.push('다중 발주 표기 문구가 비어 있습니다.');
    return problems;
  }

  function applyLoaded(settings) {
    state.settings = settings;
    state.loadedUpdatedAt = settings.updated_at;
    if (!state.settings.types.some(t => t.id === state.selectedTypeId)) {
      state.selectedTypeId = state.settings.types[0]?.id ?? null;
    }
    $('savedAt').textContent = settings.updated_at ? `마지막 저장: ${settings.updated_at.replace('T', ' ').slice(0, 19)}` : '';
    markClean();
    renderTypeList();
    renderTypeEditor();
    renderMessages();
    renderAddresses();
    renderMisc();
  }

  async function save(payloadSettings = null, successMsg = '저장되었습니다. 새로 작성하는 발주서부터 적용됩니다.') {
    const settings = payloadSettings || state.settings;
    if (!payloadSettings) {
      const problems = clientProblems();
      if (problems.length) {
        await confirmDialog({ title: '저장할 수 없습니다', items: problems.map(p => ({ level: 'error', message: p })), okText: '확인', cancelText: '닫기' });
        return false;
      }
    }
    const body = { settings, expected_updated_at: state.loadedUpdatedAt };
    const res = await postJson('/api/order-settings', body, 'PUT');
    let data = null;
    try { data = await res.json(); } catch { /* ignore */ }
    if (res.status === 200) {
      applyLoaded(data.settings);
      toast(successMsg);
      return true;
    }
    if (res.status === 409) {
      const ok = await confirmDialog({ title: '다른 곳에서 설정이 수정되었습니다', message: '현재 변경 내용을 버리고 최신 설정을 다시 불러올까요?', okText: '다시 불러오기', danger: true });
      if (ok) await load();
      return false;
    }
    const errors = (data && data.errors) || [(data && data.detail) || '저장에 실패했습니다.'];
    await confirmDialog({ title: '저장할 수 없습니다', items: errors.map(p => ({ level: 'error', message: p })), okText: '확인', cancelText: '닫기' });
    return false;
  }

  async function load() {
    const { res, data } = await fetchJson('/api/order-settings');
    if (!res.ok || !data) { toast('설정을 불러오지 못했습니다.', 'error'); return; }
    state.meta = data.meta;
    applyLoaded(data.settings);
  }

  function bindToolbar() {
    $('saveBtn').addEventListener('click', () => save());
    $('discardBtn').addEventListener('click', async () => {
      const ok = await confirmDialog({ title: '변경 취소', message: '저장하지 않은 변경 내용을 모두 버립니다.', okText: '버리기', danger: true });
      if (ok) await load();
    });
    $('importBtn').addEventListener('click', () => $('importFile').click());
    $('importFile').addEventListener('change', async e => {
      const file = e.target.files[0];
      e.target.value = '';
      if (!file) return;
      let parsed;
      try { parsed = JSON.parse(await file.text()); } catch { toast('JSON 파일을 읽을 수 없습니다.', 'error'); return; }
      const ok = await confirmDialog({
        title: '설정 가져오기',
        message: `'${file.name}' 의 설정으로 현재 설정 전체를 덮어씁니다. 계속할까요?`,
        okText: '가져오기', danger: true,
      });
      if (!ok) return;
      await save(parsed, '설정을 가져왔습니다.');
    });
    $('resetBtn').addEventListener('click', async () => {
      const ok = await confirmDialog({
        title: '초기값으로 되돌리기',
        message: '제작 종류·선택지·기본값·전달사항·주소록을 모두 프로그램 초기값으로 되돌립니다. 되돌릴 수 없습니다.',
        okText: '초기화', danger: true,
      });
      if (!ok) return;
      const { res, data } = await fetchJson('/api/order-settings/reset', { method: 'POST' });
      if (!res.ok) { toast('초기화에 실패했습니다.', 'error'); return; }
      applyLoaded(data.settings);
      toast('초기값으로 되돌렸습니다.');
    });
    for (const b of document.querySelectorAll('.tab')) b.addEventListener('click', () => showTab(b.dataset.tab));
    $('addTypeBtn').addEventListener('click', () => {
      const name = window.prompt('새 제작 종류 이름');
      if (name == null) return;
      const v = name.trim();
      if (!v) return;
      if (state.settings.types.some(t => t.name === v)) { toast('같은 이름의 종류가 이미 있습니다.', 'error'); return; }
      const t = emptyType(v);
      state.settings.types.push(t);
      state.selectedTypeId = t.id;
      markDirty(); renderTypeList(); renderTypeEditor();
    });
    $('multiLabel').addEventListener('input', e => { state.settings.multi_label = e.target.value; markDirty(); });
    window.addEventListener('beforeunload', e => {
      if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  async function init() {
    bindToolbar();
    bindTypeEditorDelegates();
    bindMessages();
    bindAddresses();
    await load();
  }

  init();
})();

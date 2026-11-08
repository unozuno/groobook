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
    priceTypeId: null,
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
        <td><input type="text" value="${esc(a.email || '')}" data-addr="email" data-i="${i}" placeholder="name@example.com" inputmode="email"></td>
        <td class="act" style="white-space:nowrap;width:96px;">
          <button type="button" class="icon-btn" data-aact="up" data-i="${i}" ${i === 0 ? 'disabled' : ''}>▲</button>
          <button type="button" class="icon-btn" data-aact="down" data-i="${i}" ${i === book.length - 1 ? 'disabled' : ''}>▼</button>
          <button type="button" class="icon-btn danger" data-aact="del" data-i="${i}" title="삭제">✕</button>
        </td>
      </tr>`).join('');
    markAddressDuplicates();
    for (const inp of $('addressBody').querySelectorAll('input[data-addr="email"]')) inp.classList.toggle('cell-error', !emailOk(inp.value));
  }

  const EMAIL_RE = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;
  const emailOk = v => !v.trim() || EMAIL_RE.test(v.trim());

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
      if (inp.dataset.addr === 'email') inp.classList.toggle('cell-error', !emailOk(inp.value));
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
      state.settings.address_book.push({ id: uid('a'), name: '', address: '', contact: '', phone: '', email: '' });
      markDirty(); renderAddresses();
      const rows = $('addressBody').children;
      rows[rows.length - 1]?.querySelector('input')?.focus();
      rows[rows.length - 1]?.scrollIntoView({ block: 'nearest' });
    });
  }

  // ───────────── 단가표 ─────────────
  const PRICE_COND_FIELDS = ['binding_method', 'inner_paper', 'inner_print', 'inner_size', 'cover_paper', 'cover_print', 'cover_size'];
  const PRICE_KINDS = { manual: '직접 입력', fixed: '고정 금액', per_page: '페이지당 금액 × 페이지 + 기본액' };

  const DELIVERY_ID = 'delivery';   // 빈 납품서(납품명세서): 제품명 + 수령자별 단가
  const DELIVERY_LABEL = '납품명세서 (빈 납품서)';
  const DELIVERY_KINDS = { manual: '직접 입력', fixed: '고정 금액' };
  const priceKind = r => (r.price ? r.price.kind : 'manual');
  const numOrNull = v => (String(v).trim() === '' ? null : Number(String(v).replace(/,/g, '')));
  const numVal = v => (v == null ? '' : String(v));

  function priceRulesOfType() {
    return state.settings.price_rules.filter(r => r.type_id === state.priceTypeId);
  }

  function renderPrices() {
    const s = state.settings;
    const sel = $('priceType');
    if (state.priceTypeId !== DELIVERY_ID && !s.types.some(t => t.id === state.priceTypeId)) state.priceTypeId = s.types[0]?.id ?? null;
    sel.innerHTML = [...s.types.map(t => [t.id, t.name]), [DELIVERY_ID, DELIVERY_LABEL]]
      .map(([id, name]) => `<option value="${esc(id)}" ${id === state.priceTypeId ? 'selected' : ''}>${esc(name)}</option>`).join('');
    $('priceCount').textContent = `전체 ${s.price_rules.length}줄`;
    $('priceHelp').style.display = state.priceTypeId === DELIVERY_ID ? 'none' : '';
    $('deliveryHelp').style.display = state.priceTypeId === DELIVERY_ID ? '' : 'none';
    if (state.priceTypeId === DELIVERY_ID) { renderDeliveryPrices(); return; }
    const heads = PRICE_COND_FIELDS.map(f => {
      const m = state.meta.fields.find(x => x.id === f);
      return `<th style="min-width:130px;">${esc(m ? `${m.group} ${m.label}` : f)}</th>`;
    }).join('');
    $('priceHead').innerHTML = `<tr><th>#</th>${heads}<th style="min-width:110px;">수량(총 발주수량)</th><th>페이지</th><th style="min-width:150px;">방식</th><th style="min-width:90px;">금액 / 페이지당</th><th style="min-width:80px;">기본액</th><th></th></tr>`;
    const rules = priceRulesOfType();
    // 페이지 조건은 안내문·빙고판처럼 실제로 쓰는 종류에서만 보여 준다
    const showPages = rules.some(r => r.pages != null);
    $('priceHead').innerHTML = $('priceHead').innerHTML.replace(/<th[^>]*>페이지<\/th>/, showPages ? '<th style="min-width:70px;">페이지 수<br><small>(정확히 일치)</small></th>' : '');
    $('priceBody').innerHTML = rules.length ? rules.map((r, i) => {
      const kind = priceKind(r);
      const conds = PRICE_COND_FIELDS.map(f => `<td><input type="text" data-pc="${f}" value="${esc((r.when[f] || []).join(', '))}"></td>`).join('');
      const amount = kind === 'fixed' ? r.price.amount : kind === 'per_page' ? r.price.rate : '';
      const base = kind === 'per_page' ? r.price.base : '';
      return `<tr data-rid="${esc(r.id)}">
        <td class="idx">${i + 1}</td>${conds}
        <td style="white-space:nowrap;"><input type="text" class="num" style="width:56px;" data-pf="qty_min" value="${numVal(r.qty_min)}" inputmode="numeric" placeholder="하한"> ~
          <input type="text" class="num" style="width:56px;" data-pf="qty_max" value="${numVal(r.qty_max)}" inputmode="numeric" placeholder="상한"></td>
        ${showPages ? `<td><input type="text" class="num" data-pf="pages" value="${numVal(r.pages)}" inputmode="numeric"></td>` : ''}
        <td><select data-pkind="1">${Object.entries(PRICE_KINDS).map(([k, l]) => `<option value="${k}" ${k === kind ? 'selected' : ''}>${l}</option>`).join('')}</select></td>
        <td><input type="text" class="num" data-pp="${kind === 'fixed' ? 'amount' : 'rate'}" value="${numVal(amount)}" inputmode="numeric" ${kind === 'manual' ? 'disabled' : ''}></td>
        <td><input type="text" class="num" data-pp="base" value="${numVal(base)}" inputmode="numeric" ${kind === 'per_page' ? '' : 'disabled'}></td>
        <td class="act" style="white-space:nowrap;width:170px;">
          <button type="button" class="icon-btn" data-pact="up" ${i === 0 ? 'disabled' : ''}>▲</button>
          <button type="button" class="icon-btn" data-pact="down" ${i === rules.length - 1 ? 'disabled' : ''}>▼</button>
          <button type="button" class="icon-btn" data-pact="copy" title="이 줄을 그대로 복사해 아래에 추가">복제</button>
          <button type="button" class="icon-btn danger" data-pact="del" title="삭제">✕</button>
        </td></tr>`;
    }).join('') : '<tr><td colspan="12" class="hint" style="text-align:center;padding:14px;">이 제작 종류에는 단가 줄이 없습니다. 단가는 발주서 작성 시 직접 입력해야 합니다.</td></tr>';
  }

  function renderDeliveryPrices() {
    $('priceHead').innerHTML = '<tr><th>#</th><th style="min-width:200px;">제품명</th><th style="min-width:260px;">수령자 (비우면 모든 학원)</th><th style="min-width:130px;">방식</th><th style="min-width:100px;">단가</th><th></th></tr>';
    const rules = priceRulesOfType();
    $('priceBody').innerHTML = rules.length ? rules.map((r, i) => {
      const kind = priceKind(r);
      return `<tr data-rid="${esc(r.id)}">
        <td class="idx">${i + 1}</td>
        <td><input type="text" data-pprod="1" value="${esc(r.product || '')}" placeholder="예: 대봉투"></td>
        <td><input type="text" data-pcamp="1" value="${esc((r.campuses || []).join(', '))}" placeholder="예: 대치크레오, 하남크레오"></td>
        <td><select data-pkind="1">${Object.entries(DELIVERY_KINDS).map(([k, l]) => `<option value="${k}" ${k === kind ? 'selected' : ''}>${l}</option>`).join('')}</select></td>
        <td><input type="text" class="num" data-pp="amount" value="${numVal(kind === 'fixed' ? r.price.amount : '')}" inputmode="numeric" ${kind === 'manual' ? 'disabled' : ''}></td>
        <td class="act" style="white-space:nowrap;width:170px;">
          <button type="button" class="icon-btn" data-pact="up" ${i === 0 ? 'disabled' : ''}>▲</button>
          <button type="button" class="icon-btn" data-pact="down" ${i === rules.length - 1 ? 'disabled' : ''}>▼</button>
          <button type="button" class="icon-btn" data-pact="copy" title="이 줄을 그대로 복사해 아래에 추가">복제</button>
          <button type="button" class="icon-btn danger" data-pact="del" title="삭제">✕</button>
        </td></tr>`;
    }).join('') : '<tr><td colspan="6" class="hint" style="text-align:center;padding:14px;">납품명세서 단가 줄이 없습니다. 빈 납품서의 단가는 직접 입력해야 합니다.</td></tr>';
  }

  function bindPrices() {
    $('priceType').addEventListener('change', e => { state.priceTypeId = e.target.value; renderPrices(); });
    const ruleOf = el => state.settings.price_rules.find(r => r.id === el.closest('tr')?.dataset.rid);

    $('priceBody').addEventListener('input', e => {
      const inp = e.target;
      const r = ruleOf(inp);
      if (!r) return;
      if (inp.dataset.pprod) {
        r.product = inp.value;
      } else if (inp.dataset.pcamp) {
        r.campuses = inp.value.split(',').map(v => v.trim()).filter(Boolean);
      } else if (inp.dataset.pc) {
        r.when[inp.dataset.pc] = inp.value.split(',').map(v => v.trim()).filter(Boolean);
      } else if (inp.dataset.pf) {
        r[inp.dataset.pf] = numOrNull(inp.value);
      } else if (inp.dataset.pp) {
        r.price[inp.dataset.pp] = numOrNull(inp.value);
      } else return;
      markDirty();
    });

    $('priceBody').addEventListener('change', e => {
      if (!e.target.dataset.pkind) return;
      const r = ruleOf(e.target);
      if (!r) return;
      const kind = e.target.value;
      r.price = kind === 'manual' ? null
        : kind === 'fixed' ? { kind: 'fixed', amount: null, rate: null, base: null }
        : { kind: 'per_page', amount: null, rate: null, base: 0 };
      markDirty(); renderPrices();
    });

    $('priceBody').addEventListener('click', async e => {
      const btn = e.target.closest('[data-pact]');
      if (!btn) return;
      const r = ruleOf(btn);
      const all = state.settings.price_rules;
      const idx = all.indexOf(r);
      if (btn.dataset.pact === 'del') {
        const ok = await confirmDialog({ title: '단가 줄 삭제', message: '이 단가 줄을 삭제할까요?', okText: '삭제', danger: true });
        if (!ok) return;
        all.splice(idx, 1);
      } else if (btn.dataset.pact === 'copy') {
        all.splice(idx + 1, 0, { ...JSON.parse(JSON.stringify(r)), id: uid('pr') });
      } else {
        // 같은 제작 종류 안의 이웃 줄과 자리를 바꾼다 (다른 종류 줄은 건너뜀)
        const dir = btn.dataset.pact === 'up' ? -1 : 1;
        let j = idx + dir;
        while (j >= 0 && j < all.length && all[j].type_id !== r.type_id) j += dir;
        if (j < 0 || j >= all.length) return;
        [all[idx], all[j]] = [all[j], all[idx]];
      }
      markDirty(); renderPrices();
    });

    $('addPriceBtn').addEventListener('click', () => {
      if (!state.priceTypeId) return;
      const all = state.settings.price_rules;
      let last = -1;
      all.forEach((r, i) => { if (r.type_id === state.priceTypeId) last = i; });
      all.splice(last + 1, 0, { id: uid('pr'), type_id: state.priceTypeId, when: {}, qty_min: null, qty_max: null, pages: null, product: '', campuses: [],
        price: { kind: 'fixed', amount: null, rate: null, base: null } });
      markDirty(); renderPrices();
      const rows = $('priceBody').children;
      for (const tr of rows) if (tr.dataset.rid === all[last + 1].id) { tr.querySelector('input')?.focus(); tr.scrollIntoView({ block: 'nearest' }); }
    });
  }

  // ───────────── 기타 ─────────────
  function renderMisc() {
    $('multiLabel').value = state.settings.multi_label;
    $('desktopDir').value = state.settings.desktop_dir || '';
    showDesktopHint();
  }

  async function showDesktopHint() {
    const { res, data } = await fetchJson('/api/order-form/desktop-info');
    if (!res.ok || !data) return;
    $('desktopHint').textContent = `현재 저장된 설정 기준 사용 경로: ${data.desktop_dir} (${data.exists ? '폴더 있음' : '폴더 없음'}, 결정 방법: ${data.source})`;
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
    for (const a of s.address_book) {
      if (!emailOk(a.email || '')) problems.push(`'${a.name.trim() || '(이름 없음)'}' 의 이메일 형식이 올바르지 않습니다. 학원당 메일 주소 1개만 입력할 수 있습니다.`);
    }
    const typeName = id => (id === DELIVERY_ID ? '납품명세서' : (s.types.find(t => t.id === id) || {}).name || id);
    s.price_rules.forEach(r => {
      if (r.qty_min != null && r.qty_max != null && r.qty_min > r.qty_max) problems.push(`단가표 · ${typeName(r.type_id)}: 수량 하한이 상한보다 큰 줄이 있습니다.`);
      if (r.type_id === DELIVERY_ID && !(r.product || '').trim()) problems.push('단가표 · 납품명세서: 제품명이 비어 있는 줄이 있습니다.');
      if (r.price && r.price.kind === 'fixed' && r.price.amount == null) problems.push(`단가표 · ${typeName(r.type_id)}: 금액이 비어 있는 고정 단가 줄이 있습니다.`);
      if (r.price && r.price.kind === 'per_page' && r.price.rate == null) problems.push(`단가표 · ${typeName(r.type_id)}: 페이지당 금액이 비어 있는 줄이 있습니다.`);
    });
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
    renderPrices();
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
    $('desktopDir').addEventListener('input', e => { state.settings.desktop_dir = e.target.value; markDirty(); });
    window.addEventListener('beforeunload', e => {
      if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  async function init() {
    bindToolbar();
    bindTypeEditorDelegates();
    bindMessages();
    bindAddresses();
    bindPrices();
    await load();
  }

  init();
})();

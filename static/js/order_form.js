/* 공통발주서 작성 페이지 */
(() => {
  const { esc, fetchJson, postJson, filenameFromDisposition, downloadBlob, fillDatalist,
          makeCombobox, debounce, toast, confirmDialog, choiceDialog, checklistDialog, planItemsHtml, uid, isBlank, parseInt0 } = OF;
  const $ = id => document.getElementById(id);

  const BLANK_ORDER_LABEL = '빈 발주서';
  const BLANK_DELIVERY_LABEL = '납품서';
  const SIZE_FOLLOW_FIELDS = ['insert_size', 'cover_size'];
  const SIZE_SOURCE = 'inner_size';
  const ITEM_NUM_LABELS = { qty: '발주수량', mono: '1도', insert: '청간지', color: '4도', pages: '페이지', unit_price: '단가' };

  const state = {
    settings: null, meta: null,
    mode: 'order', orderType: 'single',
    typeId: null, typeName: '',
    receivedDate: '', dueDate: '', campus: '', multiName: '', jobNo: '',
    spec: {}, specTouched: new Set(), sizeFollow: { insert_size: false, cover_size: false },
    messages: new Set(), messageExtra: '',
    items: [], distribution: [],
    extras: [], distExtras: {},   // 납품서 추가 항목 (단일 / 다중은 분배표 행 id 별)
    serverIssues: null,
    quotes: [],   // 서버가 계산한 품목별 자동 단가 {status, price, reason} | null (품목 순서)
  };

  // ───────────── 헬퍼 ─────────────
  const fieldIds = () => state.meta.fields.map(f => f.id);
  const fieldLabel = id => (state.meta.fields.find(f => f.id === id) || {}).label || id;
  const fieldGroupName = id => (state.meta.groups.find(g => g.fields.includes(id)) || {}).name || fieldLabel(id);
  const typeNames = () => state.settings.types.map(t => t.name);
  const campusNames = () => state.settings.address_book.map(a => a.name);
  const currentType = () => state.settings.types.find(t => t.id === state.typeId) || null;
  const isMulti = () => state.orderType === 'multi' && state.mode !== 'blank_delivery';
  const isBlankDelivery = () => state.mode === 'blank_delivery';

  const ITEM_FIELDS = ['name', 'qty', 'mono', 'insert', 'color', 'pages', 'unitPrice'];
  const itemIsEmpty = it => ITEM_FIELDS.every(f => isBlank(it[f]));

  function newItem() {
    const it = { id: uid('it'), name: '', qty: '', mono: '', insert: '', color: '', pages: '', unitPrice: '' };
    applyItemDefaults(it);
    return it;
  }

  function newDistRow() {
    return { id: uid('d'), campus: '', qtys: {} };
  }

  function applyItemDefaults(it) {
    const t = currentType();
    if (!t || state.mode !== 'order') return;
    const d = t.item_defaults || {};
    for (const key of ['qty', 'mono', 'insert', 'color']) {
      if (d[key] != null && isBlank(it[key])) it[key] = String(d[key]);
    }
  }

  function pageTotal(it) {
    if (isBlankDelivery()) return parseInt0(it.pages).value || 0;
    return (parseInt0(it.mono).value || 0) + (parseInt0(it.insert).value || 0) + (parseInt0(it.color).value || 0);
  }

  function itemQty(it) {
    if (isMulti()) {
      return state.distribution.reduce((s, d) => s + (parseInt0(d.qtys[it.id]).value || 0), 0);
    }
    return parseInt0(it.qty).value || 0;
  }

  function hasUserContent() {
    return state.specTouched.size > 0
      || state.items.some(it => !itemIsEmptyExceptDefaults(it))
      || state.distribution.some(d => d.campus || Object.values(d.qtys).some(v => !isBlank(v)))
      || state.extras.some(ex => !extraIsEmpty(ex))
      || Object.values(state.distExtras).some(rows => rows.some(ex => !extraIsEmpty(ex)));
  }

  function itemIsEmptyExceptDefaults(it) {
    const probe = { ...it };
    const t = currentType();
    const d = (t && t.item_defaults) || {};
    for (const key of ['qty', 'mono', 'insert', 'color']) {
      if (d[key] != null && String(probe[key]) === String(d[key])) probe[key] = '';
    }
    return itemIsEmpty(probe);
  }

  // ───────────── 종류 · 기본값 · 규칙 ─────────────
  function typeDefaults(t) {
    const spec = {};
    for (const f of fieldIds()) spec[f] = (t.fields[f] && t.fields[f].default) || '';
    return spec;   // 기본값 없는 간지·표지 사이즈는 빈칸 ('내지 따름' 은 항상 꺼진 채 시작)
  }

  // '내지 따름' 은 현재 내지 사이즈 값이 해당 칸의 옵션 목록에 있을 때만 켤 수 있다 (rules.can_follow 와 동일)
  const normOpt = v => String(v || '').replace(/\s+/g, '');
  function canFollow(fid) {
    const t = currentType();
    const src = normOpt(state.spec[SIZE_SOURCE]);
    if (!t || state.mode !== 'order' || !src) return false;
    return ((t.fields[fid] && t.fields[fid].options) || []).some(o => normOpt(o) === src);
  }

  function applyRules() {
    const t = currentType();
    if (!t) return;
    const defaults = typeDefaults(t);
    const targeted = new Set();
    const assigned = {};
    for (const rule of state.settings.rules || []) {
      if (rule.when.type_id !== t.id) continue;
      const matched = (state.spec[rule.when.field] || '') === rule.when.equals;
      for (const [fid, value] of Object.entries(rule.set)) {
        targeted.add(fid);
        if (matched && !(fid in assigned)) assigned[fid] = value;
      }
    }
    for (const fid of targeted) {
      if (state.specTouched.has(fid)) continue;
      state.spec[fid] = fid in assigned ? assigned[fid] : defaults[fid];
    }
  }

  function applyTypeDefaults() {
    const t = currentType();
    state.specTouched.clear();
    if (t && state.mode === 'order') {
      state.spec = typeDefaults(t);
      for (const f of SIZE_FOLLOW_FIELDS) state.sizeFollow[f] = false;
      applyRules();
    } else {
      for (const f of fieldIds()) state.spec[f] = '';
      for (const f of SIZE_FOLLOW_FIELDS) state.sizeFollow[f] = false;
    }
    for (const it of state.items) {
      if (itemIsEmpty(it)) applyItemDefaults(it);
    }
  }

  async function onTypeChange() {
    const v = $('typeInput').value.trim();
    let newMode = 'order';
    let newType = null;
    let newName = '';
    if (v === BLANK_ORDER_LABEL) {
      newMode = 'blank_order';
    } else if (v === BLANK_DELIVERY_LABEL) {
      newMode = 'blank_delivery';
    } else if (v) {
      newType = state.settings.types.find(t => t.name === v) || null;
      if (newType) { newMode = 'order'; newName = newType.name; }
      else { newMode = 'blank_order'; newName = v; }
    }
    const sameType = newMode === state.mode && (newType ? newType.id : null) === state.typeId
      && (newMode !== 'blank_order' || newName === state.typeName);
    if (sameType) return;

    if (hasUserContent()) {
      const ok = await confirmDialog({
        title: '제작 종류 변경',
        message: '입력한 사양·품목 값을 새 종류의 기본값으로 덮어씁니다. 계속할까요?',
        okText: '변경',
      });
      if (!ok) { $('typeInput').value = typeInputLabel(); return; }
    }
    state.mode = newMode;
    state.typeId = newType ? newType.id : null;
    state.typeName = newName;
    if (newMode !== 'order' && !newType) {
      // 빈 발주서/납품서: 품목 기본값 제거를 위해 빈 품목으로 리셋하지 않고 값은 유지
    }
    applyTypeDefaults();
    state.serverIssues = null;
    renderAll();
  }

  function typeInputLabel() {
    if (state.mode === 'blank_delivery') return BLANK_DELIVERY_LABEL;
    if (state.mode === 'blank_order') return state.typeName || BLANK_ORDER_LABEL;
    const t = currentType();
    return t ? t.name : '';
  }

  // ───────────── 렌더링: 사양 ─────────────
  function buildSpecTable() {
    const body = $('specBody');
    body.innerHTML = '';
    for (const g of state.meta.groups) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<th>${esc(g.name)}</th>`;
      for (const fid of g.fields) {
        const td = document.createElement('td');
        const follow = SIZE_FOLLOW_FIELDS.includes(fid)
          ? `<button type="button" class="follow-badge off" data-follow="${fid}" title="내지 사이즈를 따라갑니다">내지 따름</button>
             <small class="follow-note" data-follow-note="${fid}"></small>` : '';
        td.innerHTML = `<div class="spec-cell">
            <span class="field-label">${esc(fieldLabel(fid))} ${follow}</span>
            <input type="text" data-field="${fid}" data-path="spec.${fid}">
          </div>`;
        tr.appendChild(td);
      }
      body.appendChild(tr);
    }
    for (const input of body.querySelectorAll('input[data-field]')) {
      makeCombobox(input, 'dl-' + input.dataset.field);
      input.addEventListener('input', () => onSpecInput(input.dataset.field, input.value));
    }
    for (const btn of body.querySelectorAll('[data-follow]')) {
      btn.addEventListener('click', () => {
        const f = btn.dataset.follow;
        if (!state.sizeFollow[f] && !canFollow(f)) {
          if (isBlank(state.spec[SIZE_SOURCE])) toast('내지 사이즈를 먼저 입력해 주세요.');
          updateSpecInputs();
          return;
        }
        state.sizeFollow[f] = !state.sizeFollow[f];
        if (state.sizeFollow[f]) {
          state.specTouched.delete(f);
          state.spec[f] = state.spec[SIZE_SOURCE] || '';
        }
        updateSpecInputs();
        scheduleValidate();
      });
    }
  }

  function onSpecInput(fid, value) {
    state.spec[fid] = value;
    state.specTouched.add(fid);
    if (fid === SIZE_SOURCE) {
      for (const f of SIZE_FOLLOW_FIELDS) {
        if (!state.sizeFollow[f]) continue;
        if (canFollow(f)) state.spec[f] = value;
        else state.sizeFollow[f] = false;    // 옵션에 없는 내지 값이면 따름 자동 해제 (현재 값은 그대로)
      }
    }
    if (SIZE_FOLLOW_FIELDS.includes(fid)) state.sizeFollow[fid] = false;
    applyRules();
    updateSpecInputs(fid);
    scheduleValidate();
  }

  function updateSpecInputs(skip = null) {
    for (const input of $('specBody').querySelectorAll('input[data-field]')) {
      const f = input.dataset.field;
      if (f !== skip && input.value !== (state.spec[f] || '')) input.value = state.spec[f] || '';
    }
    for (const btn of $('specBody').querySelectorAll('[data-follow]')) {
      const f = btn.dataset.follow;
      const on = !!state.sizeFollow[f];
      const unavailable = !on && !canFollow(f);
      btn.classList.toggle('off', !on);
      btn.classList.toggle('unavailable', unavailable);
      btn.title = on ? '내지 사이즈를 따라가는 중입니다. 눌러서 해제'
        : unavailable ? '선택할 수 없습니다' : '내지 사이즈를 따라가지 않습니다. 눌러서 연결';
      const note = $('specBody').querySelector(`[data-follow-note="${f}"]`);
      if (note) {
        const inner = (state.spec[SIZE_SOURCE] || '').trim();
        note.textContent = unavailable && inner && state.mode === 'order'
          ? `${fieldGroupName(f)} 사이즈 옵션에 '${inner}' 이(가) 없어 선택할 수 없습니다` : '';
      }
    }
  }

  function updateSpecDatalists() {
    const t = currentType();
    for (const f of fieldIds()) fillDatalist('dl-' + f, t && state.mode === 'order' ? t.fields[f].options : []);
  }

  // ───────────── 렌더링: 전달사항 ─────────────
  function renderMessages() {
    const wrap = $('msgChecks');
    wrap.innerHTML = '';
    (state.settings.messages || []).forEach((m, i) => {
      const label = document.createElement('label');
      label.innerHTML = `<input type="checkbox" value="${esc(m)}"> ${esc(m)}`;
      const cb = label.querySelector('input');
      cb.checked = state.messages.has(m);
      cb.addEventListener('change', () => {
        if (cb.checked) state.messages.add(m); else state.messages.delete(m);
      });
      wrap.appendChild(label);
    });
    $('msgExtra').value = state.messageExtra;
  }

  // ───────────── 렌더링: 품목 ─────────────
  function itemColumns() {
    if (isBlankDelivery()) {
      return [
        { key: 'name', label: '제품명 *', type: 'text' },
        { key: 'qty', label: '수량', type: 'num' },
        { key: 'pages', label: '페이지', type: 'num' },
        { key: 'unitPrice', label: '단가', type: 'num' },
      ];
    }
    return [
      { key: 'name', label: '교재명 *', type: 'text' },
      { key: 'qty', label: '발주수량', type: 'num', readonly: isMulti() },
      { key: 'mono', label: '1도', type: 'num' },
      { key: 'insert', label: '청간지', type: 'num' },
      { key: 'color', label: '4도', type: 'num' },
      { key: 'pagesCalc', label: '페이지합계', type: 'calc' },
      { key: 'unitPrice', label: '단가', type: 'num' },
    ];
  }

  const PATH_KEY = { name: 'name', qty: 'qty', mono: 'mono', insert: 'insert', color: 'color', pages: 'pages', unitPrice: 'unit_price', pagesCalc: 'pages' };

  function renderItems() {
    const cols = itemColumns();
    $('itemsHead').innerHTML = `<tr><th>#</th>${cols.map(c => `<th>${esc(c.label)}</th>`).join('')}<th></th></tr>`;
    const body = $('itemsBody');
    body.innerHTML = '';
    state.items.forEach((it, i) => {
      const tr = document.createElement('tr');
      tr.dataset.id = it.id;
      let html = `<td class="idx">${i + 1}</td>`;
      for (const c of cols) {
        const path = `items[${i}].${PATH_KEY[c.key]}`;
        if (c.type === 'calc') {
          html += `<td><input type="text" class="num cell-readonly" readonly tabindex="-1" data-calc="pages" data-path="${path}" value="${pageTotal(it)}"></td>`;
        } else {
          const ro = c.readonly ? 'readonly tabindex="-1" class="num cell-readonly"' : `class="${c.type === 'num' ? 'num' : ''}"`;
          const val = c.readonly ? itemQty(it) : esc(it[c.key]);
          const note = c.key === 'unitPrice' ? '<small class="price-note"></small>' : '';
          const list = c.key === 'name' && isBlankDelivery() ? 'list="dl-products" autocomplete="off"' : '';   // 납품서 제품 목록
          html += `<td><input type="text" ${ro} ${list} data-i="${i}" data-k="${c.key}" data-path="${path}" value="${val}" ${c.type === 'num' ? 'inputmode="numeric"' : ''}>${note}</td>`;
        }
      }
      html += `<td class="act"><button type="button" class="icon-btn danger" data-del="${i}" title="행 삭제" ${state.items.length <= 1 ? 'disabled' : ''}>✕</button></td>`;
      tr.innerHTML = html;
      body.appendChild(tr);
    });
    updatePriceCells();
    renderItemsFoot();
  }

  // 입력한 단가 > 자동 단가. 입력이 비어 있으면 자동 단가(없으면 0)로 공급액을 계산한다.
  function effectivePrice(it, i) {
    const typed = parseInt0(it.unitPrice).value;
    if (typed != null) return typed;
    const q = state.quotes[i];
    return q && q.status === 'auto' ? q.price : 0;
  }

  // 단가 칸: 비어 있으면 placeholder 로 자동 단가를 보여 주고, 아래 작은 글씨로 상태를 알린다.
  function updatePriceCells() {
    const body = $('itemsBody');
    state.items.forEach((it, i) => {
      const tr = body.children[i];
      const inp = tr && tr.querySelector('[data-k="unitPrice"]');
      if (!inp) return;
      const note = inp.parentElement.querySelector('.price-note');
      const q = itemIsEmpty(it) ? null : state.quotes[i];
      const typed = parseInt0(it.unitPrice).value;
      inp.classList.toggle('price-auto', !!q && q.status === 'auto' && typed == null);
      let text = '', kind = '', placeholder = '';
      if (q && q.status === 'auto') {
        placeholder = q.price.toLocaleString();
        if (typed == null) { text = '자동 단가'; kind = 'auto'; }
        else if (typed !== q.price) { text = `수정됨 (자동 ${q.price.toLocaleString()})`; kind = 'edited'; }
        else { text = '자동 단가와 같음'; kind = 'auto'; }
      } else if (q) {
        placeholder = '직접 입력';
        if (typed == null) { text = '직접 입력 필요'; kind = 'manual'; }
        inp.title = q.reason;
      }
      if (!q || q.status === 'auto') inp.title = '';
      inp.placeholder = placeholder;
      if (note) { note.textContent = text; note.className = 'price-note ' + kind; }
    });
  }

  function renderItemsFoot() {
    const cols = itemColumns();
    const items = state.items;
    let cells = '';
    for (const c of cols) {
      let v = '';
      if (c.key === 'qty') v = items.reduce((s, it) => s + itemQty(it), 0);
      else if (['mono', 'insert', 'color', 'pages'].includes(c.key)) v = items.reduce((s, it) => s + (parseInt0(it[c.key]).value || 0), 0);
      else if (c.key === 'pagesCalc') v = items.reduce((s, it) => s + pageTotal(it), 0);
      else if (c.key === 'unitPrice') {
        v = '공급액 ' + items.reduce((s, it, i) => s + itemQty(it) * effectivePrice(it, i), 0).toLocaleString();
      }
      cells += `<td>${esc(typeof v === 'number' ? v.toLocaleString() : v)}</td>`;
    }
    $('itemsFoot').innerHTML = `<tr><td>합계</td>${cells}<td></td></tr>`;
  }

  function updateItemsDerived() {
    const body = $('itemsBody');
    state.items.forEach((it, i) => {
      const tr = body.children[i];
      if (!tr) return;
      const calc = tr.querySelector('[data-calc="pages"]');
      if (calc) calc.value = pageTotal(it);
      if (isMulti()) {
        const q = tr.querySelector('[data-k="qty"]');
        if (q) q.value = itemQty(it);
      }
    });
    renderItemsFoot();
  }

  function bindItemsEvents() {
    $('itemsBody').addEventListener('input', e => {
      const inp = e.target;
      if (!inp.dataset.k) return;
      const it = state.items[Number(inp.dataset.i)];
      if (!it) return;
      it[inp.dataset.k] = inp.value;
      state.serverIssues = null;
      updatePriceCells();
      updateItemsDerived();
      if (inp.dataset.k === 'name') renderDistHead();
      scheduleValidate();
    });
    $('itemsBody').addEventListener('click', e => {
      const btn = e.target.closest('[data-del]');
      if (!btn || btn.disabled) return;
      const i = Number(btn.dataset.del);
      const removed = state.items.splice(i, 1)[0];
      state.quotes.splice(i, 1);
      for (const d of state.distribution) delete d.qtys[removed.id];
      renderItems();
      renderDist();
      scheduleValidate();
    });
    $('addItemBtn').addEventListener('click', () => {
      state.items.push(newItem());
      renderItems();
      renderDist();
      const rows = $('itemsBody').children;
      const last = rows[rows.length - 1];
      const first = last && last.querySelector('input:not([readonly])');
      if (first) first.focus();
      scheduleValidate();
    });
  }

  // ───────────── 렌더링: 분배표 ─────────────
  const CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';
  const bookNo = i => CIRCLED[i] || `${i + 1}.`;

  function renderDistHead() {
    const n = state.items.length;
    const books = state.items.map((it, i) => {
      const name = it.name.trim();
      const label = name ? esc(name) : '<span class="dist-missing">(교재명 미입력)</span>';
      return `<th class="dist-book" title="${esc(name)}">${bookNo(i)} ${label}<small>발주 ${itemQty(it).toLocaleString()}부</small></th>`;
    }).join('');
    $('distHead').innerHTML = `
      <tr>
        <th class="dist-corner" rowspan="2" style="min-width:160px;">학원 ↓ / 교재 →</th>
        <th class="dist-group" colspan="${n}">교재 (위 품목 표에서 입력한 교재명)</th>
        <th rowspan="2">소계</th>
        <th rowspan="2"></th>
      </tr>
      <tr>${books}</tr>`;
  }

  function renderDist() {
    if (!isMulti()) { $('distSection').style.display = 'none'; return; }
    $('distSection').style.display = '';
    renderDistHead();
    const body = $('distBody');
    body.innerHTML = '';
    state.distribution.forEach((d, j) => {
      const tr = document.createElement('tr');
      tr.dataset.id = d.id;
      let html = `<td><input type="text" data-j="${j}" data-campus="1" data-path="distribution[${j}].campus" value="${esc(d.campus)}" placeholder="학원 선택 또는 입력"></td>`;
      state.items.forEach((it, i) => {
        html += `<td><input type="text" class="num" inputmode="numeric" data-j="${j}" data-item="${it.id}" data-path="distribution[${j}].qtys[${i}]" value="${esc(d.qtys[it.id] || '')}"></td>`;
      });
      html += `<td><input type="text" class="num cell-readonly" readonly tabindex="-1" data-subtotal="1" value="${distRowTotal(d)}"></td>`;
      html += `<td class="act"><button type="button" class="icon-btn danger" data-deldist="${j}" title="행 삭제">✕</button></td>`;
      tr.innerHTML = html;
      body.appendChild(tr);
    });
    for (const inp of body.querySelectorAll('input[data-campus]')) makeCombobox(inp, 'dl-campuses');
    renderDistFoot();
  }

  const distRowTotal = d => Object.values(d.qtys).reduce((s, v) => s + (parseInt0(v).value || 0), 0);

  function renderDistFoot() {
    const totals = state.items.map(it => itemQty(it));
    const grand = totals.reduce((s, v) => s + v, 0);
    $('distFoot').innerHTML = `<tr><td>합계</td>${totals.map(v => `<td>${v.toLocaleString()}</td>`).join('')}<td>${grand.toLocaleString()}</td><td></td></tr>`;
  }

  function updateDistDerived() {
    const body = $('distBody');
    state.distribution.forEach((d, j) => {
      const tr = body.children[j];
      if (!tr) return;
      const sub = tr.querySelector('[data-subtotal]');
      if (sub) sub.value = distRowTotal(d);
    });
    renderDistFoot();
    renderDistHead();
    updateItemsDerived();
  }

  function bindDistEvents() {
    $('distBody').addEventListener('input', e => {
      const inp = e.target;
      const d = state.distribution[Number(inp.dataset.j)];
      if (!d) return;
      if (inp.dataset.campus) { d.campus = inp.value; updateExtrasTitles(); }
      else if (inp.dataset.item) d.qtys[inp.dataset.item] = inp.value;
      else return;
      state.serverIssues = null;
      updateDistDerived();
      scheduleValidate();
    });
    $('distBody').addEventListener('click', e => {
      const btn = e.target.closest('[data-deldist]');
      if (!btn) return;
      const [gone] = state.distribution.splice(Number(btn.dataset.deldist), 1);
      if (gone) delete state.distExtras[gone.id];
      if (state.distribution.length === 0) state.distribution.push(newDistRow());
      renderDist();
      renderExtras();
      updateItemsDerived();
      scheduleValidate();
    });
    $('addDistBtn').addEventListener('click', () => {
      state.distribution.push(newDistRow());
      renderDist();
      renderExtras();
      const rows = $('distBody').children;
      const last = rows[rows.length - 1];
      const first = last && last.querySelector('input[data-campus]');
      if (first) first.focus();
      scheduleValidate();
    });
  }

  // ───────────── 렌더링: 납품서 추가 항목 ─────────────
  // 단일 발주·납품서 모드는 state.extras 한 벌, 다중 발주는 분배표 행(d.id)마다 따로 가진다.
  const newExtra = () => ({ id: uid('ex'), name: '', qty: '', unitPrice: '' });
  const extraIsEmpty = ex => isBlank(ex.name) && isBlank(ex.qty) && isBlank(ex.unitPrice);
  function extraRows(owner) {
    if (!owner) return state.extras;
    return state.distExtras[owner] || (state.distExtras[owner] = []);
  }
  const extraAmount = ex => {
    const q = parseInt0(ex.qty).value;
    const p = parseInt0(ex.unitPrice).value;
    return q && p != null ? q * p : null;
  };
  const distLabel = (d, j) => d.campus.trim() || `학원 ${j + 1}`;

  function extrasBlockHtml(owner, title, j) {
    const rows = extraRows(owner);
    const prefix = owner ? `extras_by_campus[${j}].extras` : 'extras';
    const head = owner ? `<div class="extras-head"><span class="extras-title" data-extras-title="${esc(owner)}">${esc(title)}</span></div>` : '';
    const body = rows.map((ex, i) => {
      const path = `${prefix}[${i}]`;
      const amt = extraAmount(ex);
      return `<tr>
        <td class="idx">${i + 1}</td>
        <td><input type="text" list="dl-extras" autocomplete="off" data-owner="${esc(owner || '')}" data-eid="${ex.id}" data-k="name" data-path="${path}.name" value="${esc(ex.name)}" placeholder="항목 선택 또는 입력"></td>
        <td><input type="text" class="num" inputmode="numeric" data-owner="${esc(owner || '')}" data-eid="${ex.id}" data-k="qty" data-path="${path}.qty" value="${esc(ex.qty)}"></td>
        <td><input type="text" class="num" inputmode="numeric" data-owner="${esc(owner || '')}" data-eid="${ex.id}" data-k="unitPrice" data-path="${path}.unit_price" value="${esc(ex.unitPrice)}"></td>
        <td><input type="text" class="num cell-readonly" readonly tabindex="-1" data-amount="${ex.id}" value="${amt == null ? '' : amt.toLocaleString()}"></td>
        <td class="act"><button type="button" class="icon-btn danger" data-ex-del="${ex.id}" data-owner="${esc(owner || '')}" title="행 삭제">✕</button></td>
      </tr>`;
    }).join('');
    const table = rows.length ? `<div class="table-wrap" style="margin-bottom:0;"><table class="data-table">
        <thead><tr><th>#</th><th>항목</th><th>수량</th><th>단가</th><th>공급액</th><th></th></tr></thead>
        <tbody>${body}</tbody>
        <tfoot><tr><td colspan="4">합계</td><td data-extras-total="${esc(owner || '')}">${extrasTotal(rows).toLocaleString()}</td><td></td></tr></tfoot>
      </table></div>` : '<p class="extras-empty">추가 항목이 없습니다.</p>';
    const copy = owner && state.distribution.length > 1
      ? `<button type="button" class="btn-small" data-ex-copy-sel="${esc(owner)}">선택한 학원에 복사…</button>
         <button type="button" class="btn-small" data-ex-copy-all="${esc(owner)}">전체 학원에 복사</button>` : '';
    return `<div class="extras-block" data-extras-owner="${esc(owner || '')}">${head}${table}
      <div class="extras-actions"><button type="button" class="btn-small" data-ex-add="${esc(owner || '')}">+ 항목 추가</button>${copy}</div></div>`;
  }

  const extrasTotal = rows => rows.reduce((s, ex) => s + (extraAmount(ex) || 0), 0);

  function renderExtras() {
    const wrap = $('extrasWrap');
    if (!isMulti()) {
      wrap.innerHTML = extrasBlockHtml(null, '', 0);
      return;
    }
    wrap.innerHTML = state.distribution.map((d, j) => extrasBlockHtml(d.id, distLabel(d, j), j)).join('');
  }

  function updateExtrasTitles() {
    state.distribution.forEach((d, j) => {
      const el = document.querySelector(`[data-extras-title="${d.id}"]`);
      if (el) el.textContent = distLabel(d, j);
    });
  }

  async function copyExtras(fromId, mode) {
    const src = extraRows(fromId).filter(ex => !extraIsEmpty(ex));
    if (!src.length) { toast('복사할 추가 항목이 없습니다.'); return; }
    const others = state.distribution.map((d, j) => ({ value: d.id, label: distLabel(d, j) })).filter(o => o.value !== fromId);
    let targets;
    if (mode === 'all') {
      const ok = await confirmDialog({
        title: '전체 학원에 복사',
        message: `이 학원의 추가 항목 ${src.length}개를 다른 ${others.length}개 학원 모두에 복사합니다. 해당 학원들의 기존 추가 항목은 덮어씁니다.`,
        okText: '복사', danger: true,
      });
      if (!ok) return;
      targets = others.map(o => o.value);
    } else {
      targets = await checklistDialog({
        title: '선택한 학원에 복사',
        message: `추가 항목 ${src.length}개를 복사할 학원을 고르세요. 선택한 학원의 기존 추가 항목은 덮어씁니다.`,
        options: others, okText: '복사',
      });
      if (!targets || !targets.length) return;
    }
    for (const id of targets) state.distExtras[id] = src.map(ex => ({ ...ex, id: uid('ex') }));
    renderExtras();
    state.serverIssues = null;
    scheduleValidate();
    toast(`${targets.length}개 학원에 추가 항목을 복사했습니다.`);
  }

  function bindExtrasEvents() {
    const wrap = $('extrasWrap');
    wrap.addEventListener('input', e => {
      const inp = e.target;
      if (!inp.dataset.eid) return;
      const ex = extraRows(inp.dataset.owner || null).find(x => x.id === inp.dataset.eid);
      if (!ex) return;
      ex[inp.dataset.k] = inp.value;
      const amt = wrap.querySelector(`[data-amount="${ex.id}"]`);
      if (amt) { const a = extraAmount(ex); amt.value = a == null ? '' : a.toLocaleString(); }
      const tot = wrap.querySelector(`[data-extras-total="${inp.dataset.owner || ''}"]`);
      if (tot) tot.textContent = extrasTotal(extraRows(inp.dataset.owner || null)).toLocaleString();
      state.serverIssues = null;
      scheduleValidate();
    });
    wrap.addEventListener('click', e => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.exAdd !== undefined) {
        const owner = t.dataset.exAdd || null;
        extraRows(owner).push(newExtra());
        renderExtras();
        const block = wrap.querySelector(`[data-extras-owner="${owner || ''}"]`);
        const inputs = block && block.querySelectorAll('input[data-k="name"]');
        if (inputs && inputs.length) inputs[inputs.length - 1].focus();
        scheduleValidate();
      } else if (t.dataset.exDel) {
        const rows = extraRows(t.dataset.owner || null);
        const i = rows.findIndex(x => x.id === t.dataset.exDel);
        if (i >= 0) rows.splice(i, 1);
        renderExtras();
        state.serverIssues = null;
        scheduleValidate();
      } else if (t.dataset.exCopySel) {
        copyExtras(t.dataset.exCopySel, 'selected');
      } else if (t.dataset.exCopyAll) {
        copyExtras(t.dataset.exCopyAll, 'all');
      }
    });
  }

  function extrasPayload(rows) {
    return rows.map(ex => ({ name: ex.name, qty: ex.qty, unit_price: ex.unitPrice }));
  }

  // 서버 validation._parse_extras 와 동일한 규칙
  function validateExtraRows(rows, prefix, issues) {
    const err = (code, path, message) => issues.push({ level: 'error', code, path, message });
    const warn = (code, path, message) => issues.push({ level: 'warning', code, path, message });
    rows.forEach((ex, i) => {
      if (extraIsEmpty(ex)) return;
      const p = `${prefix}[${i}]`;
      if (!ex.name.trim()) err('EXTRA_NAME_REQUIRED', `${p}.name`, `추가 항목 ${i + 1}번의 항목명을 입력해 주세요.`);
      const q = parseInt0(ex.qty);
      const u = parseInt0(ex.unitPrice);
      if (!q.ok) err('EXTRA_NUM_INVALID', `${p}.qty`, `추가 항목 ${i + 1}번의 수량 값은 0 이상의 정수여야 합니다.`);
      if (!u.ok) err('EXTRA_NUM_INVALID', `${p}.unit_price`, `추가 항목 ${i + 1}번의 단가 값은 0 이상의 정수여야 합니다.`);
      if (!q.value) warn('EXTRA_QTY_EMPTY', `${p}.qty`, `추가 항목 ${i + 1}번의 수량이 비어 있거나 0 입니다.`);
      else if (isBlank(ex.unitPrice)) err('EXTRA_PRICE_REQUIRED', `${p}.unit_price`, `추가 항목 ${i + 1}번의 단가를 입력해 주세요.`);
    });
  }

  // ───────────── 모드별 표시 ─────────────
  function renderModeVisibility() {
    const bd = isBlankDelivery();
    const multi = isMulti();
    $('specSection').style.display = bd ? 'none' : '';
    $('messagesSection').style.display = bd ? 'none' : '';
    $('orderTypeField').style.display = bd ? 'none' : '';
    $('receivedDateField').style.display = bd ? 'none' : '';
    $('blankTypeNameField').style.display = state.mode === 'blank_order' ? '' : 'none';
    $('multiNameField').style.display = multi ? '' : 'none';
    $('campusLabel').textContent = '납품학원';
    $('dueDateLabel').textContent = bd ? '납품일' : '납기일자';
    $('itemsTitle').textContent = bd ? '납품 품목' : '품목';
    $('generateBtn').textContent = bd ? '납품서 생성' : '발주서 생성';

    const campusInput = $('campusInput');
    if (multi) {
      campusInput.value = state.settings.multi_label;
      campusInput.disabled = true;
    } else {
      campusInput.disabled = false;
      if (campusInput.value === state.settings.multi_label) campusInput.value = '';
      campusInput.value = state.campus;
    }

    const hint = $('typeHint');
    if (state.mode === 'blank_order' && state.typeName && !typeNames().includes(state.typeName)
        && $('typeInput').value.trim() === state.typeName) {
      hint.textContent = `'${state.typeName}' 은(는) 등록된 종류가 아니라 빈 발주서 형식으로 생성됩니다.`;
      hint.style.display = '';
    } else if (state.mode === 'blank_order') {
      hint.textContent = '모든 사양을 직접 입력하는 빈 발주서입니다.';
      hint.style.display = '';
    } else if (state.mode === 'blank_delivery') {
      hint.textContent = '발주서 없이 납품서 시트만 생성합니다.';
      hint.style.display = '';
    } else {
      hint.style.display = 'none';
    }
    $('blankTypeName').value = state.typeName;
  }

  function renderAll() {
    renderModeVisibility();
    updateSpecDatalists();
    updateSpecInputs();
    renderItems();
    renderDist();
    renderExtras();
    $('typeInput').value = typeInputLabel();
    $('receivedDate').value = state.receivedDate;
    $('dueDate').value = state.dueDate;
    $('multiName').value = state.multiName;
    $('jobNo').value = state.jobNo;
    validateAndRender();
    scheduleQuote();
  }

  // ───────────── 검증 (서버 validation.py 와 동일 규칙) ─────────────
  function validateClient() {
    const issues = [];
    const err = (code, path, message) => issues.push({ level: 'error', code, path, message });
    const warn = (code, path, message) => issues.push({ level: 'warning', code, path, message });
    const multi = isMulti();
    const bd = isBlankDelivery();
    const addressNames = new Set(campusNames());

    if (state.mode === 'order' && !currentType()) err('TYPE_REQUIRED', 'type_id', '제작 종류를 선택해 주세요.');
    if (multi) {
      if (!state.multiName.trim()) err('MULTI_NAME_REQUIRED', 'multi_name', '다중 발주 파일명에 쓸 이름을 입력해 주세요.');
    } else if (bd) {
      if (!state.campus.trim()) err('RECEIVER_REQUIRED', 'campus', '납품학원을 입력해 주세요.');
    } else if (!state.campus.trim()) {
      err('CAMPUS_REQUIRED', 'campus', '납품학원을 입력해 주세요.');
    }
    if (!state.jobNo.trim()) err('JOB_NO_REQUIRED', 'job_no', '작업번호를 입력해 주세요.');
    if (!state.dueDate) {
      warn('DUE_DATE_MISSING', 'due_date', `${bd ? '납품일' : '납기일자'}이 비어 있어 납품서의 납품일이 빈칸으로 출력됩니다.`);
    }

    const kept = [];
    state.items.forEach((it, i) => {
      if (itemIsEmpty(it)) return;
      kept.push(i);
      if (!it.name.trim()) {
        err('ITEM_NAME_REQUIRED', `items[${i}].name`, `${i + 1}번 품목의 ${bd ? '제품명' : '교재명'}을 입력해 주세요.`);
      }
      const nums = {};
      let priceBad = false;
      for (const [k, pk] of [['qty', 'qty'], ['mono', 'mono'], ['insert', 'insert'], ['color', 'color'], ['pages', 'pages'], ['unitPrice', 'unit_price']]) {
        if (k === 'qty' && multi) { nums.qty = itemQty(it); continue; }
        const p = parseInt0(it[k]);
        if (!p.ok) {
          if (pk === 'unit_price') priceBad = true;
          err(pk === 'unit_price' ? 'PRICE_INVALID' : 'ITEM_NUM_INVALID', `items[${i}].${pk}`,
              `${i + 1}번 품목의 ${ITEM_NUM_LABELS[pk]}은(는) 0 이상의 정수여야 합니다.`);
        }
        nums[k] = p.value;
      }
      const pages = pageTotal(it);
      const hasContent = !!it.name.trim() || !!nums.qty;
      if (!bd && hasContent && pages === 0) warn('ITEM_PAGES_ZERO', `items[${i}].pages`, `${i + 1}번 품목의 페이지합계가 0 입니다.`);
      const others = !!it.name.trim() || [nums.mono, nums.insert, nums.color, nums.unitPrice].some(v => v) || (bd && pages);
      if (!nums.qty && others) warn('ITEM_QTY_EMPTY', `items[${i}].qty`, `${i + 1}번 품목의 발주수량이 비어 있거나 0 입니다.`);
      // 자동 단가가 없는 품목은 단가를 직접 입력해야 한다 (자동 단가 여부는 서버 응답 state.quotes 기준)
      const q = state.quotes[i];
      if (nums.qty && nums.unitPrice == null && !priceBad && q && q.status === 'manual') {
        err('PRICE_REQUIRED', `items[${i}].unit_price`, `${i + 1}번 품목: ${q.reason}`);
      }
    });
    if (kept.length === 0) err('NO_ITEMS', 'items', '품목을 1개 이상 입력해 주세요.');

    if (multi && kept.length) {
      const seen = new Set();
      let campusCount = 0;
      state.distribution.forEach((d, j) => {
        const c = d.campus.trim();
        const anyQty = Object.values(d.qtys).some(v => !isBlank(v));
        if (!c && !anyQty) return;
        let isDup = false;
        if (!c) err('DIST_CAMPUS_EMPTY', `distribution[${j}].campus`, `분배표 ${j + 1}행의 학원을 입력해 주세요.`);
        else if (seen.has(c)) { isDup = true; err('DIST_DUP_CAMPUS', `distribution[${j}].campus`, `분배표에 '${c}' 학원이 중복으로 들어 있습니다.`); }
        else { seen.add(c); campusCount++; }
        let total = 0;
        state.items.forEach((it, i) => {
          if (itemIsEmpty(it)) return;
          const p = parseInt0(d.qtys[it.id]);
          if (!p.ok) err('DIST_NUM_INVALID', `distribution[${j}].qtys[${i}]`, `분배표 ${j + 1}행 ${kept.indexOf(i) + 1}번 품목 수량은 0 이상의 정수여야 합니다.`);
          total += p.value || 0;
        });
        if (c && !isDup) {
          if (total === 0) warn('DIST_CAMPUS_ZERO', `distribution[${j}]`, `'${c}' 의 분배 수량이 모두 0 이라 납품서를 만들지 않습니다.`);
          else if (!addressNames.has(c)) warn('ADDRESS_NOT_FOUND', `distribution[${j}].campus`, `'${c}' 은(는) 주소록에 없어 납품서의 주소·담당자가 빈칸으로 출력됩니다.`);
        }
      });
      if (campusCount < 2) warn('DIST_TOO_FEW', 'distribution', '다중 발주인데 학원이 2곳 미만입니다. 단일 발주가 아닌지 확인해 주세요.');
    } else if (!multi && state.campus.trim() && kept.length && !addressNames.has(state.campus.trim())) {
      warn('ADDRESS_NOT_FOUND', 'campus', `'${state.campus.trim()}' 은(는) 주소록에 없어 납품서의 주소·담당자가 빈칸으로 출력됩니다.`);
    }

    // 납품서 추가 항목
    if (multi) {
      const deliverable = new Set();
      const seenCampus = new Set();
      state.distribution.forEach(d => {
        const c = d.campus.trim();
        const total = state.items.reduce((s, it) => s + (itemIsEmpty(it) ? 0 : (parseInt0(d.qtys[it.id]).value || 0)), 0);
        if (c && !seenCampus.has(c) && total > 0 && kept.length) deliverable.add(d.id);
        if (c) seenCampus.add(c);
      });
      state.distribution.forEach((d, j) => {
        const rows = extraRows(d.id);
        validateExtraRows(rows, `extras_by_campus[${j}].extras`, issues);
        if (rows.some(ex => !extraIsEmpty(ex)) && !deliverable.has(d.id)) {
          warn('EXTRA_CAMPUS_UNKNOWN', `extras_by_campus[${j}].campus`,
               `추가 항목의 학원 '${d.campus.trim()}' 은(는) 납품서가 없어 반영되지 않습니다.`);
        }
      });
    } else {
      validateExtraRows(state.extras, 'extras', issues);
    }
    return issues;
  }

  const TOP_PATHS = { type_id: 'typeInput', campus: 'campusInput', multi_name: 'multiName', due_date: 'dueDate', received_date: 'receivedDate', job_no: 'jobNo' };

  function renderIssues(issues) {
    const list = $('issueList');
    for (const el of document.querySelectorAll('.cell-error, .cell-warning')) el.classList.remove('cell-error', 'cell-warning');
    if (!issues.length) {
      list.innerHTML = '<li class="issue-empty">✔ 문제가 없습니다.</li>';
    } else {
      const order = { error: 0, warning: 1 };
      issues.sort((a, b) => order[a.level] - order[b.level]);
      list.innerHTML = issues.map((i, idx) => `<li class="issue ${esc(i.level)}" data-idx="${idx}" data-target="${esc(i.path)}">
          <span class="badge badge-${esc(i.level)}">${i.level === 'error' ? '오류' : '경고'}</span><span>${esc(i.message)}</span></li>`).join('');
    }
    for (const i of issues) {
      const el = elementForPath(i.path);
      if (el) el.classList.add(i.level === 'error' ? 'cell-error' : 'cell-warning');
    }
    $('generateBtn').disabled = issues.some(i => i.level === 'error');
  }

  function elementForPath(path) {
    if (TOP_PATHS[path]) return $(TOP_PATHS[path]);
    const el = document.querySelector(`[data-path="${CSS.escape(path)}"]`);
    if (el) return el;
    const m = /^distribution\[(\d+)\]$/.exec(path);
    if (m) return document.querySelector(`[data-path="distribution[${m[1]}].campus"]`);
    return null;
  }

  function validateAndRender() {
    const issues = validateClient();
    if (state.serverIssues) {
      const have = new Set(issues.map(i => i.code + '|' + i.path));
      for (const s of state.serverIssues) if (!have.has(s.code + '|' + s.path)) issues.push(s);
    }
    renderIssues(issues);
  }

  // ───────────── 자동 단가 조회 ─────────────
  let quoteSeq = 0;
  async function fetchQuotes() {
    const seq = ++quoteSeq;
    let items = [];
    try {
      const res = await postJson('/api/order-form/price-quote', { order: buildPayload() });
      if (!res.ok) return;
      items = (await res.json()).items || [];
    } catch (e) {
      return;   // 서버가 응답하지 않으면 자동 단가 없이 두고, 생성 시 서버 검증이 판단한다
    }
    if (seq !== quoteSeq) return;   // 더 최근 입력의 응답이 있음
    state.quotes = items;
    updatePriceCells();
    renderItemsFoot();
    validateAndRender();
  }
  const scheduleQuote = debounce(fetchQuotes, 300);

  const scheduleValidate = debounce(() => { validateAndRender(); scheduleQuote(); }, 150);

  // ───────────── 생성 ─────────────
  function buildPayload() {
    const multi = isMulti();
    const items = state.items.map(it => ({
      name: it.name, qty: multi ? String(itemQty(it)) : it.qty, mono: it.mono, insert: it.insert,
      color: it.color, pages: it.pages, unit_price: it.unitPrice,
    }));
    return {
      mode: state.mode,
      order_type: isBlankDelivery() ? 'single' : state.orderType,
      type_id: state.typeId,
      type_name: state.typeName,
      received_date: state.receivedDate,
      due_date: state.dueDate,
      campus: multi ? '' : state.campus,
      multi_name: state.multiName,
      job_no: state.jobNo,
      spec: { ...state.spec },
      messages: [...state.messages],
      message_extra: state.messageExtra,
      items,
      distribution: multi ? state.distribution.map(d => ({ campus: d.campus, qtys: state.items.map(it => d.qtys[it.id] || '') })) : [],
      extras: multi ? [] : extrasPayload(state.extras),
      extras_by_campus: multi ? state.distribution.map(d => ({ campus: d.campus, extras: extrasPayload(extraRows(d.id)) })) : [],
    };
  }

  async function generate(force = false) {
    const btn = $('generateBtn');
    btn.disabled = true;
    hideResult();
    let downloaded = false;
    try {
      const res = await postJson('/api/order-form/generate', { order: buildPayload(), force });
      if (res.status === 200) {
        const blob = await res.blob();
        const filename = filenameFromDisposition(res.headers.get('Content-Disposition')) || '발주서.xlsx';
        downloadBlob(blob, filename);
        showResult(filename);
        downloaded = true;
      } else if (res.status === 409) {
        const data = await res.json();
        const ok = await confirmDialog({
          title: '확인이 필요한 경고가 있습니다',
          message: '아래 내용을 확인한 뒤 그대로 생성할 수 있습니다.',
          items: data.warnings || [],
          okText: '그래도 생성',
        });
        if (ok) { downloaded = await generate(true); return downloaded; }
      } else if (res.status === 422) {
        const data = await res.json();
        state.serverIssues = [...(data.errors || []), ...(data.warnings || [])];
        validateAndRender();
        showError(data.detail || '입력 오류가 있습니다. 검증 결과를 확인해 주세요.');
      } else {
        let detail = '서버 오류가 발생했습니다.';
        try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
        showError(detail);
      }
    } catch (e) {
      showError('서버 연결에 실패했습니다.');
    } finally {
      validateAndRender();
    }
    return downloaded;
  }

  // ───────────── 청구서·마케팅팀 파일 반영 ─────────────
  const TARGET_LABEL = { invoice: '청구서', marketing: '마케팅팀' };
  const toPlanItems = items => items.map(i => ({
    status: i.status, title: `[${TARGET_LABEL[i.target] || i.target}] ${i.campus}`, message: i.message, file: i.file,
  }));

  function selectedTargets() {
    return { invoice: $('reflectInvoice').checked, marketing: $('reflectMarketing').checked };
  }

  async function onGenerate() {
    const targets = selectedTargets();
    if (!targets.invoice && !targets.marketing) { await generate(false); return; }

    $('generateBtn').disabled = true;
    hideResult();
    let plan;
    try {
      const res = await postJson('/api/order-form/reflect', { order: buildPayload(), targets, dry_run: true });
      let data = {};
      try { data = await res.json(); } catch { /* ignore */ }
      if (res.status === 422) {
        state.serverIssues = [...(data.errors || []), ...(data.warnings || [])];
        validateAndRender();
        showError(data.detail || '입력 오류가 있습니다. 검증 결과를 확인해 주세요.');
        return;
      }
      if (!res.ok) { showError(data.detail || '파일 반영 계획을 확인하지 못했습니다.'); return; }
      plan = data.items || [];
    } catch (e) {
      showError('서버 연결에 실패했습니다.');
      return;
    } finally {
      validateAndRender();
    }

    const okCount = plan.filter(i => i.status === 'ok').length;
    const choice = await choiceDialog({
      title: '파일 반영 확인',
      message: okCount
        ? `엑셀 파일을 생성한 뒤 아래 ${okCount}건을 바탕화면 파일에 반영합니다. 반영 전 원본은 자동으로 백업됩니다.`
        : '반영할 수 있는 항목이 없습니다. 엑셀 파일만 생성할 수 있습니다.',
      items: toPlanItems(plan),
      buttons: [
        { label: '취소', value: 'cancel' },
        { label: '파일만 생성', value: 'file' },
        { label: '반영하고 생성', value: 'reflect', primary: true, disabled: okCount === 0 },
      ],
    });
    if (choice !== 'file' && choice !== 'reflect') return;

    const downloaded = await generate(false);
    if (downloaded && choice === 'reflect') await applyReflect(targets);
  }

  async function applyReflect(targets) {
    const box = $('reflectReport');
    try {
      const res = await postJson('/api/order-form/reflect', { order: buildPayload(), targets, dry_run: false });
      const data = await res.json();
      if (!res.ok) { box.innerHTML = planItemsHtml([{ status: 'error', title: '파일 반영', message: data.detail || '반영하지 못했습니다.' }]); return; }
      box.innerHTML = planItemsHtml(toPlanItems(data.items || []));
      if ((data.items || []).some(i => i.status === 'error')) toast('일부 파일에 반영하지 못했습니다. 결과를 확인해 주세요.', 'error');
    } catch (e) {
      box.innerHTML = planItemsHtml([{ status: 'error', title: '파일 반영', message: '서버 연결에 실패했습니다.' }]);
    }
  }

  async function loadDesktopInfo() {
    const { res, data } = await fetchJson('/api/order-form/desktop-info');
    const el = $('desktopInfo');
    if (!res.ok || !data) { el.textContent = ''; return; }
    el.textContent = data.exists
      ? `바탕화면 경로: ${data.desktop_dir}`
      : `바탕화면 경로를 찾을 수 없습니다 (${data.desktop_dir}). 이 기능은 파일이 있는 PC에서 서버를 실행할 때만 쓸 수 있고, 경로는 공통설정에서 바꿀 수 있습니다.`;
    el.style.color = data.exists ? '' : 'var(--danger)';
  }

  function showResult(filename) {
    $('resultSection').style.display = 'flex';
    $('resultFilename').textContent = filename;
    $('errorSection').style.display = 'none';
    $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showError(msg) {
    $('errorSection').style.display = 'flex';
    $('errorMsg').textContent = msg;
    $('resultSection').style.display = 'none';
    $('errorSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideResult() {
    $('reflectReport').innerHTML = '';
    $('resultSection').style.display = 'none';
    $('errorSection').style.display = 'none';
  }

  // ───────────── 초기화 ─────────────
  function resetState() {
    state.mode = 'order';
    state.orderType = 'single';
    state.typeId = null;
    state.typeName = '';
    state.receivedDate = state.meta.today;
    state.dueDate = '';
    state.campus = '';
    state.multiName = '';
    state.jobNo = '';
    state.spec = {};
    for (const f of fieldIds()) state.spec[f] = '';
    state.specTouched.clear();
    state.sizeFollow = { insert_size: false, cover_size: false };
    state.messages.clear();
    state.messageExtra = '';
    state.items = [newItem()];
    state.distribution = [newDistRow(), newDistRow()];
    state.extras = [];
    state.distExtras = {};
    state.serverIssues = null;
    document.querySelector('input[name=orderType][value=single]').checked = true;
    renderMessages();
    hideResult();
    renderAll();
  }

  function bindStatic() {
    $('typeInput').addEventListener('change', onTypeChange);
    $('typeInput').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); onTypeChange(); } });
    for (const r of document.querySelectorAll('input[name=orderType]')) {
      r.addEventListener('change', () => {
        state.orderType = r.value;
        if (state.orderType === 'multi' && state.distribution.length < 2) {
          while (state.distribution.length < 2) state.distribution.push(newDistRow());
        }
        state.serverIssues = null;
        renderAll();
      });
    }
    $('blankTypeName').addEventListener('input', e => { state.typeName = e.target.value; $('typeInput').value = state.typeName || BLANK_ORDER_LABEL; });
    $('receivedDate').addEventListener('input', e => { state.receivedDate = e.target.value; scheduleValidate(); });
    $('dueDate').addEventListener('input', e => { state.dueDate = e.target.value; state.serverIssues = null; scheduleValidate(); });
    $('campusInput').addEventListener('input', e => { if (!e.target.disabled) state.campus = e.target.value; state.serverIssues = null; scheduleValidate(); });
    $('multiName').addEventListener('input', e => { state.multiName = e.target.value; state.serverIssues = null; scheduleValidate(); });
    $('jobNo').addEventListener('input', e => { state.jobNo = e.target.value; state.serverIssues = null; scheduleValidate(); });
    $('msgExtra').addEventListener('input', e => { state.messageExtra = e.target.value; });
    bindItemsEvents();
    bindDistEvents();
    bindExtrasEvents();
    $('issueList').addEventListener('click', e => {
      const li = e.target.closest('[data-target]');
      if (!li) return;
      const el = elementForPath(li.dataset.target);
      if (el && typeof el.focus === 'function') { el.focus(); el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    });
    $('generateBtn').addEventListener('click', onGenerate);
    $('resetBtn').addEventListener('click', async () => {
      if (hasUserContent() || state.campus || state.jobNo) {
        const ok = await confirmDialog({ title: '초기화', message: '입력한 내용을 모두 지웁니다. 계속할까요?', okText: '초기화', danger: true });
        if (!ok) return;
      }
      resetState();
    });
    $('resultCloseBtn').addEventListener('click', hideResult);
    $('errorCloseBtn').addEventListener('click', hideResult);
  }

  async function init() {
    const { res, data } = await fetchJson('/api/order-settings');
    if (!res.ok || !data) { showError('설정을 불러오지 못했습니다. 페이지를 새로고침해 주세요.'); return; }
    state.settings = data.settings;
    state.meta = data.meta;
    fillDatalist('dl-types', [...typeNames(), BLANK_ORDER_LABEL, BLANK_DELIVERY_LABEL]);
    fillDatalist('dl-campuses', campusNames());
    fillDatalist('dl-extras', state.meta.extra_presets || []);
    fillDatalist('dl-products', [...new Set(state.settings.price_rules.filter(r => r.type_id === 'delivery').map(r => r.product))]);
    for (const f of fieldIds()) fillDatalist('dl-' + f, []);
    makeCombobox($('typeInput'), 'dl-types');
    makeCombobox($('campusInput'), 'dl-campuses');
    buildSpecTable();
    bindStatic();
    resetState();
    loadDesktopInfo();
  }

  init();
})();

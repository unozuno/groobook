/* 공통발주서 페이지 공용 유틸 (order_form.js, order_settings.js 에서 사용) */
window.OF = (() => {
  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ESC[c]);

  async function fetchJson(url, opts = {}) {
    const res = await fetch(url, opts);
    let data = null;
    try { data = await res.json(); } catch { /* 본문 없음 */ }
    return { res, data };
  }

  function postJson(url, body, method = 'POST') {
    return fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  function filenameFromDisposition(header) {
    const m = /filename\*=UTF-8''([^;]+)/i.exec(header || '');
    return m ? decodeURIComponent(m[1]) : null;
  }

  function downloadBlob(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function fillDatalist(id, options) {
    let dl = document.getElementById(id);
    if (!dl) {
      dl = document.createElement('datalist');
      dl.id = id;
      document.body.appendChild(dl);
    }
    dl.innerHTML = '';
    for (const o of options) {
      if (o === '' || o == null) continue;
      const opt = document.createElement('option');
      opt.value = o;
      dl.appendChild(opt);
    }
    return dl;
  }

  /**
   * 드롭다운 + 직접 입력 콤보박스.
   * input 에 datalist 를 연결한다. 목록 화살표는 브라우저 기본 것 하나만 쓴다
   * (별도 토글 버튼은 값을 비워서 초기화처럼 보이므로 두지 않는다).
   */
  function makeCombobox(input, datalistId) {
    input.setAttribute('list', datalistId);
    input.setAttribute('autocomplete', 'off');
    if (input.parentElement && input.parentElement.classList.contains('combo')) return input;
    const wrap = document.createElement('div');
    wrap.className = 'combo';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    return input;
  }

  function debounce(fn, ms) {
    let t = null;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  let toastEl = null;
  let toastTimer = null;
  function toast(msg, kind = '') {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.className = 'toast show' + (kind ? ' ' + kind : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2600);
  }

  /**
   * 확인 모달. items 가 있으면 목록으로 보여준다. resolve(true|false).
   */
  function confirmDialog({ title, message = '', items = [], okText = '확인', cancelText = '취소', danger = false }) {
    return new Promise(resolve => {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.innerHTML = `
        <div class="modal-box">
          <h3>${esc(title)}</h3>
          ${message ? `<p class="modal-subtitle">${esc(message)}</p>` : ''}
          ${items.length ? `<ul class="issue-list" style="margin-bottom:20px;">${items.map(i =>
            `<li class="issue ${esc(i.level || 'warning')}"><span class="badge badge-${esc(i.level || 'warning')}">${i.level === 'error' ? '오류' : '경고'}</span><span>${esc(i.message || i)}</span></li>`
          ).join('')}</ul>` : ''}
          <div class="modal-actions">
            <button class="btn-secondary" data-act="cancel">${esc(cancelText)}</button>
            <button class="btn-primary" data-act="ok" ${danger ? 'style="background:var(--danger)"' : ''}>${esc(okText)}</button>
          </div>
        </div>`;
      const done = v => { overlay.remove(); resolve(v); };
      overlay.querySelector('[data-act="ok"]').addEventListener('click', () => done(true));
      overlay.querySelector('[data-act="cancel"]').addEventListener('click', () => done(false));
      overlay.addEventListener('click', e => { if (e.target === overlay) done(false); });
      document.body.appendChild(overlay);
      overlay.querySelector('[data-act="ok"]').focus();
    });
  }

  function uid(prefix = 'id') {
    return prefix + '_' + Math.random().toString(16).slice(2, 10);
  }

  function isBlank(v) {
    return v == null || String(v).trim() === '';
  }

  /** 서버 validation.parse_int 와 동일한 규칙. 반환: {ok, value} */
  function parseInt0(v) {
    if (isBlank(v)) return { ok: true, value: null };
    const s = String(v).trim().replace(/,/g, '');
    if (!/^-?\d+(\.0+)?$/.test(s)) return { ok: false, value: null };
    const n = parseInt(s, 10);
    if (n < 0) return { ok: false, value: null };
    return { ok: true, value: n };
  }

  return { esc, fetchJson, postJson, filenameFromDisposition, downloadBlob, fillDatalist,
           makeCombobox, debounce, toast, confirmDialog, uid, isBlank, parseInt0 };
})();

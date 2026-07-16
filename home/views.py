import json
import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt


# ---------------------------------------------------------------------------
# TIP API proxy — forwards same-origin /tip-api/... calls to the real API
# ---------------------------------------------------------------------------
@csrf_exempt
def tip_api_proxy(request, path):
    """Transparent proxy that adds the x-api-key header server-side."""
    target_url = f"{settings.TIP_API_URL}/{path}"
    params = request.GET.dict()

    headers = {
        "x-api-key": settings.TIP_API_TOKEN,
        "Content-Type": "application/json",
    }

    try:
        if request.method == "GET":
            resp = requests.get(target_url, params=params, headers=headers, timeout=30)
        else:
            try:
                body = json.loads(request.body or "{}")
            except Exception:
                body = {}
            resp = requests.request(
                request.method,
                target_url,
                params=params,
                json=body,
                headers=headers,
                timeout=30,
            )
        return HttpResponse(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
    except Exception as exc:
        return JsonResponse({"status": False, "message": str(exc)}, status=502)


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
def index(request):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Patent Search — TriangleIP</title>
  <link rel="stylesheet" href="/static/tip_design.css" />
  <style>
    /* ---- search bar ---- */
    .search-wrap {
      position: relative;
      max-width: 580px;
      margin: 0 auto 2rem;
    }
    .search-row {
      display: flex;
      gap: .5rem;
    }
    .search-input {
      flex: 1;
      padding: .6rem 1rem;
      border: 1.5px solid var(--tip-border, #d1d5db);
      border-radius: 8px;
      font-size: 1rem;
      font-family: inherit;
      outline: none;
      transition: border-color .2s;
    }
    .search-input:focus {
      border-color: var(--tip-primary, #4f46e5);
      box-shadow: 0 0 0 3px rgba(79,70,229,.15);
    }

    /* ---- autocomplete dropdown ---- */
    #suggestions {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      right: 80px;   /* leave room for button */
      background: #fff;
      border: 1.5px solid var(--tip-border, #d1d5db);
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(0,0,0,.1);
      z-index: 999;
      max-height: 280px;
      overflow-y: auto;
      display: none;
    }
    .suggest-item {
      padding: .55rem 1rem;
      cursor: pointer;
      font-size: .9rem;
      border-bottom: 1px solid #f3f4f6;
      color: var(--tip-text, #111827);
      transition: background .15s;
    }
    .suggest-item:last-child { border-bottom: none; }
    .suggest-item:hover, .suggest-item.active {
      background: var(--tip-primary-light, #ede9fe);
      color: var(--tip-primary, #4f46e5);
    }
    .suggest-meta {
      font-size: .75rem;
      color: var(--tip-text-secondary, #6b7280);
      display: block;
      margin-top: 1px;
    }

    /* ---- result grid ---- */
    .result-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 1.2rem;
      margin-bottom: 2rem;
    }
    .field-card {
      background: var(--tip-surface, #fff);
      border: 1.5px solid var(--tip-border, #e5e7eb);
      border-radius: 12px;
      padding: 1.1rem 1.3rem;
    }
    .field-label {
      font-size: .72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--tip-text-secondary, #6b7280);
      margin-bottom: .4rem;
    }
    .field-value {
      font-size: 1.05rem;
      font-weight: 500;
      color: var(--tip-text, #111827);
      word-break: break-word;
    }
    .field-value.em-dash {
      color: var(--tip-text-secondary, #9ca3af);
      font-style: italic;
    }

    /* ---- placeholder / states ---- */
    .placeholder-wrap {
      text-align: center;
      padding: 4rem 1rem;
      color: var(--tip-text-secondary, #6b7280);
    }
    .placeholder-wrap svg {
      width: 72px;
      height: 72px;
      margin-bottom: 1rem;
      opacity: .35;
    }
    .placeholder-wrap p {
      font-size: 1rem;
      margin-top: .5rem;
    }

    /* ---- patent header banner ---- */
    .patent-header {
      background: linear-gradient(135deg, var(--tip-primary, #4f46e5) 0%, #7c3aed 100%);
      color: #fff;
      border-radius: 12px;
      padding: 1.4rem 1.8rem;
      margin-bottom: 1.5rem;
    }
    .patent-header h2 {
      margin: 0 0 .3rem;
      font-size: 1.25rem;
      font-weight: 700;
    }
    .patent-header .sub {
      font-size: .85rem;
      opacity: .85;
    }
    .patent-header .quota-badge {
      float: right;
      font-size: .75rem;
      background: rgba(255,255,255,.2);
      border-radius: 20px;
      padding: .2rem .75rem;
      margin-top: .2rem;
    }

    /* ---- spinner ---- */
    .spinner {
      display: inline-block;
      width: 22px; height: 22px;
      border: 3px solid rgba(79,70,229,.25);
      border-top-color: var(--tip-primary, #4f46e5);
      border-radius: 50%;
      animation: spin .7s linear infinite;
      vertical-align: middle;
      margin-right: .5rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ---- diagnostics ---- */
    details.diag-wrap { margin-top: 2rem; }
    details.diag-wrap summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--tip-primary, #4f46e5);
      padding: .5rem 0;
      list-style: none;
      display: flex;
      align-items: center;
      gap: .5rem;
    }
    details.diag-wrap summary::before {
      content: '▶';
      font-size: .7rem;
      transition: transform .2s;
    }
    details.diag-wrap[open] summary::before { transform: rotate(90deg); }
    .diag-section-title {
      font-size: .72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--tip-text-secondary, #6b7280);
      margin: 1rem 0 .4rem;
    }
    .diag-code {
      background: #f8f9fb;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      padding: .55rem .85rem;
      font-family: 'Fira Code', 'Courier New', monospace;
      font-size: .78rem;
      white-space: pre-wrap;
      word-break: break-word;
      color: #374151;
    }
    .diag-mapping-table {
      width: 100%;
      border-collapse: collapse;
      font-size: .82rem;
    }
    .diag-mapping-table th {
      text-align: left;
      padding: .4rem .7rem;
      background: #f3f4f6;
      font-weight: 600;
      color: #374151;
      border-bottom: 1px solid #e5e7eb;
    }
    .diag-mapping-table td {
      padding: .4rem .7rem;
      border-bottom: 1px solid #f3f4f6;
      color: #4b5563;
      font-family: 'Fira Code', 'Courier New', monospace;
      font-size: .77rem;
    }
    .diag-mapping-table tr:last-child td { border-bottom: none; }
  </style>
</head>
<body>
<div class="tip-page">

  <!-- ── Navbar ─────────────────────────────────────────────── -->
  <nav class="tip-navbar">
    <a class="tip-navbar-brand" href="/">TriangleIP</a>
  </nav>

  <!-- ── Page heading ───────────────────────────────────────── -->
  <h1 class="tip-page-title">Patent Search</h1>
  <p style="color:var(--tip-text-secondary);margin-top:-.5rem;margin-bottom:1.8rem;max-width:560px;">
    Enter a US application number, publication number, or patent number to retrieve
    bibliographic details from the USPTO via the TIP API.
  </p>

  <!-- ── Search bar ─────────────────────────────────────────── -->
  <div class="search-wrap">
    <div class="search-row">
      <input
        id="searchInput"
        class="search-input"
        type="text"
        placeholder="e.g. 16/687,273 · US8623891 · EP1514569A1"
        autocomplete="off"
        aria-label="Patent number"
      />
      <button class="tip-btn tip-btn-primary" id="searchBtn" onclick="doSearch()">Search</button>
    </div>
    <div id="suggestions" role="listbox"></div>
  </div>

  <!-- ── Status / spinner ────────────────────────────────────── -->
  <div id="statusMsg" style="text-align:center;margin-bottom:1rem;min-height:32px;"></div>

  <!-- ── Results area ───────────────────────────────────────── -->
  <div id="results">
    <!-- placeholder shown before first search -->
    <div class="placeholder-wrap" id="placeholder">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.4"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586
             a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19
             a2 2 0 01-2 2z"/>
      </svg>
      <h3 style="font-size:1.1rem;font-weight:600;color:var(--tip-text);">No patent searched yet</h3>
      <p>Type at least 5 characters to see suggestions, or enter a number and press Search.</p>
    </div>
  </div>

  <!-- ── Diagnostics ────────────────────────────────────────── -->
  <div class="tip-card" style="margin-top:2.5rem;">
    <details class="diag-wrap" id="diagDetails">
      <summary>Diagnostics</summary>

      <div class="diag-section-title">1 · User Request</div>
      <div class="diag-code">Create a patent search page with type-ahead suggestions and a result view
showing attorney name, law firm name, assignee name, examiner name, filing date,
and disposal status — all sourced live from the TIP patent-lookup API.</div>

      <div class="diag-section-title">2 · API Calls Made</div>
      <div class="diag-code" id="diagCalls">—</div>

      <div class="diag-section-title">3 · Input Parameters Sent</div>
      <div class="diag-code" id="diagInput">—</div>

      <div class="diag-section-title">4 · Output Fields Received</div>
      <div class="diag-code" id="diagOutput">—</div>

      <div class="diag-section-title">5 · Field Mapping (API → UI)</div>
      <div class="tip-table-wrap">
        <table class="diag-mapping-table">
          <thead>
            <tr>
              <th>API Response Field</th>
              <th>UI Element</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>data.application.attorneys[0].full_name</td><td>Attorney Name card</td></tr>
            <tr><td>data.application.attorneys[0].law_firm_name</td><td>Law Firm Name card</td></tr>
            <tr><td>data.application.assignees[0].name</td><td>Assignee Name card</td></tr>
            <tr><td>data.application.examiners[0].full_name</td><td>Examiner Name card</td></tr>
            <tr><td>data.application.filing_date</td><td>Filing Date card</td></tr>
            <tr><td>data.application.app_status / disposal</td><td>Disposal Status card</td></tr>
            <tr><td>data.quota.used / limit / remaining</td><td>Quota badge in header</td></tr>
            <tr><td>data.jurisdiction</td><td>Patent header sub-line</td></tr>
            <tr><td>data.application_number</td><td>Patent header title</td></tr>
          </tbody>
        </table>
      </div>
    </details>
  </div>

</div><!-- /.tip-page -->

<script>
/* =========================================================
   Constants & state
   ========================================================= */
const SUGGEST_URL  = '/tip-api/v1/patent-lookup/suggest';
const SEARCH_URL   = '/tip-api/v1/patent-lookup/search';

let suggestTimer   = null;
let activeIndex    = -1;
let lastQuery      = '';
let currentSuggestions = [];

/* =========================================================
   Diagnostics helpers
   ========================================================= */
function diagReset() {
  document.getElementById('diagCalls').textContent  = '—';
  document.getElementById('diagInput').textContent  = '—';
  document.getElementById('diagOutput').textContent = '—';
}

function diagUpdate({ calls, input, output }) {
  if (calls)  document.getElementById('diagCalls').textContent  = calls;
  if (input)  document.getElementById('diagInput').textContent  = JSON.stringify(input, null, 2);
  if (output) document.getElementById('diagOutput').textContent = JSON.stringify(output, null, 2);
}

/* =========================================================
   Status bar
   ========================================================= */
function setStatus(html) {
  document.getElementById('statusMsg').innerHTML = html;
}
function clearStatus() {
  document.getElementById('statusMsg').innerHTML = '';
}

/* =========================================================
   Autocomplete / suggest
   ========================================================= */
const inputEl   = document.getElementById('searchInput');
const suggestEl = document.getElementById('suggestions');

inputEl.addEventListener('input', () => {
  const q = inputEl.value.trim();
  clearTimeout(suggestTimer);
  if (q.length < 5) { closeSuggestions(); return; }
  suggestTimer = setTimeout(() => fetchSuggestions(q), 280);
});

inputEl.addEventListener('keydown', e => {
  if (!suggestEl.style.display || suggestEl.style.display === 'none') {
    if (e.key === 'Enter') doSearch();
    return;
  }
  const items = suggestEl.querySelectorAll('.suggest-item');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    activeIndex = Math.min(activeIndex + 1, items.length - 1);
    updateActive(items);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    activeIndex = Math.max(activeIndex - 1, 0);
    updateActive(items);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (activeIndex >= 0 && activeIndex < currentSuggestions.length) {
      selectSuggestion(currentSuggestions[activeIndex]);
    } else {
      doSearch();
    }
  } else if (e.key === 'Escape') {
    closeSuggestions();
  }
});

document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrap')) closeSuggestions();
});

function updateActive(items) {
  items.forEach((el, i) => {
    el.classList.toggle('active', i === activeIndex);
  });
}

async function fetchSuggestions(q) {
  if (q === lastQuery) return;
  lastQuery = q;
  try {
    const url = `${SUGGEST_URL}?q=${encodeURIComponent(q)}`;
    const resp = await fetch(url);
    const data = await resp.json();
    if (!data.status || !Array.isArray(data.data?.results)) {
      closeSuggestions(); return;
    }
    currentSuggestions = data.data.results;
    renderSuggestions(currentSuggestions);
  } catch (_) {
    closeSuggestions();
  }
}

function renderSuggestions(items) {
  if (!items.length) { closeSuggestions(); return; }
  activeIndex = -1;
  suggestEl.innerHTML = items.map((s, i) => `
    <div class="suggest-item" role="option" data-index="${i}">
      <strong>${escHtml(s.display || s.id)}</strong>
      ${s.title ? `<span class="suggest-meta">${escHtml(s.title)}</span>` : ''}
    </div>`).join('');
  suggestEl.querySelectorAll('.suggest-item').forEach((el, i) => {
    el.addEventListener('mousedown', () => selectSuggestion(items[i]));
  });
  suggestEl.style.display = 'block';
}

function closeSuggestions() {
  suggestEl.style.display = 'none';
  suggestEl.innerHTML = '';
  activeIndex = -1;
  currentSuggestions = [];
}

function selectSuggestion(s) {
  inputEl.value = s.display || s.id;
  closeSuggestions();
  doSearch(inputEl.value);
}

/* =========================================================
   Search / result rendering
   ========================================================= */
async function doSearch(overrideQuery) {
  const query = (overrideQuery || inputEl.value).trim();
  if (!query) {
    setStatus('<span style="color:var(--tip-error,#dc2626);">Please enter a patent number.</span>');
    return;
  }

  // Hide placeholder, show spinner
  hidePlaceholder();
  setStatus('<span class="spinner"></span> Searching…');
  diagReset();
  clearResults();

  const body = { query };
  diagUpdate({
    calls: `GET  ${SUGGEST_URL}?q=<typed>\nPOST ${SEARCH_URL}`,
    input: { query },
  });

  try {
    const resp = await fetch(SEARCH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await resp.json();

    if (!resp.ok || !data.status) {
      const msg = data.message || `HTTP ${resp.status}`;
      renderError(msg);
      clearStatus();
      diagUpdate({ output: { error: msg, status: data.status } });
      return;
    }

    clearStatus();
    renderResult(data, query);
  } catch (err) {
    renderError(`Network error: ${err.message}`);
    clearStatus();
    diagUpdate({ output: { error: err.message } });
  }
}

/* ---- value extraction helpers ---- */
function safeVal(val) {
  if (val === null || val === undefined || val === '' || val === 'N/A') return null;
  return String(val).trim() || null;
}

function orDash(val) {
  return safeVal(val) ?? '—';
}

/* 
  The API response shape varies — try several known paths so we gracefully
  handle both documented and real-world shapes.
*/
function extractFields(data) {
  const app  = data.data?.application || {};
  const root = data.data || {};

  // ── Attorney ──────────────────────────────────────────────────────────────
  // Try: attorneys array → single attorney object → flat fields
  let attorney = null;
  if (Array.isArray(app.attorneys) && app.attorneys.length) {
    attorney = safeVal(app.attorneys[0]?.full_name)
      || safeVal(app.attorneys[0]?.name)
      || safeVal(app.attorneys[0]?.attorney_name);
  }
  if (!attorney) attorney = safeVal(app.attorney_name)
    || safeVal(app.attorney)
    || safeVal(root.attorney_name);

  // ── Law firm ──────────────────────────────────────────────────────────────
  let lawFirm = null;
  if (Array.isArray(app.attorneys) && app.attorneys.length) {
    lawFirm = safeVal(app.attorneys[0]?.law_firm_name)
      || safeVal(app.attorneys[0]?.firm_name)
      || safeVal(app.attorneys[0]?.firm);
  }
  if (!lawFirm) lawFirm = safeVal(app.law_firm_name)
    || safeVal(app.law_firm)
    || safeVal(root.law_firm_name);

  // ── Assignee ──────────────────────────────────────────────────────────────
  let assignee = null;
  if (Array.isArray(app.assignees) && app.assignees.length) {
    assignee = safeVal(app.assignees[0]?.name)
      || safeVal(app.assignees[0]?.assignee_name);
  }
  if (!assignee) assignee = safeVal(app.assigneeName)
    || safeVal(app.assignee_name)
    || safeVal(app.assignee)
    || safeVal(root.assigneeName);

  // ── Examiner ──────────────────────────────────────────────────────────────
  let examiner = null;
  if (Array.isArray(app.examiners) && app.examiners.length) {
    examiner = safeVal(app.examiners[0]?.full_name)
      || safeVal(app.examiners[0]?.name);
  }
  if (!examiner) examiner = safeVal(app.examiner_name)
    || safeVal(app.examiner)
    || safeVal(root.examiner_name);

  // ── Filing date ───────────────────────────────────────────────────────────
  const filingDate = safeVal(app.filing_date)
    || safeVal(app.filing_dt)
    || safeVal(root.filing_date);

  // ── Disposal / status ─────────────────────────────────────────────────────
  const disposal = safeVal(app.app_status)
    || safeVal(app.status)
    || safeVal(app.disposal_type)
    || safeVal(root.app_status);

  // ── Quota ─────────────────────────────────────────────────────────────────
  const quota = data.data?.quota || root.quota || null;

  return { attorney, lawFirm, assignee, examiner, filingDate, disposal, quota };
}

function renderResult(data, query) {
  const appNum      = data.data?.application_number || query;
  const jurisdiction = (data.data?.jurisdiction || 'us').toUpperCase();
  const {
    attorney, lawFirm, assignee, examiner, filingDate, disposal, quota
  } = extractFields(data);

  const quotaBadge = quota
    ? `<span class="quota-badge">Quota: ${quota.used}/${quota.limit} used · ${quota.remaining} remaining</span>`
    : '';

  const resultsEl = document.getElementById('results');
  resultsEl.innerHTML = `
    <!-- Patent header banner -->
    <div class="patent-header">
      ${quotaBadge}
      <h2>Application ${escHtml(appNum)}</h2>
      <div class="sub">Jurisdiction: ${escHtml(jurisdiction)} &nbsp;·&nbsp; Source: TIP Patent Lookup API</div>
    </div>

    <!-- Field cards grid -->
    <div class="result-grid">
      ${fieldCard('Attorney Name',    attorney)}
      ${fieldCard('Law Firm',         lawFirm)}
      ${fieldCard('Assignee',         assignee)}
      ${fieldCard('Examiner',         examiner)}
      ${fieldCard('Filing Date',      filingDate)}
      ${fieldCard('Disposal Status',  disposal)}
    </div>
  `;

  // Update diagnostics with real output values
  diagUpdate({
    output: {
      'data.application_number':          appNum,
      'data.jurisdiction':                jurisdiction,
      'data.application.attorneys[0].full_name': attorney  ?? '(not present)',
      'data.application.attorneys[0].law_firm_name': lawFirm ?? '(not present)',
      'data.application.assignees[0].name': assignee ?? '(not present)',
      'data.application.examiners[0].full_name': examiner ?? '(not present)',
      'data.application.filing_date':     filingDate ?? '(not present)',
      'data.application.app_status':      disposal   ?? '(not present)',
      'data.quota':                       quota,
    }
  });
}

function fieldCard(label, value) {
  const isEmpty = value === null || value === undefined;
  return `
    <div class="field-card">
      <div class="field-label">${escHtml(label)}</div>
      <div class="field-value${isEmpty ? ' em-dash' : ''}">${isEmpty ? '—' : escHtml(value)}</div>
    </div>`;
}

function renderError(msg) {
  document.getElementById('results').innerHTML = `
    <div class="tip-card" style="border-left:4px solid var(--tip-error,#dc2626);padding:1.2rem 1.5rem;">
      <div style="font-weight:700;color:var(--tip-error,#dc2626);margin-bottom:.4rem;">
        ⚠ API Error
      </div>
      <div style="color:var(--tip-text,#111827);font-size:.95rem;">${escHtml(msg)}</div>
    </div>`;
}

function clearResults() {
  document.getElementById('results').innerHTML = '';
}

function hidePlaceholder() {
  const p = document.getElementById('placeholder');
  if (p) p.remove();
}

/* =========================================================
   Utility
   ========================================================= */
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
</script>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html")

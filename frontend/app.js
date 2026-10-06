const API_BASE = window.location.hostname.includes('vercel.app') ? 'https://mris-maritime-regulatory-intelligence.onrender.com' : '';
/* ============================================================
   MRIS — Premium UI application (vanilla JS SPA, zero deps)
   Live API first; falls back to demo_data.json (real engine output
   baked at build time) so the UI renders on static hosting too.
   ============================================================ */
"use strict";

const App = {
  view: "overview",
  params: {},
  offline: false,
  data: {},          // shared payloads
};

/* ------------------------------------------------------------
   API layer
   ------------------------------------------------------------ */
const API = {
  getToken() { return localStorage.getItem("mris_token"); },
  setToken(t) { localStorage.setItem("mris_token", t); },
  logout() { localStorage.removeItem("mris_token"); location.reload(); },
  async get(path) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3500);
      const r = await fetch(API_BASE + path, { signal: ctrl.signal, headers: { "Authorization":  } });
      clearTimeout(t);
      if (!r.ok) throw new Error(r.status);
      return await r.json();
    } catch (e) {
      App.offline = true;
      return null;
    }
  },
  async post(path, body) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 4500);
      const r = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization":  },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      clearTimeout(t);
      const data = await r.json().catch(() => ({}));
      if (!r.ok) return { __error: data.detail || `HTTP ${r.status}` };
      return data;
    } catch (e) {
      App.offline = true;
      return null;
    }
  },
  async boot() {
    // Try live API; otherwise load baked engine output.
    const health = await this.get("/health");
    if (health) {
      App.data.fleet = await this.get("/v1/fleet/summary");
      App.data.instruments = await this.get("/v1/legal/instruments");
      App.data.impacts = await this.get("/v1/changes/impacts");
    } else {
      const r = await fetch("demo_data.json");
      if (r.ok) App.data = await r.json();
    }
    if (!App.data.fleet) {
      App.data.fleet = { fleet_status_counts: {}, vessels: [], as_of_date: "—" };
      App.data.instruments = { bangladesh: [], international: [] };
      App.data.impacts = { open_verification_items: [], sla: "" };
    }
  },
};

/* ------------------------------------------------------------
   Helpers
   ------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function statusBadge(status) {
  return `<span class="badge ${status}"><span class="dot"></span>${status}</span>`;
}

function offlineNote() {
  return App.offline
    ? `<div class="offline-note">◐ static preview — engine output baked at build time</div>`
    : "";
}

function donut(counts, size = 128) {
  const colors = { GREEN: "#34d399", YELLOW: "#fbbf24", RED: "#f87171", BLACK: "#94a3b8" };
  const total = Math.max(1, Object.values(counts).reduce((a, b) => a + b, 0));
  const r = size / 2 - 12, c = 2 * Math.PI * r;
  let offset = 0;
  const arcs = Object.entries(counts).map(([k, v]) => {
    const frac = v / total;
    const arc = `<circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
      stroke="${colors[k]}" stroke-width="13" stroke-linecap="round"
      stroke-dasharray="${(frac * c).toFixed(2)} ${c.toFixed(2)}"
      stroke-dashoffset="${(-offset * c).toFixed(2)}"><title>${k}: ${v}</title></circle>`;
    offset += frac;
    return arc;
  }).join("");
  return `<div class="donut-wrap">
    <div style="position:relative;width:${size}px;height:${size}px">
      <svg width="${size}" height="${size}" style="transform:rotate(-90deg)">${arcs}</svg>
      <div style="position:absolute;inset:0;display:grid;place-items:center;text-align:center">
        <div><div style="font-size:22px;font-weight:800">${total}</div>
        <div style="font-size:9px;letter-spacing:1.2px;color:var(--text-2)">ASSESSMENTS</div></div>
      </div>
    </div>
    <div class="donut-legend">
      ${Object.entries(counts).map(([k, v]) => `
        <div class="legend-row"><span class="sw" style="background:${colors[k]}"></span>
        ${k} <b>${v}</b></div>`).join("")}
    </div>
  </div>`;
}

function ring(status, size = 92) {
  const colors = { GREEN: "#34d399", YELLOW: "#fbbf24", RED: "#f87171", BLACK: "#94a3b8" };
  const r = size / 2 - 9, c = 2 * Math.PI * r;
  return `<div class="ring-wrap" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
        stroke="rgba(255,255,255,0.08)" stroke-width="9"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none"
        stroke="${colors[status]}" stroke-width="9" stroke-linecap="round"
        stroke-dasharray="${(0.82 * c).toFixed(1)} ${c.toFixed(1)}"/>
    </svg>
    <div class="ring-center" style="color:${colors[status]}">${status}</div>
  </div>`;
}

const DSL_KW = /\b(AND|OR|NOT|EXISTS|FORALL|ANY|NONE|IN|MATCHES|TRUE|FALSE|UNKNOWN)\b/g;
const DSL_FN = /\b([a-z_][a-z0-9_]*)\s*\(/g;

function highlightDsl(text) {
  let out = esc(text);
  out = out.replace(/(#.*)$/gm, '<span class="comment">$1</span>');
  out = out.replace(/(&quot;[^&]*?&quot;|"[^"]*?")/g, '<span class="str">$1</span>');
  out = out.replace(DSL_KW, '<span class="kw">$1</span>');
  out = out.replace(/([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)(?=\s*(?:[)=&lt;&gt;!]|$))/gi,
    '<span class="field">$1</span>');
  out = out.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="num">$1</span>');
  return out;
}

function highlightYaml(text) {
  let out = esc(text);
  out = out.replace(/(#.*)$/gm, '<span class="comment">$1</span>');
  out = out.replace(/^(\s*)([a-z_][a-z0-9_]*):/gim, '$1<span class="field">$2</span>:');
  out = out.replace(/(&quot;[^&]*?&quot;)/g, '<span class="str">$1</span>');
  out = out.replace(DSL_KW, '<span class="kw">$1</span>');
  return out;
}

/* ------------------------------------------------------------
   Views
   ------------------------------------------------------------ */
function viewOverview() {
  const fleet = App.data.fleet || {};
  const vessels = fleet.vessels || [];
  const counts = fleet.fleet_status_counts || {};
  const impacts = (App.data.impacts || {}).open_verification_items || [];
  const bd = (App.data.instruments || {}).bangladesh || [];
  const intl = (App.data.instruments || {}).international || [];
  const health = vessels.length
    ? Math.round(100 * ((counts.GREEN || 0) * 1 + (counts.YELLOW || 0) * 0.6) / vessels.length)
    : 0;

  return `
    <div class="banner">
      <div class="b-icon">⚓</div>
      <div><strong>Deterministic maritime compliance.</strong>
      Every result is a function of exact law version × rule version × facts —
      conflicts, missing data and unverified sources fail closed to BLACK, never a guess.
      ${offlineNote()}</div>
    </div>

    <div class="grid grid-4">
      <div class="card kpi">
        <div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 13l1.5-6h11L19 13M3 17c1.5 1.5 3 2 4.5 2s3-.5 4.5-2 3-2 4.5-2 3 .5 4.5 2"/></svg></div>
        <div class="kpi-label">Fleet under assessment</div>
        <div class="kpi-value grad">${vessels.length}</div>
        <div class="kpi-foot">BD-flagged · demo fleet · ${esc(fleet.as_of_date || "")}</div>
      </div>
      <div class="card kpi">
        <div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/></svg></div>
        <div class="kpi-label">Compliance health</div>
        <div class="kpi-value">${health}<span style="font-size:16px;color:var(--text-2)">%</span></div>
        <div class="kpi-foot">${counts.GREEN || 0} green · ${counts.YELLOW || 0} yellow · ${counts.RED || 0} red</div>
      </div>
      <div class="card kpi">
        <div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 5a2 2 0 012-2h5v18H6a2 2 0 01-2-2V5zM20 5a2 2 0 00-2-2h-5v18h5a2 2 0 002-2V5z"/></svg></div>
        <div class="kpi-label">Legal corpus</div>
        <div class="kpi-value">${bd.length + intl.length}</div>
        <div class="kpi-foot">${bd.length} Bangladesh · ${intl.length} international</div>
      </div>
      <div class="card kpi">
        <div class="kpi-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8v5l3 2"/><circle cx="12" cy="12" r="9"/></svg></div>
        <div class="kpi-label">Open verification items</div>
        <div class="kpi-value" style="color:var(--yellow)">${impacts.length}</div>
        <div class="kpi-foot">⚠ VERIFY gates — fail-closed until closed</div>
      </div>
    </div>

    <div class="section-head">
      <div class="section-title">Fleet status</div>
      <div class="section-sub">computed by ILRMF-DSL rules over live evidence records</div>
    </div>
    <div class="grid grid-3">
      ${vessels.map(vesselCard).join("") || emptyState("No vessels in demo store")}
    </div>

    <div class="grid grid-2 mt-2">
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Status distribution</div>
          <div class="muted">binding items only</div></div>
        ${donut(counts)}
      </div>
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Verification gates</div>
          <div class="muted">Part 16 open-items register</div></div>
        ${impacts.slice(0, 5).map(i => `
          <div class="hbar-row">
            <div class="hbar-label" title="${esc(i.item)}">${esc(i.item)}</div>
            <div class="hbar-track"><div class="hbar-fill" style="width:38%;background:linear-gradient(90deg,#fbbf24,#f59e0b)"></div></div>
            <div class="hbar-val">${esc(i.verify_against || "")}</div>
          </div>`).join("")}
        <div class="muted mt-1">All marked EXTRACTED_BY_AI → REVIEWED → VERIFIED_AGAINST_GAZETTE before rules go ACTIVE.</div>
      </div>
    </div>`;
}

function vesselCard(v) {
  const counts = v.counts || {};
  const total = Math.max(1, Object.values(counts).reduce((a, b) => a + b, 0));
  const seg = (k, color) => counts[k]
    ? `<i style="width:${(counts[k] / total) * 100}%;background:${color}"></i>` : "";
  return `
    <div class="card vessel-card" onclick="App.go('#/vessel/${esc(v.imo_number)}')">
      <div class="v-head">
        <div>
          <div class="v-name">${esc(v.name)}</div>
          <div class="v-imo">IMO ${esc(v.imo_number)}</div>
        </div>
        ${statusBadge(v.status)}
      </div>
      <div class="v-meta">
        <span class="chip">${esc(v.flag)}</span>
        <span class="chip">${esc(v.ship_type)}</span>
        <span class="chip">GT ${Number(v.gross_tonnage).toLocaleString()}</span>
        <span class="chip">${esc(v.class_society || "")}</span>
      </div>
      <div class="v-bar-row">
        <div class="v-bar">
          ${seg("GREEN", "#34d399")}${seg("YELLOW", "#fbbf24")}${seg("RED", "#f87171")}${seg("BLACK", "#94a3b8")}
        </div>
        <span class="mono">${Object.values(counts).reduce((a, b) => a + b, 0)} rules</span>
      </div>
    </div>`;
}

function emptyState(msg, icon = "🌊") {
  return `<div class="empty"><div class="big">${icon}</div>${esc(msg)}</div>`;
}

/* ---------------- fleet ---------------- */
function viewFleet() {
  const vessels = (App.data.fleet || {}).vessels || [];
  return `
    <div class="section-head">
      <div class="section-title">Fleet compliance</div>
      <div class="section-sub">click a vessel for the full result contract · ${offlineNote()}</div>
    </div>
    <div class="grid grid-3">
      ${vessels.map(vesselCard).join("") || emptyState("No vessels")}
    </div>
    <div class="card mt-2">
      <div class="section-title mb-1">Status legend</div>
      <div class="flex" style="flex-wrap:wrap;gap:16px">
        ${statusBadge("GREEN")}<span class="muted">all applicable obligations satisfied</span>
        ${statusBadge("YELLOW")}<span class="muted">expiring / advisory — scheduled action</span>
        ${statusBadge("RED")}<span class="muted">hard requirement failed — act before operation</span>
        ${statusBadge("BLACK")}<span class="muted">conflict / missing data — human review, never a guess</span>
      </div>
    </div>`;
}

/* ---------------- vessel detail ---------------- */
async function viewVessel(imo) {
  const holder = $("#content");
  holder.innerHTML = `<div class="loading"><div class="spinner"></div><span>Running deterministic rules…</span></div>`;

  let data = App.data.compliance && App.data.compliance[imo];
  if (!data) {
    data = await API.get(`/v1/vessels/${imo}/compliance`);
    if (data) {
      App.data.compliance = App.data.compliance || {};
      App.data.compliance[imo] = data;
    }
  }
  if (!data) {
    holder.innerHTML = emptyState(`No assessment for IMO ${imo}`, "🛟");
    return;
  }

  const v = ((App.data.fleet || {}).vessels || []).find(x => x.imo_number === imo) || {};
  const items = data.items || [];

  holder.innerHTML = `
    <a class="back-link" onclick="App.go('#/fleet')">← back to fleet</a>
    <div class="detail-head">
      ${ring(data.overall_status)}
      <div>
        <div style="font-size:21px;font-weight:800;letter-spacing:-0.4px">${esc(v.name || data.entity_id)}</div>
        <div class="v-imo">IMO ${esc(imo)} · flag ${esc(v.flag || "")} · ${esc(v.ship_type || "")}</div>
        <div class="detail-meta">
          <div class="meta-block"><div class="meta-k">As of</div><div class="meta-v">${esc(data.as_of_date)}</div></div>
          <div class="meta-block"><div class="meta-k">Gross tonnage</div><div class="meta-v">${Number(v.gross_tonnage || 0).toLocaleString()}</div></div>
          <div class="meta-block"><div class="meta-k">Built</div><div class="meta-v">${esc(v.build_date || "—")}</div></div>
          <div class="meta-block"><div class="meta-k">Class</div><div class="meta-v">${esc(v.class_society || "—")}</div></div>
          <div class="meta-block"><div class="meta-k">Legal review queue</div>
            <div class="meta-v">${(data.lawyer_review_queue || []).length} item(s)</div></div>
        </div>
      </div>
    </div>

    <div class="section-head">
      <div class="section-title">Obligations &amp; result contract</div>
      <div class="section-sub">expand a row for the full Part-Z contract · ${offlineNote()}</div>
    </div>
    ${items.map((item, idx) => itemRow(item, idx, imo)).join("")}

    <div class="card mt-2">
      <div class="section-title mb-1">Version snapshot (Principle 8)</div>
      <div class="muted mb-1">result = f(law_version, rule_version, facts) — recorded so the past reproduces exactly.</div>
      <div class="flex" style="flex-wrap:wrap">
        ${Object.entries(data.law_versions_used || {}).map(([k, val]) =>
          `<span class="tag info">${esc(k)} → ${esc(val)}</span>`).join("")}
        ${Object.entries(data.rule_versions_used || {}).map(([k, val]) =>
          `<span class="tag ok">${esc(k)} ${esc(val)}</span>`).join("")}
      </div>
    </div>`;
}

function itemRow(item, idx, imo) {
  const c = item.contract || {};
  return `
    <div class="item-row" id="item-${idx}">
      <div class="item-summary" onclick="document.getElementById('item-${idx}').classList.toggle('open')">
        ${statusBadge(item.status)}
        <div class="grow">
          <div class="rule-id">${esc(item.provision_id)} · ${esc(item.layer)}</div>
          <div class="req">${esc(c.requirement || item.reason)}</div>
        </div>
        ${item.advisory ? '<span class="tag warn">ADVISORY</span>' : ""}
        ${c.lawyer_review_needed ? '<span class="tag warn">⚖ REVIEW</span>' : ""}
        <svg class="chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </div>
      <div class="item-body">
        <div class="contract-grid">
          <div class="contract-cell"><div class="c-k">Requirement</div><div class="c-v">${esc(c.requirement)}</div></div>
          <div class="contract-cell"><div class="c-k">Why applicable</div><div class="c-v">${esc(c.why_applicable)}</div></div>
          <div class="contract-cell"><div class="c-k">Source law</div><div class="c-v">${esc(c.source_law)}</div></div>
          <div class="contract-cell"><div class="c-k">Legal version</div><div class="c-v mono">${esc(c.legal_version)}</div></div>
          <div class="contract-cell"><div class="c-k">In force on date</div><div class="c-v">${c.in_force_on_date === true ? "✅ yes" : c.in_force_on_date === false ? "❌ no" : "UNKNOWN"}</div></div>
          <div class="contract-cell"><div class="c-k">Amended</div><div class="c-v">${c.amended === true ? "yes" : c.amended === false ? "no" : "—"}</div></div>
          <div class="contract-cell"><div class="c-k">Evidence required</div><div class="c-v">${(c.evidence || []).map(e => `<span class="tag">${esc(e)}</span>`).join("")}</div></div>
          <div class="contract-cell"><div class="c-k">Rule executed</div><div class="c-v mono">${esc(c.rule_executed)}</div></div>
          <div class="contract-cell full"><div class="c-k">Reasoning chain</div><div class="c-v">${esc(item.reason)}</div></div>
          ${c.missing && c.missing.length ? `
          <div class="contract-cell full"><div class="c-k">What's missing</div>
            <div class="c-v">${c.missing.map(m => `<span class="tag warn">${esc(m)}</span>`).join("")}</div></div>` : ""}
          <div class="contract-cell"><div class="c-k">Required action</div><div class="c-v">${esc(c.required_action || "none")}</div></div>
          <div class="contract-cell"><div class="c-k">Consequence of non-correction</div><div class="c-v">${esc(c.consequence || "")}</div></div>
        </div>
        <div class="flex mt-2">
          <button class="btn" onclick="App.showProvenance('${esc(imo)}', '${esc(item.obligation_id)}')">
            ◈ Show provenance chain</button>
          ${c.lawyer_review_needed ? `<span class="tag warn">48 h legal-review SLA</span>` : ""}
        </div>
      </div>
    </div>`;
}

/* ---------------- rule engine ---------------- */
async function viewRules() {
  const holder = $("#content");
  if (!App.data.rules || !Object.keys(App.data.rules).length) {
    App.data.rules = (await API.get("/v1/rules")) || App.data.rules || {};
  }
  const rules = App.data.rules || {};
  const ruleIds = Object.keys(rules);

  const sampleFacts = JSON.stringify({
    evidence: [{ evidence_type: "SAFE_MANNING_DOCUMENT", entity_id: "v-demo-001", verification_status: "VERIFIED" }],
    current_crew: [{ id: "sf-001", rank: "MASTER", certificates: [{ type: "COC", issue_date: "2024-01-01", expiry_date: "2028-01-01", verification_status: "VERIFIED" }] }],
  }, null, 2);

  holder.innerHTML = `
    <div class="banner">
      <div class="b-icon">⚙</div>
      <div><strong>ILRMF-DSL — deterministic, total, three-valued.</strong>
      Every expression yields TRUE / FALSE / UNKNOWN on every input. A MANDATORY rule
      evaluating UNKNOWN fails closed to BLACK. Ill-typed rules are rejected and can
      never reach ACTIVE. ${offlineNote()}</div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <div class="spread mb-1">
          <div class="section-title">Executable rule specs</div>
          <div class="muted">YAML surface → JSONB AST</div>
        </div>
        ${ruleIds.length ? ruleIds.map((id, i) => `
          <div class="item-row" style="margin-bottom:10px">
            <div class="item-summary" onclick="this.parentElement.classList.toggle('open')">
              <span class="tag info mono" style="font-size:9.5px">${esc(id)}</span>
              <div class="grow"></div>
              <svg class="chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            </div>
            <div class="item-body"><div class="code">${highlightYaml(rules[id])}</div></div>
          </div>`).join("") : `<div class="empty"><div class="big">📜</div>Rule specs load from the live backend or demo_data.json</div>`}
      </div>

      <div class="card">
        <div class="section-title mb-1">Live evaluation console</div>
        <div class="muted mb-1">POST /v1/rule/evaluate — sandboxed, step-budgeted, fail-closed.</div>
        <label class="field-label">Rule spec (YAML)</label>
        <textarea class="input" id="ruleYaml">rule_id: PLAYGROUND-R001
rule_version: 1
domain: MANNING
legal_source: {provision_id: P1, legal_version_id: LV1}
applicability:
  all: [{flag: [BD]}]
condition:
  type: MANDATORY
  expression: 'FORALL m IN current_crew : m.coc_valid(at: eval_date)'
outcome: {compliant_if: "condition true"}
evidence_required: [COC_PER_CREW_MEMBER]
status_ladder: {}</textarea>
        <label class="field-label">Facts (JSON)</label>
        <textarea class="input" id="ruleFacts">${esc(sampleFacts)}</textarea>
        <label class="field-label">Applicability facts</label>
        <input class="input" id="ruleApp" value='{"flag": "BD"}'>
        <div class="flex mt-2">
          <button class="btn primary" onclick="App.runRule()">▶ Evaluate rule</button>
          <span class="muted">UNKNOWN ⇒ BLACK · TRUE ⇒ GREEN · FALSE ⇒ RED</span>
        </div>
        <div id="ruleOut" class="mt-2"></div>
      </div>
    </div>`;
}

App.runRule = async function () {
  const out = $("#ruleOut");
  out.innerHTML = `<div class="loading" style="padding:18px 0"><div class="spinner"></div><span>Evaluating…</span></div>`;
  let payload = {
    rule_yaml: $("#ruleYaml").value,
    facts: JSON.parse($("#ruleFacts").value || "{}"),
    applicability_facts: JSON.parse($("#ruleApp").value || "{}"),
  };
  const res = await API.post("/v1/rule/evaluate", payload);
  if (!res) {
    out.innerHTML = `<div class="banner"><div class="b-icon">◐</div><div>
      <strong>Live engine unavailable</strong> in this static preview.
      Run <span class="mono">uvicorn mris.api:app</span> locally (or deploy the
      backend to Vercel) to evaluate rules interactively.</div></div>`;
    return;
  }
  if (res.__error) {
    out.innerHTML = `<div class="banner" style="background:var(--red-bg);border-color:rgba(248,113,113,0.3)">
      <div class="b-icon" style="color:var(--red)">⛔</div><div><strong>Rule rejected (never reaches ACTIVE):</strong>
      ${esc(res.__error)}</div></div>`;
    return;
  }
  out.innerHTML = `
    <div class="contract-grid">
      <div class="contract-cell"><div class="c-k">Status</div><div class="c-v">${statusBadge(res.status)}</div></div>
      <div class="contract-cell"><div class="c-k">Condition</div><div class="c-v mono">${esc(res.condition)}</div></div>
      <div class="contract-cell"><div class="c-k">Applicability</div><div class="c-v mono">${esc(res.applicability)}</div></div>
      <div class="contract-cell"><div class="c-k">Lawyer review</div><div class="c-v">${res.lawyer_review_needed ? "⚖ required" : "not required"}</div></div>
      <div class="contract-cell full"><div class="c-k">Reasoning chain</div><div class="c-v">${esc(res.reason)}</div></div>
      ${(res.unknown_reasons || []).length ? `
      <div class="contract-cell full"><div class="c-k">Unknowns (fail-closed)</div>
        <div class="c-v">${res.unknown_reasons.map(u => `<span class="tag warn">${esc(u)}</span>`).join("")}</div></div>` : ""}
    </div>`;
};

/* ---------------- voyage preview ---------------- */
function viewVoyage() {
  return `
    <div class="banner">
      <div class="b-icon">🌐</div>
      <div><strong>Layer-Combining Algorithm LCA-1.</strong>
      Legs × jurisdiction segments → candidates per layer (L1 treaty, L2 flag, L3 coastal,
      L4 port, L5 class, L6 contractual) → STRICTER merge or CONFLICT ⇒ BLACK with both
      provisions cited, routed to legal review (48 h SLA). ${offlineNote()}</div>
    </div>
    <div class="grid grid-2">
      <div class="card">
        <div class="section-title mb-1">Voyage parameters</div>
        <label class="field-label">Vessel flag</label>
        <input class="input" id="vyFlag" value="BD">
        <label class="field-label">Domestic vessel (full L4 applies; foreign flag = PSC entry conditions only)</label>
        <select class="input" id="vyDomestic">
          <option value="true">domestic — L4 binding in full</option>
          <option value="false">foreign flag — PSC asymmetry</option>
        </select>
        <label class="field-label">Legs (JSON)</label>
        <textarea class="input" id="vyLegs" style="min-height:150px">[
  {"seq": 1, "zone_type": "INTERNAL_WATERS", "coastal_state": "BD"},
  {"seq": 2, "zone_type": "TERRITORIAL", "coastal_state": "BD", "port": "CHITTAGONG"}
]</textarea>
        <div class="flex mt-2">
          <button class="btn primary" onclick="App.runVoyage()">▶ Resolve obligations</button>
          <span class="muted">worst status across legs · per-leg drill-down</span>
        </div>
        <div id="vyOut" class="mt-2"></div>
      </div>
      <div class="card">
        <div class="section-title mb-1">Precedence hierarchy</div>
        ${[
          ["L1", "International treaty obligations (as in force FOR THE FLAG)", "binding", "#22d3ee"],
          ["L2", "Flag-State legislation & regulations", "binding", "#3b82f6"],
          ["L3", "Coastal-State legislation (EEZ, approaches, cabotage)", "binding in zone", "#6366f1"],
          ["L4", "Port-State law + port authority rules", "binding in port", "#8b5cf6"],
          ["L5", "Class statutory requirements (delegated)", "binding via delegation", "#a78bfa"],
          ["L6", "Contractual / commercial (SIRE, OCIMF, charter)", "advisory only", "#f59e0b"],
        ].map(([code, desc, force, color]) => `
          <div class="hbar-row">
            <div class="hbar-label" style="width:44px;font-weight:800;color:${color}">${code}</div>
            <div style="flex:1;font-size:12px;color:var(--text-1)">${desc}</div>
            <div class="hbar-val" style="width:118px">${force}</div>
          </div>`).join("")}
        <div class="banner mt-2" style="margin-bottom:0">
          <div class="b-icon">⚖</div>
          <div>Advisory (L6) items can <strong>never weaken</strong> a statutory GREEN.
          Compatible obligations merge to the stricter bound: MIN(5) ∧ MIN(8) ⇒ MIN(8).
          Incompatible hard obligations ⇒ BLACK citing both provisions.</div>
        </div>
      </div>
    </div>`;
}

App.runVoyage = async function () {
  const out = $("#vyOut");
  out.innerHTML = `<div class="loading" style="padding:18px 0"><div class="spinner"></div><span>Resolving…</span></div>`;
  const body = {
    vessel_flag: $("#vyFlag").value,
    domestic: $("#vyDomestic").value === "true",
    legs: JSON.parse($("#vyLegs").value || "[]"),
  };
  const res = await API.post("/v1/voyages/obligation-preview", body);
  if (!res) {
    out.innerHTML = `<div class="banner"><div class="b-icon">◐</div><div>
      <strong>Live engine unavailable</strong> in this static preview —
      the backend runs LCA-1 interactively.</div></div>`;
    return;
  }
  if (res.__error) { out.innerHTML = `<span class="offline-note">⛔ ${esc(res.__error)}</span>`; return; }
  const legs = Object.entries(res.drill_down || {});
  out.innerHTML = `
    <div class="flex mb-1">${statusBadge(res.overall_status)}
      <span class="muted">algorithm ${esc(res.algorithm)} · review SLA ${res.legal_review_sla_hours} h</span></div>
    ${(res.conflict_items || []).map(ci => `
      <div class="banner" style="background:var(--red-bg);border-color:rgba(248,113,113,0.3)">
        <div class="b-icon" style="color:var(--red)">⚡</div>
        <div><strong>CONFLICT — ${esc(ci.dimension)}</strong> on leg ${ci.leg_seq} (${esc(ci.zone_type)})<br>
        ${esc(ci.left.layer)} ${esc(ci.left.rule_id)}: ${esc(ci.left.requirement)}<br>
        ${esc(ci.right.layer)} ${esc(ci.right.rule_id)}: ${esc(ci.right.requirement)}<br>
        <em>${esc(ci.action)}</em></div>
      </div>`).join("")}
    ${legs.map(([seq, leg]) => `
      <div class="item-row open" style="margin-top:10px">
        <div class="item-summary">
          ${statusBadge(leg.status)}
          <div class="grow"><div class="rule-id">leg ${esc(seq)} · ${esc(leg.zone_type)}</div></div>
        </div>
        <div class="item-body">
          ${Object.entries(leg.dimensions || {}).map(([dim, d]) => `
            <div class="spread" style="padding:7px 0;border-bottom:1px solid rgba(148,197,253,0.07)">
              <div><span class="mono" style="font-size:11.5px">${esc(dim)}</span>
                <div class="muted" style="font-size:11px">${esc(d.merged_requirement || "")}</div></div>
              <div class="flex">
                ${d.conflict ? '<span class="tag warn">CONFLICT</span>' : ""}
                ${statusBadge(d.status)}
              </div>
            </div>`).join("")}
        </div>
      </div>`).join("")}`;
};

/* ---------------- operations & risk (P4/P5) ---------------- */
async function viewOperations() {
  const holder = $("#content");
  if (!App.data.ops) {
    App.data.ops = {
      incidents: (await API.get("/v1/incidents")) || null,
      cyber: (await API.get("/v1/cyber")) || null,
      yard: (await API.get("/v1/yard/readiness")) || null,
    };
    const vessels = (App.data.fleet || {}).vessels || [];
    App.data.ops.liability = [];
    for (const v of vessels) {
      const r = await API.get(`/v1/liability/${v.imo_number}`);
      if (r) App.data.ops.liability.push({ name: v.name, imo: v.imo_number, ...r });
    }
  }
  const ops = App.data.ops;
  const incidents = (ops.incidents?.incidents || []);
  const overdue = (ops.incidents?.overdue || []);

  const notifRow = (n) => `
    <div class="spread" style="padding:8px 2px;border-bottom:1px solid rgba(148,197,253,0.07)">
      <div class="grow">
        <div style="font-size:12px;font-weight:650">${esc(n.authority_id)} · ${esc(n.basis)}</div>
        <div class="mono" style="font-size:9.5px;color:var(--text-2)">${esc(n.requirement_provision_id)}</div>
      </div>
      <div class="muted mono" style="font-size:10.5px">${n.status === "OVERDUE" ? "⛔" : "⏱"} ${n.hours_remaining > 0 ? n.hours_remaining.toFixed(1) + "h left" : Math.abs(n.hours_remaining).toFixed(1) + "h overdue"}</div>
      ${statusBadge(n.status === "OVERDUE" ? "RED" : n.status === "SENT" ? "GREEN" : "YELLOW")}
    </div>`;

  holder.innerHTML = `
    <div class="banner">
      <div class="b-icon">🛡</div>
      <div><strong>Commercial depth — incidents, liability, cyber, yard.</strong>
      Incident notifications carry deterministic regulatory deadlines; liability flags are
      <b>advisory only</b> and never downgrade statutory status (Principle 15); cyber posture
      follows IMO MSC.428(98) + MSC-FAL.1/Circ.3; yard permits are hard gates. ${offlineNote()}</div>
    </div>

    <div class="grid grid-4">
      <div class="card kpi"><div class="kpi-label">Incidents tracked</div>
        <div class="kpi-value grad">${incidents.length}</div>
        <div class="kpi-foot">${overdue.length} overdue notification(s)</div></div>
      <div class="card kpi"><div class="kpi-label">Liability signals</div>
        <div class="kpi-value" style="color:var(--yellow)">${(ops.liability || []).reduce((a, r) => a + r.flags.filter(f => f.flag !== "INFO").length, 0)}</div>
        <div class="kpi-foot">advisory flags · WATCH + ELEVATED</div></div>
      <div class="card kpi"><div class="kpi-label">Cyber posture (worst)</div>
        <div class="kpi-value" style="color:var(--red)">${esc((ops.cyber?.postures || []).map(p => p.overall).sort((a, b) => ["GREEN","YELLOW","RED","BLACK"].indexOf(b) - ["GREEN","YELLOW","RED","BLACK"].indexOf(a))[0] || "—")}</div>
        <div class="kpi-foot">MSC.428 five-step model</div></div>
      <div class="card kpi"><div class="kpi-label">Yard permit risk</div>
        <div class="kpi-value" style="color:${ops.yard?.permits?.risk === "ELEVATED" ? "var(--red)" : "var(--green)"}">${esc(ops.yard?.permits?.risk || "—")}</div>
        <div class="kpi-foot">${(ops.yard?.permits?.expired_but_open || []).length} expired-but-open permit(s)</div></div>
    </div>

    <div class="section-head"><div class="section-title">Incidents &amp; regulatory notifications</div>
      <div class="section-sub">deadlines computed from incident type + occurrence time</div></div>
    <div class="grid grid-2">
      ${incidents.map(inc => `
        <div class="card">
          <div class="spread">
            <div><div class="mono" style="font-size:11px;color:var(--text-2)">${esc(inc.id)}</div>
              <div style="font-size:14.5px;font-weight:750">${esc(inc.incident_type)} · ${esc(inc.severity)}</div>
              <div class="muted" style="font-size:11px">${esc(inc.vessel_id || "")} · ${esc((inc.occurred_at || "").slice(0, 16))}Z · ${esc(inc.status)}</div></div>
            ${statusBadge(inc.compliance_posture)}
          </div>
          <div class="mt-1 muted" style="font-size:11.5px">${esc(inc.description)}</div>
          <div class="mt-1">${(inc.notifications || []).map(notifRow).join("") || '<div class="muted">no notifications required</div>'}</div>
          <div class="mt-1">${(inc.corrective_actions || []).map(ca => `
            <span class="tag info">CA: ${esc(ca.action)} · due ${esc(ca.due_date)}</span>`).join("")}</div>
        </div>`).join("") || emptyState("No incidents reported", "✅")}
    </div>

    <div class="section-head"><div class="section-title">Liability &amp; insurance — advisory flags</div>
      <div class="section-sub">never legal advice · never downgrades statutory compliance</div></div>
    <div class="grid grid-2">
      ${(ops.liability || []).map(rep => `
        <div class="card">
          <div class="spread"><div><div style="font-size:13.5px;font-weight:700">${esc(rep.name)}</div>
            <div class="v-imo">IMO ${esc(rep.imo)}</div></div>
            <span class="badge ${rep.risk_level === "ELEVATED" ? "RED" : rep.risk_level === "WATCH" ? "YELLOW" : "GREEN"}">
              <span class="dot"></span>${esc(rep.risk_level)}</span></div>
          <div class="mt-1">${(rep.policies || []).map(p => `
            <div class="spread" style="padding:6px 0;border-bottom:1px solid rgba(148,197,253,0.07)">
              <div><b style="font-size:11.5px">${esc(p.policy_type)}</b> <span class="muted">${esc(p.insurer)}</span></div>
              <div class="flex"><span class="mono muted" style="font-size:10px">exp ${esc(p.expiry_date)}</span>
                ${statusBadge(p.status === "EXPIRED" ? "RED" : p.status === "EXPIRING" ? "YELLOW" : "GREEN")}</div>
            </div>`).join("")}</div>
          <div class="mt-1">${(rep.flags || []).map(f => `
            <div class="tag ${f.flag === "ELEVATED" ? "warn" : f.flag === "WATCH" ? "warn" : "info"}">${esc(f.flag)} · ${esc(f.rationale)}</div>`).join("")}</div>
        </div>`).join("") || emptyState("No liability data", "⚖")}
    </div>

    <div class="grid grid-2 mt-2">
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Cyber posture — MSC.428</div>
          <div class="muted">identify · protect · detect · respond · recover</div></div>
        ${(ops.cyber?.postures || []).map(p => `
          <div class="spread" style="padding:8px 2px;border-bottom:1px solid rgba(148,197,253,0.07)">
            <div class="grow"><div style="font-size:12.5px;font-weight:650">${esc(p.name)}</div>
              <div class="muted" style="font-size:10px">${p.assessments.filter(a => a.status !== "GREEN").length} gap(s) across ${p.assessments.length} controls</div></div>
            ${statusBadge(p.overall)}
          </div>`).join("")}
        <div class="muted mt-1">${esc(ops.cyber?.national_note || "")}</div>
      </div>
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Shipyard — project &amp; permits</div>
          <div class="muted">hot-work / confined-space are hard gates</div></div>
        ${ops.yard ? `
          <div class="flex mb-1">${statusBadge(ops.yard.project.readiness.status)}
            <div class="muted" style="font-size:11px">${esc(ops.yard.project.project_name)} · hull ${esc(ops.yard.project.hull_no)} · ${esc(ops.yard.project.phase)}</div></div>
          <div class="muted" style="font-size:11.5px">${esc(ops.yard.project.readiness.reason)}</div>
          <div class="mt-1">${(ops.yard.project.design_approvals || []).map(a =>
            `<span class="tag ${a.status === "APPROVED" ? "ok" : "warn"}">${esc(a.plan_type)}: ${esc(a.status)}</span>`).join("")}</div>
          <div class="mt-1">${(ops.yard.permits.expired_but_open || []).map(p => `
            <div class="banner" style="background:var(--red-bg);border-color:rgba(248,113,113,0.3);margin:6px 0 0">
              <div class="b-icon" style="color:var(--red)">⛔</div><div><strong>${esc(p.permit_type)} ${esc(p.id)}</strong> — ${esc(p.rationale)}</div></div>`).join("")}
            ${(ops.yard.permits.active || []).map(id => `<span class="tag ok">ACTIVE ${esc(id)}</span>`).join("")}</div>
        ` : emptyState("No yard data", "🏗")}
      </div>
    </div>`;
}

/* ---------------- legal review console ---------------- */
async function viewReview() {
  const holder = $("#content");
  if (!App.data.review) {
    App.data.review = (await API.get("/v1/review/queue")) || null;
    App.data.audit = (await API.get("/v1/audit/trail")) || null;
    App.data.ingestion = (await API.get("/v1/ingestion/status")) || null;
  }
  const review = App.data.review || { items: [], pending: 0, gates: [] };
  const audit = App.data.audit || { entries: [], chain_valid: null };
  const ingestion = App.data.ingestion || { sources: [], stages: [] };

  const tierTag = (tier) => {
    const cls = tier === "VERIFIED_AGAINST_GAZETTE" ? "ok"
      : tier === "REVIEWED" ? "info" : "warn";
    const icon = tier === "VERIFIED_AGAINST_GAZETTE" ? "✓" : tier === "REVIEWED" ? "👁" : "⚠";
    return `<span class="tag ${cls}">${icon} ${esc(tier)}</span>`;
  };

  holder.innerHTML = `
    <div class="banner">
      <div class="b-icon">⚖</div>
      <div><strong>Human gate — AI extracts, lawyers publish.</strong>
      EXTRACTED_BY_AI → REVIEWED → VERIFIED_AGAINST_GAZETTE. Two-person rule: the
      verifier must differ from the reviewer. Only VERIFIED provisions feed live
      compliance calculations (fail-closed). ${offlineNote()}</div>
    </div>

    <div class="grid grid-3">
      <div class="card kpi">
        <div class="kpi-label">Pending in queue</div>
        <div class="kpi-value" style="color:var(--yellow)">${review.pending ?? 0}</div>
        <div class="kpi-foot">awaiting review or verification</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Audit chain</div>
        <div class="kpi-value" style="color:${audit.chain_valid === false ? 'var(--red)' : 'var(--green)'}">
          ${audit.chain_valid === null ? "—" : audit.chain_valid ? "INTACT" : "BROKEN"}</div>
        <div class="kpi-foot">${(audit.entries || []).length} hash-chained entries</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label">Monitored sources</div>
        <div class="kpi-value grad">${(ingestion.sources || []).length}</div>
        <div class="kpi-foot">sha256 delta detection · 72 h alert SLA</div>
      </div>
    </div>

    <div class="section-head">
      <div class="section-title">Verification queue</div>
      <div class="section-sub">review → verify (two-person) → feeds compliance</div>
    </div>
    <div class="card" style="padding:8px 4px">
      ${(review.items || []).map(item => `
        <div class="item-row" id="rq-${esc(item.id)}" style="margin:8px 12px">
          <div class="item-summary" onclick="this.parentElement.classList.toggle('open')">
            ${tierTag(item.tier)}
            <div class="grow">
              <div class="rule-id">${esc(item.object_id)}</div>
              <div class="req">${esc(item.title)}</div>
            </div>
            <span class="chip mono">conf ${Math.round((item.confidence ?? 1) * 100)}%</span>
            <svg class="chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </div>
          <div class="item-body">
            <div class="contract-grid">
              <div class="contract-cell full"><div class="c-k">Extracted text (provision-atomic)</div>
                <div class="c-v">${esc(item.extracted_text)}</div></div>
              <div class="contract-cell"><div class="c-k">Source</div>
                <div class="c-v mono">${esc(item.source_url || "—")}</div></div>
              <div class="contract-cell"><div class="c-k">Workflow</div>
                <div class="c-v">${item.reviewed_by ? `reviewed by <b>${esc(item.reviewed_by)}</b>` : "not yet reviewed"}
                ${item.verified_by ? ` · verified by <b>${esc(item.verified_by)}</b>` : ""}</div></div>
            </div>
            <div class="flex mt-2">
              ${item.tier === "EXTRACTED_BY_AI" ? `
                <button class="btn" onclick="App.reviewItem('${esc(item.id)}')">👁 Mark reviewed</button>` : ""}
              ${item.tier === "REVIEWED" ? `
                <button class="btn primary" onclick="App.verifyItem('${esc(item.id)}')">✓ Verify against Gazette</button>
                <span class="muted">verifier must differ from ${esc(item.reviewed_by || "reviewer")}</span>` : ""}
              ${item.tier === "VERIFIED_AGAINST_GAZETTE" ? `
                <span class="tag ok">✓ feeds live compliance</span>` : ""}
            </div>
            <div id="rq-msg-${esc(item.id)}" class="mt-1"></div>
          </div>
        </div>`).join("") || emptyState("Review queue empty", "✅")}
    </div>

    <div class="grid grid-2 mt-2">
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Audit trail</div>
          <div class="muted">append-only · hash-chained · tamper-evident</div></div>
        <div class="timeline">
          ${(audit.entries || []).slice(-8).reverse().map(e => `
            <div class="tl-item">
              <div class="tl-k">${esc(e.action)} · ${esc(e.object_id || "")}</div>
              <div class="tl-v">${esc(e.actor || "system")} · ${esc((e.at || "").slice(0, 19))}
                <div class="mono" style="font-size:9.5px;color:var(--text-2)">
                  ${esc((e.entry_hash || "").slice(0, 16))}… ← ${esc((e.prev_hash || "").slice(0, 8))}…</div>
              </div>
            </div>`).join("") || emptyState("No audit entries", "📜")}
        </div>
      </div>
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Ingestion pipeline</div>
          <div class="muted">Part 11 — publication → alert ≤ 72 h</div></div>
        ${(ingestion.sources || []).map(s => `
          <div class="spread" style="padding:9px 0;border-bottom:1px solid rgba(148,197,253,0.07)">
            <div><div style="font-size:12.5px;font-weight:650">${esc(s.publisher)}</div>
              <div class="mono" style="font-size:10px;color:var(--text-2)">${esc(s.url)}</div></div>
            <span class="tag info">${esc(s.source_type)}</span>
          </div>`).join("")}
        <div class="mt-2">
          <div class="c-k" style="font-size:9.5px;letter-spacing:1.1px;color:var(--text-2)">PIPELINE STAGES</div>
          <div class="mt-1">${(ingestion.stages || []).map((st, i) =>
            `<span class="tag ${i < 3 ? "info" : ""}">${i + 1}. ${esc(st)}</span>`).join("")}</div>
        </div>
        <div class="mt-2">
          <label class="field-label">Try provision-boundary detection (live backend)</label>
          <textarea class="input" id="ingestText" style="min-height:90px">Section 82. Manning of ships. Every ship registered in Bangladesh shall be manned in accordance with the safe manning document.
Section 83. Crew agreements. An agreement shall be made between the master and each member of the crew.</textarea>
          <div class="flex mt-1">
            <button class="btn" onclick="App.runIngest()">⚙ Ingest &amp; queue</button>
            <span class="muted">sha256 delta → classify → provision chunks → human queue</span>
          </div>
          <div id="ingestOut" class="mt-1"></div>
        </div>
      </div>
    </div>`;
}

App.reviewItem = async function (id) {
  const msg = document.getElementById(`rq-msg-${id}`);
  msg.innerHTML = `<div class="loading" style="padding:8px 0"><div class="spinner"></div></div>`;
  const res = await API.post(`/v1/review/queue/${id}/review`, { actor_id: "reviewer-1", notes: "reviewed via console" });
  if (!res) { msg.innerHTML = `<span class="offline-note">live backend required for workflow actions</span>`; return; }
  if (res.__error) { msg.innerHTML = `<span class="offline-note">⛔ ${esc(res.__error)}</span>`; return; }
  App.data.review = null;
  await viewReview();
};

App.verifyItem = async function (id) {
  const msg = document.getElementById(`rq-msg-${id}`);
  msg.innerHTML = `<div class="loading" style="padding:8px 0"><div class="spinner"></div></div>`;
  // two-person rule: reviewer-2 verifies what reviewer-1 reviewed
  const res = await API.post(`/v1/review/queue/${id}/verify`, { actor_id: "reviewer-2", source_url: "https://www.bdlaws.minlaw.gov.bd" });
  if (!res) { msg.innerHTML = `<span class="offline-note">live backend required for workflow actions</span>`; return; }
  if (res.__error) { msg.innerHTML = `<span class="offline-note">⛔ ${esc(res.__error)}</span>`; return; }
  App.data.review = null;
  await viewReview();
};

App.runIngest = async function () {
  const out = $("#ingestOut");
  out.innerHTML = `<div class="loading" style="padding:8px 0"><div class="spinner"></div></div>`;
  const res = await API.post("/v1/ingestion/ingest", {
    source_id: "bd-gazette", instrument_id: "BD-ORD-MERCHANT-SHIPPING-1983",
    content: document.getElementById("ingestText").value,
  });
  if (!res) {
    out.innerHTML = `<span class="offline-note">live backend required for ingestion</span>`;
    return;
  }
  if (res.__error) { out.innerHTML = `<span class="offline-note">⛔ ${esc(res.__error)}</span>`; return; }
  out.innerHTML = `
    <div class="contract-grid">
      <div class="contract-cell"><div class="c-k">Delta</div>
        <div class="c-v">${res.changed ? "🔄 content changed" : "= unchanged"}</div></div>
      <div class="contract-cell"><div class="c-k">Classification</div>
        <div class="c-v">${esc(res.classification || "—")}</div></div>
      <div class="contract-cell"><div class="c-k">Provision chunks</div>
        <div class="c-v">${res.provision_count}</div></div>
      <div class="contract-cell"><div class="c-k">sha256</div>
        <div class="c-v mono" style="font-size:9.5px">${esc((res.sha256 || "").slice(0, 24))}…</div></div>
      <div class="contract-cell full"><div class="c-k">Notes</div><div class="c-v">${esc(res.notes || "")}</div></div>
    </div>`;
};

/* ---------------- corpus ---------------- */
function viewCorpus() {
  const bd = (App.data.instruments || {}).bangladesh || [];
  const intl = (App.data.instruments || {}).international || [];
  return `
    <div class="banner">
      <div class="b-icon">📚</div>
      <div><strong>Instrument immutability + provision-level traceability.</strong>
      Every instrument carries verification status; drafts are quarantined, repealed law is
      never deleted, future law is stored inactive. ${offlineNote()}</div>
    </div>
    <div class="card mb-2">
      <div class="spread mb-1"><div class="section-title">Treaty status — flag BD</div>
        <div class="muted">"in force FOR THE FLAG on date D" · Part 6.5 · future amendments never applied early</div></div>
      ${(App.data.treaty?.rows || []).map(r => `
        <div class="spread" style="padding:9px 2px;border-bottom:1px solid rgba(148,197,253,0.07)">
          <div class="grow">
            <div class="mono" style="font-size:11.5px">${esc(r.amendment_id || r.instrument_id)}</div>
            <div class="muted" style="font-size:10.5px">
              ${r.entry_into_force_for_state ? `EIF for state: ${esc(r.entry_into_force_for_state)} (${esc(r.date_precision || "DAY")} precision)` : esc(r.note || "")}
            </div>
          </div>
          ${r.verification_status ? `<span class="tag warn">⚠ ${esc(r.verification_status)}</span>` : ""}
          ${r.in_force === true ? '<span class="tag ok">IN FORCE</span>'
            : r.in_force === false ? '<span class="tag">NOT YET / NOT BOUND</span>'
            : '<span class="tag warn">UNKNOWN</span>'}
        </div>`).join("") || emptyState("Treaty data loads from the live backend or demo_data.json", "🌐")}
    </div>
    <div class="grid grid-2">
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Bangladesh corpus</div>
          <div class="muted">${bd.length} instruments</div></div>
        ${bd.map(instRow).join("") || emptyState("No instruments")}
      </div>
      <div class="card">
        <div class="spread mb-1"><div class="section-title">International corpus</div>
          <div class="muted">${intl.length} instruments</div></div>
        ${intl.map(instRow).join("") || emptyState("No instruments")}
      </div>
    </div>`;
}

function instRow(inst) {
  const vstat = inst.verification_status || "EXTRACTED_BY_AI";
  const verified = vstat === "VERIFIED_AGAINST_GAZETTE";
  return `
    <div class="item-row" style="margin-bottom:9px">
      <div class="item-summary" onclick="this.parentElement.classList.toggle('open')">
        <div class="grow">
          <div class="rule-id">${esc(inst.id)}</div>
          <div class="req" style="font-size:12px">${esc(inst.title || "")}</div>
        </div>
        <span class="tag ${verified ? "ok" : "warn"}">${verified ? "✓" : "⚠"} ${esc(vstat)}</span>
        <svg class="chevron" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </div>
      <div class="item-body">
        <div class="contract-grid">
          <div class="contract-cell"><div class="c-k">Status</div><div class="c-v">${esc(inst.status || "—")}</div></div>
          <div class="contract-cell"><div class="c-k">Citation</div><div class="c-v">${esc(inst.citation || "—")}</div></div>
          ${inst.verify_open ? `
          <div class="contract-cell full"><div class="c-k">⚠ Open verification item</div>
            <div class="c-v">${esc(inst.verify_open)}</div></div>` : ""}
          ${inst.note ? `
          <div class="contract-cell full"><div class="c-k">Note</div><div class="c-v">${esc(inst.note)}</div></div>` : ""}
          ${inst.annexes ? `
          <div class="contract-cell full"><div class="c-k">Annexes</div>
            <div class="c-v">${inst.annexes.map(a => `<span class="tag">${esc(a)}</span>`).join("")}</div></div>` : ""}
        </div>
      </div>
    </div>`;
}

/* ---------------- change monitor ---------------- */
function viewChanges() {
  const impacts = (App.data.impacts || {}).open_verification_items || [];
  const sla = (App.data.impacts || {}).sla || "official publication → customer alert ≤ 72h for high-impact changes";
  return `
    <div class="banner">
      <div class="b-icon">🛰</div>
      <div><strong>Regulatory change pipeline.</strong>
      Source monitor → hash compare → classify → provision extraction → legal diff →
      rule impact analysis → human legal review → two-person approval → alerts. SLA: ${esc(sla)}.</div>
    </div>
    <div class="grid grid-2">
      <div class="card">
        <div class="spread mb-1"><div class="section-title">Open verification items</div>
          <div class="muted">never deleted — closed with verified_at + source URL</div></div>
        ${impacts.map(i => `
          <div class="item-row" style="margin-bottom:9px">
            <div class="item-summary">
              <span class="tag warn">⚠ VERIFY</span>
              <div class="grow"><div class="req">${esc(i.item)}</div></div>
              <span class="chip">${esc(i.verify_against || "")}</span>
            </div>
          </div>`).join("") || emptyState("Register empty")}
      </div>
      <div class="card">
        <div class="section-title mb-1">Change pipeline stages</div>
        ${[
          ["1", "Source monitor", "scheduled fetch + sha256 delta detection"],
          ["2", "Classifier", "instrument | amendment | repeal | circular | notice | tariff"],
          ["3", "Provision extraction", "layout-aware OCR, Bengali + English, provision-atomic"],
          ["4", "Legal diff", "provision-level, human-reviewable"],
          ["5", "Rule impact analysis", "ACTIVE rules touching changed provisions auto-flagged"],
          ["6", "Human legal review", "console → super-admin approval (two-person)"],
          ["7", "Customer alerts", "per impacted vessel/fleet, with deadline dates"],
        ].map(([n, k, v]) => `
          <div class="flex" style="padding:10px 0;border-bottom:1px solid rgba(148,197,253,0.07)">
            <div style="width:28px;height:28px;border-radius:9px;background:var(--grad-soft);
              display:grid;place-items:center;color:var(--accent);font-weight:800;font-size:11px">${n}</div>
            <div><div style="font-size:12.5px;font-weight:650">${esc(k)}</div>
            <div class="muted" style="font-size:11px">${esc(v)}</div></div>
          </div>`).join("")}
      </div>
    </div>`;
}

/* ------------------------------------------------------------
   Provenance drawer
   ------------------------------------------------------------ */
App.showProvenance = async function (imo, itemId) {
  $("#drawerTitle").textContent = "Provenance chain";
  $("#drawerBody").innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  $("#drawer").classList.add("open");
  $("#drawerBackdrop").classList.add("open");

  const res = await API.get(`/v1/vessels/${imo}/compliance/${encodeURIComponent(itemId)}/provenance`);
  if (!res) {
    const item = ((App.data.compliance || {})[imo]?.items || []).find(
      i => i.obligation_id === itemId) || { contract: {} };
    $("#drawerBody").innerHTML = `
      <div class="timeline">
        ${[["Result", `${item.status || ""} · as-of assessment`],
           ["Rule", item.contract?.rule_executed || itemId],
           ["Provision", item.provision_id || ""],
           ["Legal version", item.contract?.legal_version || ""],
           ["Instrument", item.contract?.source_law || ""],
           ["Official source", "bdlaws.minlaw.gov.bd / Gazette — gated by verification status"],
          ].map(([k, v]) => `<div class="tl-item"><div class="tl-k">${k}</div>
            <div class="tl-v">${esc(v)}</div></div>`).join("")}
      </div>
      <div class="banner mt-2"><div class="b-icon">◐</div>
        <div>Static preview chain — live backend verifies each hop against the registry.</div></div>`;
    return;
  }
  $("#drawerBody").innerHTML = `
    <div class="timeline">
      ${res.chain.map(hop => `
        <div class="tl-item"><div class="tl-k">${esc(hop.level)}</div>
        <div class="tl-v">${esc(hop.detail)}</div></div>`).join("")}
    </div>`;
};

App.closeDrawer = function () {
  $("#drawer").classList.remove("open");
  $("#drawerBackdrop").classList.remove("open");
};

/* ------------------------------------------------------------
   Router
   ------------------------------------------------------------ */
const VIEWS = {
  overview: { title: "Overview", crumb: "Maritime Regulatory Intelligence Suite", render: viewOverview },
  fleet: { title: "Fleet Compliance", crumb: "Vessels · status · obligations", render: viewFleet },
  rules: { title: "Rule Engine", crumb: "ILRMF-DSL · deterministic · fail-closed", render: viewRules },
  voyage: { title: "Voyage Preview", crumb: "LCA-1 multi-jurisdiction resolution", render: viewVoyage },
  corpus: { title: "Legal Corpus", crumb: "Instruments · provisions · verification", render: viewCorpus },
  changes: { title: "Change Monitor", crumb: "Amendments · impact · alerts", render: viewChanges },
  review: { title: "Legal Review Console", crumb: "Two-person gate · verification workflow · audit", render: viewReview },
  operations: { title: "Operations & Risk", crumb: "Incidents · liability · cyber · shipyard", render: viewOperations },
};

App.go = function (hash) {
  location.hash = hash;
};

App.route = async function () {
  const h = location.hash.replace(/^#\//, "") || "overview";
  const [name, param] = h.split("/");

  document.querySelectorAll(".nav-item").forEach(el =>
    el.classList.toggle("active", el.dataset.view === name || (name === "vessel" && el.dataset.view === "fleet")));

  if (name === "vessel" && param) {
    $("#pageTitle").textContent = "Vessel Assessment";
    $("#pageCrumb").textContent = `IMO ${param} · full result contract`;
    await viewVessel(param);
    return;
  }

  const v = VIEWS[name] || VIEWS.overview;
  $("#pageTitle").textContent = v.title;
  $("#pageCrumb").textContent = v.crumb;
  $("#content").innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
  await v.render();
};

/* ------------------------------------------------------------
   Boot
   ------------------------------------------------------------ */
(async function () {
  await API.boot();
  $("#asOfPill").textContent = `as of ${App.data.fleet?.as_of_date || "—"}`;
  window.addEventListener("hashchange", App.route);
  await App.route();
})();

// --- AUTHENTICATION GATE ---
const Auth = {
    init() {
        document.getElementById("auth-login-btn").onclick = () => this.login();
        document.getElementById("auth-register-btn").onclick = () => this.register();
        document.getElementById("auth-guest-btn").onclick = () => this.guest();
    },
    showModal(err = "") {
        document.getElementById("auth-error").innerText = err;
        document.getElementById("auth-modal").style.display = "flex";
    },
    hideModal() {
        document.getElementById("auth-modal").style.display = "none";
    },
    async login() {
        const u = document.getElementById("auth-username").value;
        const p = document.getElementById("auth-password").value;
        const res = await API.post("/v1/auth/token", { username: u, password: p });
        if (res && res.access_token) {
            API.setToken(res.access_token);
            this.hideModal();
            App.boot();
        } else {
            this.showModal(res.__error || "Login failed");
        }
    },
    async register() {
        const u = document.getElementById("auth-username").value;
        const p = document.getElementById("auth-password").value;
        const res = await API.post();
        if (res && res.message) {
            alert("Registered! Logging you in...");
            this.login();
        } else {
            this.showModal(res.__error || "Registration failed");
        }
    },
    guest() {
        this.hideModal();
        App.boot();
    }
};

Auth.init();
if (API.getToken()) {
    App.boot();
} else {
    Auth.showModal();
}

// --- AUTHENTICATION GATE ---
const Auth = {
    init() {
        document.getElementById("auth-login-btn").onclick = () => this.login();
        document.getElementById("auth-register-btn").onclick = () => this.register();
        document.getElementById("auth-guest-btn").onclick = () => this.guest();
    },
    showModal(err = "") {
        document.getElementById("auth-error").innerText = err;
        document.getElementById("auth-modal").style.display = "flex";
    },
    hideModal() {
        document.getElementById("auth-modal").style.display = "none";
    },
    async login() {
        const u = document.getElementById("auth-username").value;
        const p = document.getElementById("auth-password").value;
        const res = await API.post("/v1/auth/token", { username: u, password: p });
        if (res && res.access_token) {
            API.setToken(res.access_token);
            this.hideModal();
            App.boot();
        } else {
            this.showModal(res.__error || "Login failed");
        }
    },
    async register() {
        const u = document.getElementById("auth-username").value;
        const p = document.getElementById("auth-password").value;
        const res = await API.post("/v1/auth/register?username=" + encodeURIComponent(u) + "&password=" + encodeURIComponent(p) + "&company_name=Web%20User");
        if (res && res.message) {
            alert("Registered! Logging you in...");
            this.login();
        } else {
            this.showModal(res.__error || "Registration failed");
        }
    },
    guest() {
        this.hideModal();
        App.boot();
    }
};

Auth.init();
if (API.getToken()) {
    App.boot();
} else {
    Auth.showModal();
}

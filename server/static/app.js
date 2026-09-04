// REVIVE Control Center Single-Page Application Client Logic
// Autonomous Revenue Recovery Decision System

let activeTab = "overview";
let currentEventId = null;
let isExecuting = false;

// DOM Elements
const loadingOverlay = document.getElementById("loading-overlay");
const loadingText = document.getElementById("loading-text");
const caseModal = document.getElementById("case-modal");
const offlineBanner = document.getElementById("offline-banner");

// Format Currency with ₹ Symbol
function formatINR(val) {
  return "₹" + Number(val || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Format Percent
function formatPct(val) {
  return (Number(val || 0) * 100).toFixed(1) + "%";
}

// HTML Entity Escaper for XSS Prevention
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Show/Hide Loading
function showLoading(msg = "Processing...") {
  if (loadingText) loadingText.textContent = msg;
  if (loadingOverlay) loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  if (loadingOverlay) loadingOverlay.classList.add("hidden");
}

// Network Request Wrapper with Timeout and Correlation ID
async function apiFetch(url, options = {}) {
  const correlationId = "client_" + Math.random().toString(36).substring(2, 10);
  const headers = {
    "Content-Type": "application/json",
    "X-Correlation-ID": correlationId,
    ...(options.headers || {})
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000); // 15s timeout

  try {
    const res = await fetch(url, { ...options, headers, signal: controller.signal });
    clearTimeout(timeoutId);
    if (offlineBanner) offlineBanner.classList.add("hidden");

    if (!res.ok) {
      const errJson = await res.json().catch(() => ({ message: res.statusText }));
      throw new Error(errJson.message || `Server returned error ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. Please check backend server status.");
    }
    if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
      if (offlineBanner) offlineBanner.classList.remove("hidden");
    }
    throw err;
  }
}

// Tab Switching
document.querySelectorAll(".nav-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    const target = tab.getAttribute("data-tab");
    activeTab = target;
    const targetPanel = document.getElementById(`tab-${target}`);
    if (targetPanel) targetPanel.classList.add("active");

    if (target === "cases") loadCases();
    if (target === "safety") loadSafety();
    if (target === "audit") loadAudit();
  });
});

// Run Simulation Action
const btnRunSim = document.getElementById("btn-run-sim");
if (btnRunSim) {
  btnRunSim.addEventListener("click", async () => {
    if (btnRunSim.disabled) return;
    btnRunSim.disabled = true;

    const sizeInput = document.getElementById("sim-size");
    const seedInput = document.getElementById("sim-seed");
    const size = sizeInput ? parseInt(sizeInput.value) || 100 : 100;
    const seed = seedInput ? parseInt(seedInput.value) || 42 : 42;

    showLoading(`Generating synthetic batch & running REVIVE on ${size.toLocaleString()} transactions...`);
    try {
      const summary = await apiFetch("/api/simulation/run", {
        method: "POST",
        body: JSON.stringify({ size, seed, scenario: "balanced" })
      });
      renderOverview(summary);
      if (activeTab === "cases") loadCases();
      if (activeTab === "safety") loadSafety();
      if (activeTab === "audit") loadAudit();
    } catch (err) {
      alert("Simulation failed: " + err.message);
    } finally {
      btnRunSim.disabled = false;
      hideLoading();
    }
  });
}

// Reset Demo Session Action
const btnResetDemo = document.getElementById("btn-reset-demo");
if (btnResetDemo) {
  btnResetDemo.addEventListener("click", async () => {
    if (btnResetDemo.disabled) return;
    btnResetDemo.disabled = true;

    showLoading("Resetting demo session to deterministic golden state...");
    try {
      const summary = await apiFetch("/api/demo/reset", { method: "POST" });
      const sizeInput = document.getElementById("sim-size");
      const seedInput = document.getElementById("sim-seed");
      if (sizeInput) sizeInput.value = "100";
      if (seedInput) seedInput.value = "42";
      renderOverview(summary);
      if (activeTab === "cases") loadCases();
      if (activeTab === "safety") loadSafety();
      if (activeTab === "audit") loadAudit();
    } catch (err) {
      alert("Reset failed: " + err.message);
    } finally {
      btnResetDemo.disabled = false;
      hideLoading();
    }
  });
}

// Load Overview KPIs
async function loadOverview() {
  try {
    const summary = await apiFetch("/api/overview");
    renderOverview(summary);
  } catch (err) {
    console.error("Failed to load overview:", err);
  }
}

function renderOverview(summary) {
  const kpiRisk = document.getElementById("kpi-rev-risk");
  const kpiOpps = document.getElementById("kpi-opps");
  const kpiRec = document.getElementById("kpi-rev-rec");
  const kpiInc = document.getElementById("kpi-rev-inc");
  const kpiRate = document.getElementById("kpi-rec-rate");
  const kpiPrecision = document.getElementById("kpi-precision");
  const kpiActions = document.getElementById("kpi-actions-exec");
  const kpiAuth = document.getElementById("kpi-policy-auth");
  const kpiHuman = document.getElementById("kpi-human-rev");
  const kpiBlocks = document.getElementById("kpi-safety-blocks");
  const badgeCount = document.getElementById("cases-count-badge");

  if (kpiRisk) kpiRisk.textContent = formatINR(summary.revenue_at_risk);
  if (kpiOpps) kpiOpps.textContent = summary.total_failed_opportunities.toLocaleString();
  if (kpiRec) kpiRec.textContent = formatINR(summary.total_recovered_revenue);
  if (kpiInc) kpiInc.textContent = formatINR(summary.incremental_recovered_revenue);
  if (kpiRate) kpiRate.textContent = formatPct(summary.overall_recovery_rate);
  if (kpiPrecision) kpiPrecision.textContent = formatPct(summary.intervention_success_rate);
  if (kpiActions) kpiActions.textContent = summary.actions_executed_count.toLocaleString();
  if (kpiAuth) kpiAuth.textContent = summary.policy_authorized_count.toLocaleString();
  if (kpiHuman) kpiHuman.textContent = summary.policy_human_review_count.toLocaleString();
  if (kpiBlocks) kpiBlocks.textContent = summary.actions_blocked_count.toLocaleString();
  if (badgeCount) badgeCount.textContent = summary.total_failed_opportunities.toLocaleString();

  // Safety stat summary
  const sm = summary.safety_metrics || {};
  const elP002 = document.getElementById("stat-p002");
  const elP003 = document.getElementById("stat-p003");
  const elP004 = document.getElementById("stat-p004");
  const elP005 = document.getElementById("stat-p005");
  const elP007 = document.getElementById("stat-p007");
  const elDup = document.getElementById("stat-dup");

  if (elP002) elP002.textContent = (sm.resolved_payment_attempts_blocked || 0).toLocaleString();
  if (elP003) elP003.textContent = (sm.attempt_cap_violations_blocked || 0).toLocaleString();
  if (elP004) elP004.textContent = (sm.human_review_cases || 0).toLocaleString();
  if (elP005) elP005.textContent = "0";
  if (elP007) elP007.textContent = (sm.contact_limit_violations_blocked || 0).toLocaleString();
  if (elDup) elDup.textContent = (sm.duplicate_executions_prevented || 0).toLocaleString();

  // Render Action Breakdown
  const ab = summary.action_breakdown || {};
  const tbody = document.getElementById("action-breakdown-body");
  if (tbody) {
    tbody.innerHTML = "";
    Object.values(ab).forEach(row => {
      if (row.recommended_count > 0) {
        const tr = document.createElement("tr");
        const actionEsc = escapeHtml(row.action);
        tr.innerHTML = `
          <td><span class="status-pill status-${actionEsc.toLowerCase()}">${actionEsc}</span></td>
          <td>${Number(row.recommended_count || 0).toLocaleString()}</td>
          <td>${Number(row.authorized_count || 0).toLocaleString()}</td>
          <td>${Number(row.executed_count || 0).toLocaleString()}</td>
          <td>${formatINR(row.recovered_revenue)}</td>
          <td><strong class="text-green">${formatPct(row.intervention_success_rate)}</strong></td>
        `;
        tbody.appendChild(tr);
      }
    });
  }
}

// Load Recovery Cases
async function loadCases() {
  const statusEl = document.getElementById("filter-status");
  const actionEl = document.getElementById("filter-action");
  const searchEl = document.getElementById("filter-search");
  const sortEl = document.getElementById("sort-by");

  const status = statusEl ? statusEl.value : "all";
  const action = actionEl ? actionEl.value : "all";
  const search = searchEl ? searchEl.value : "";
  const sort = sortEl ? sortEl.value : "default";

  const params = new URLSearchParams();
  if (status && status !== "all") params.append("status", status);
  if (action && action !== "all") params.append("action", action);
  if (search) params.append("search", search);
  if (sort && sort !== "default") params.append("sort", sort);

  try {
    const cases = await apiFetch(`/api/recovery-cases?${params.toString()}`);
    renderCasesTable(cases);
  } catch (err) {
    console.error("Failed to load cases:", err);
  }
}

function renderCasesTable(cases) {
  const tbody = document.getElementById("cases-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!cases || cases.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center" style="padding: 30px; color: var(--text-muted);">No matching recovery cases found for current filter criteria.</td></tr>`;
    return;
  }

  cases.forEach(c => {
    const tr = document.createElement("tr");
    const policyClass = c.policy_decision === "ALLOW" ? "status-allow" : (c.policy_decision === "HUMAN_REVIEW" ? "status-review" : "status-deny");
    const execClass = c.execution_status === "EXECUTED" ? "status-executed" : (c.execution_status === "BLOCKED" ? "status-blocked" : "status-pending");

    const eventIdEsc = escapeHtml(c.event_id);
    const custIdEsc = escapeHtml(c.customer_id);
    const diagEsc = escapeHtml(c.diagnosis);
    const recTierEsc = escapeHtml(c.recoverability_tier);
    const recActEsc = escapeHtml(c.recommended_action);
    const polDecEsc = escapeHtml(c.policy_decision);
    const execStatEsc = escapeHtml(c.execution_status);
    const recOutEsc = escapeHtml(c.recovery_outcome);

    tr.className = "case-row";
    tr.setAttribute("data-id", eventIdEsc);
    tr.setAttribute("tabindex", "0");
    tr.setAttribute("role", "button");
    tr.setAttribute("aria-label", `Inspect recovery case ${eventIdEsc}`);
    tr.style.cursor = "pointer";

    tr.innerHTML = `
      <td><code class="code-tag">${eventIdEsc}</code></td>
      <td><code class="code-tag">${custIdEsc}</code></td>
      <td><strong>${formatINR(c.amount)}</strong></td>
      <td>${diagEsc} <span class="badge">${formatPct(c.confidence)}</span></td>
      <td><strong>${formatPct(c.recoverability_score)}</strong> <span class="badge tier-${recTierEsc.toLowerCase()}">${recTierEsc}</span></td>
      <td><span class="status-pill status-${recActEsc.toLowerCase()}">${recActEsc}</span></td>
      <td><span class="status-pill ${policyClass}">${polDecEsc}</span></td>
      <td><span class="status-pill ${execClass}">${execStatEsc}</span></td>
      <td>${c.recovered_amount > 0 ? `<strong class="text-green">${formatINR(c.recovered_amount)}</strong>` : `<span class="status-pill">${recOutEsc}</span>`}</td>
      <td><button class="btn btn-inspect" data-id="${eventIdEsc}" title="Inspect full decision chain">Inspect →</button></td>
    `;

    tr.addEventListener("click", () => openCaseDetail(c.event_id));
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openCaseDetail(c.event_id);
      }
    });

    tbody.appendChild(tr);
  });

  document.querySelectorAll(".btn-inspect").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openCaseDetail(btn.getAttribute("data-id"));
    });
  });
}

// Case Filter Listeners
const filterStatus = document.getElementById("filter-status");
const filterAction = document.getElementById("filter-action");
const filterSearch = document.getElementById("filter-search");
const sortBy = document.getElementById("sort-by");

if (filterStatus) filterStatus.addEventListener("change", loadCases);
if (filterAction) filterAction.addEventListener("change", loadCases);
if (filterSearch) filterSearch.addEventListener("input", debounce(loadCases, 300));
if (sortBy) sortBy.addEventListener("change", loadCases);

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

// Modal Detail Inspection
async function openCaseDetail(eventId) {
  currentEventId = eventId;
  showLoading("Fetching Case Intelligence & Audit Trail...");
  try {
    const d = await apiFetch(`/api/recovery-cases/${eventId}`);

    const modalTitle = document.getElementById("modal-title");
    const modalPayId = document.getElementById("modal-pay-id");
    const modalCustId = document.getElementById("modal-cust-id");
    const modalAmount = document.getElementById("modal-amount");
    const modalMethod = document.getElementById("modal-method");

    if (modalTitle) modalTitle.textContent = `Recovery Case: ${d.event_id}`;
    if (modalPayId) modalPayId.textContent = d.payment_id;
    if (modalCustId) modalCustId.textContent = d.customer_id;
    if (modalAmount) modalAmount.textContent = formatINR(d.amount);
    if (modalMethod) modalMethod.textContent = d.payment_method;

    // Phase 4 Intelligence
    const diagCat = document.getElementById("modal-diag-cat");
    const diagConf = document.getElementById("modal-diag-conf");
    const diagExpl = document.getElementById("modal-diag-expl");
    const riskSig = document.getElementById("modal-risk-sig");
    const recScore = document.getElementById("modal-rec-score");
    const recTier = document.getElementById("modal-rec-tier");

    if (diagCat) diagCat.textContent = d.diagnosis;
    if (diagConf) diagConf.textContent = formatPct(d.diagnosis_confidence);
    if (diagExpl) diagExpl.textContent = d.diagnosis_explanation;
    if (riskSig) riskSig.textContent = d.diagnosis_risk_signal;
    if (recScore) recScore.textContent = formatPct(d.recoverability_score);
    if (recTier) recTier.textContent = d.recoverability_tier;

    // Action Expected Values
    const evContainer = document.getElementById("modal-action-scores");
    if (evContainer) {
      evContainer.innerHTML = "";
      const maxEV = Math.max(...(d.action_scores || []).map(a => Math.max(0, a.expected_value)), 1);

      (d.action_scores || []).forEach(as => {
        const row = document.createElement("div");
        row.className = "ev-bar-item";
        const widthPct = Math.min(100, Math.max(8, (Math.max(0, as.expected_value) / maxEV) * 100));
        const actionEsc = escapeHtml(as.action);
        row.innerHTML = `
          <div class="ev-bar-header">
            <span><strong>${actionEsc}</strong> (P(Success): ${formatPct(as.success_probability)})</span>
            <span>EV: <strong class="text-blue">${formatINR(as.expected_value)}</strong></span>
          </div>
          <div class="ev-bar-track">
            <div class="ev-bar-fill" style="width: ${widthPct}%;"></div>
          </div>
        `;
        evContainer.appendChild(row);
      });
    }

    // Top Factors
    const factorsList = document.getElementById("modal-top-factors");
    if (factorsList) {
      factorsList.innerHTML = "";
      (d.top_positive_factors || []).forEach(f => {
        const li = document.createElement("li");
        const fStr = String(f || "");
        const isPos = fStr.includes("+") || fStr.toLowerCase().includes("high") || fStr.toLowerCase().includes("reliable");
        li.className = isPos ? "factor-pos" : "factor-neg";
        li.innerHTML = `<span class="factor-icon">${isPos ? "▲" : "▼"}</span> <span>${escapeHtml(fStr)}</span>`;
        factorsList.appendChild(li);
      });
    }

    // Phase 5 Policy Decision
    const pBadge = document.getElementById("modal-policy-badge");
    if (pBadge) {
      pBadge.className = `policy-decision-banner ${escapeHtml(d.policy_decision || "")}`;
      pBadge.textContent = `DECISION: ${d.policy_decision} (${d.policy_rule_id || "P010_ACTION_APPROVED"})`;
    }
    const policyReason = document.getElementById("modal-policy-reason");
    if (policyReason) policyReason.textContent = d.policy_reason;

    const authIdEl = document.getElementById("modal-auth-id");
    if (authIdEl) authIdEl.textContent = d.authorization_id || "None (Execution not authorized)";

    // Safety Checklist
    const checklistDiv = document.getElementById("modal-safety-checklist");
    if (checklistDiv) {
      checklistDiv.innerHTML = "";
      (d.safety_checklist || []).forEach(item => {
        const cDiv = document.createElement("div");
        cDiv.className = `check-item ${item.passed ? "check-pass" : "check-fail"}`;
        const ruleIdEsc = escapeHtml(item.rule_id);
        const ruleNameEsc = escapeHtml(item.rule_name);
        const descEsc = escapeHtml(item.description);
        cDiv.innerHTML = `
          <span class="check-icon ${item.passed ? "passed" : "failed"}">${item.passed ? "✓" : "✕"}</span>
          <span><strong>[${ruleIdEsc}] ${ruleNameEsc}:</strong> ${descEsc}</span>
        `;
        checklistDiv.appendChild(cDiv);
      });
    }

    // Phase 6 Execution & Outcome
    const execStatus = document.getElementById("modal-exec-status");
    const outcomeEl = document.getElementById("modal-outcome");
    const recAmount = document.getElementById("modal-rec-amount");
    const extRef = document.getElementById("modal-ext-ref");

    if (execStatus) execStatus.textContent = d.execution_status;
    if (outcomeEl) outcomeEl.textContent = d.recovery_outcome;
    if (recAmount) recAmount.textContent = formatINR(d.recovered_amount);
    if (extRef) extRef.textContent = d.simulated_external_reference || "None";

    // Execution Button State
    const execBtn = document.getElementById("modal-btn-execute");
    if (execBtn) {
      if (d.can_execute) {
        execBtn.disabled = false;
        execBtn.textContent = "⚡ Execute Simulated Recovery";
        execBtn.className = "btn btn-success btn-large";
      } else {
        execBtn.disabled = true;
        if (d.execution_status === "EXECUTED") {
          execBtn.textContent = "✓ Already Executed";
          execBtn.className = "btn btn-secondary btn-large";
        } else if (d.policy_decision === "DENY") {
          execBtn.textContent = "✕ Blocked by Safety Policy";
          execBtn.className = "btn btn-secondary btn-large";
        } else if (d.policy_decision === "HUMAN_REVIEW") {
          execBtn.textContent = "⚠️ Requires Human Review";
          execBtn.className = "btn btn-secondary btn-large";
        } else {
          execBtn.textContent = "No Intervention Recommended";
          execBtn.className = "btn btn-secondary btn-large";
        }
      }
    }

    // Update Decision Chain Visual Flow Steps
    const stepAuth = document.getElementById("chain-step-5");
    const stepExec = document.getElementById("chain-step-6");
    const stepOut = document.getElementById("chain-step-7");
    if (stepAuth) {
      if (d.authorization_id && d.policy_decision === "ALLOW") {
        stepAuth.classList.add("active");
      } else {
        stepAuth.classList.remove("active");
      }
    }
    if (stepExec) {
      if (d.execution_status === "EXECUTED") {
        stepExec.classList.add("active");
      } else {
        stepExec.classList.remove("active");
      }
    }
    if (stepOut) {
      if (d.execution_status === "EXECUTED") {
        stepOut.classList.add("active");
      } else {
        stepOut.classList.remove("active");
      }
    }

    const modalEl = document.getElementById("case-modal") || caseModal;
    if (modalEl) modalEl.classList.remove("hidden");
  } catch (err) {
    alert("Failed to load case: " + err.message);
  } finally {
    hideLoading();
  }
}

// Modal Close Handlers
function closeModal() {
  const modalEl = document.getElementById("case-modal") || caseModal;
  if (modalEl) modalEl.classList.add("hidden");
}

const modalCloseBtn = document.getElementById("modal-close-btn");
if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeModal);

const modalBackdrop = document.querySelector(".modal-backdrop");
if (modalBackdrop) modalBackdrop.addEventListener("click", closeModal);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});

// Modal Execute Recovery Action (Protected against double-clicks)
const modalBtnExecute = document.getElementById("modal-btn-execute");
if (modalBtnExecute) {
  modalBtnExecute.addEventListener("click", async () => {
    if (!currentEventId || isExecuting) return;
    isExecuting = true;

    modalBtnExecute.disabled = true;
    modalBtnExecute.textContent = "Executing...";

    showLoading("Re-validating Authorization & Executing through Phase 6 Simulator...");
    try {
      const result = await apiFetch(`/api/recovery-cases/${encodeURIComponent(currentEventId)}/execute`, {
        method: "POST"
      });
      alert(`Simulation Execution Completed:\n\nStatus: ${result.execution_status}\nOutcome: ${result.recovery_outcome}\nRecovered Amount: ${formatINR(result.recovered_amount)}\nReference: ${result.external_reference || "N/A"}`);
      await openCaseDetail(currentEventId);
      loadOverview();
    } catch (err) {
      alert("Execution error: " + err.message);
    } finally {
      isExecuting = false;
      hideLoading();
    }
  });
}

// Load Safety Tab
async function loadSafety() {
  try {
    await apiFetch("/api/safety");
  } catch (err) {
    console.error("Failed to load safety:", err);
  }
}

// Load Audit Log Tab
async function loadAudit() {
  try {
    const events = await apiFetch("/api/audit");
    const tbody = document.getElementById("audit-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!events || events.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center" style="padding: 30px; color: var(--text-muted);">No audit events recorded yet.</td></tr>`;
      return;
    }

    events.forEach(e => {
      const tr = document.createElement("tr");
      const eventTypeStr = String(e.event_type || "");
      const eventTypeClass = `audit-type-${eventTypeStr.toLowerCase()}`;
      const auditIdEsc = escapeHtml(e.audit_id);
      const tsEsc = escapeHtml(e.timestamp);
      const evTypeEsc = escapeHtml(e.event_type);
      const payIdEsc = escapeHtml(e.payment_id);
      const custIdEsc = escapeHtml(e.customer_id);
      const actEsc = escapeHtml(e.action);
      const detailsEsc = escapeHtml(JSON.stringify(e.details, null, 2));

      tr.innerHTML = `
        <td><code class="code-tag">${auditIdEsc}</code></td>
        <td style="font-size: 12px; color: var(--text-secondary);">${tsEsc}</td>
        <td><span class="status-pill ${eventTypeClass}">${evTypeEsc}</span></td>
        <td><code class="code-tag">${payIdEsc}</code></td>
        <td><code class="code-tag">${custIdEsc}</code></td>
        <td><span class="status-pill status-${actEsc.toLowerCase()}">${actEsc}</span></td>
        <td><pre class="audit-details-json">${detailsEsc}</pre></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load audit:", err);
  }
}

// Initial Boot
window.addEventListener("DOMContentLoaded", () => {
  loadOverview();
});

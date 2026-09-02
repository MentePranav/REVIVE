// REVIVE Control Center Single-Page Application Client Logic

let activeTab = "overview";
let currentEventId = null;

// DOM Elements
const loadingOverlay = document.getElementById("loading-overlay");
const loadingText = document.getElementById("loading-text");
const caseModal = document.getElementById("case-modal");

// Format Currency
function formatINR(val) {
  return "INR " + Number(val || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Format Percent
function formatPct(val) {
  return (Number(val || 0) * 100).toFixed(1) + "%";
}

// Show/Hide Loading
function showLoading(msg = "Processing...") {
  loadingText.textContent = msg;
  loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  loadingOverlay.classList.add("hidden");
}

// Tab Switching
document.querySelectorAll(".nav-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    const target = tab.getAttribute("data-tab");
    activeTab = target;
    document.getElementById(`tab-${target}`).classList.add("active");

    if (target === "cases") loadCases();
    if (target === "safety") loadSafety();
    if (target === "audit") loadAudit();
  });
});

// Run Simulation Action
document.getElementById("btn-run-sim").addEventListener("click", async () => {
  const size = parseInt(document.getElementById("sim-size").value) || 100;
  const seed = parseInt(document.getElementById("sim-seed").value) || 42;

  showLoading(`Generating synthetic batch & running REVIVE on ${size:,} transactions...`);
  try {
    const res = await fetch("/api/simulation/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ size, seed, scenario: "balanced" })
    });
    const summary = await res.json();
    renderOverview(summary);
    if (activeTab === "cases") loadCases();
    if (activeTab === "safety") loadSafety();
    if (activeTab === "audit") loadAudit();
  } catch (err) {
    alert("Simulation failed: " + err.message);
  } finally {
    hideLoading();
  }
});

// Load Overview KPIs
async function loadOverview() {
  try {
    const res = await fetch("/api/overview");
    const summary = await res.json();
    renderOverview(summary);
  } catch (err) {
    console.error("Failed to load overview:", err);
  }
}

function renderOverview(summary) {
  document.getElementById("kpi-rev-risk").textContent = formatINR(summary.revenue_at_risk);
  document.getElementById("kpi-opps").textContent = summary.total_failed_opportunities.toLocaleString();
  document.getElementById("kpi-rev-rec").textContent = formatINR(summary.total_recovered_revenue);
  document.getElementById("kpi-rev-inc").textContent = formatINR(summary.incremental_recovered_revenue);
  document.getElementById("kpi-rec-rate").textContent = formatPct(summary.overall_recovery_rate);
  document.getElementById("kpi-precision").textContent = formatPct(summary.intervention_success_rate);
  document.getElementById("kpi-actions-exec").textContent = summary.actions_executed_count.toLocaleString();
  document.getElementById("kpi-policy-auth").textContent = summary.policy_authorized_count.toLocaleString();
  document.getElementById("kpi-human-rev").textContent = summary.policy_human_review_count.toLocaleString();
  document.getElementById("kpi-safety-blocks").textContent = summary.actions_blocked_count.toLocaleString();
  document.getElementById("cases-count-badge").textContent = summary.total_failed_opportunities.toLocaleString();

  // Safety stat summary
  const sm = summary.safety_metrics || {};
  document.getElementById("stat-p002").textContent = (sm.resolved_payment_attempts_blocked || 0).toLocaleString();
  document.getElementById("stat-p003").textContent = (sm.attempt_cap_violations_blocked || 0).toLocaleString();
  document.getElementById("stat-p004").textContent = (sm.human_review_cases || 0).toLocaleString();
  document.getElementById("stat-p005").textContent = "0";
  document.getElementById("stat-p007").textContent = (sm.contact_limit_violations_blocked || 0).toLocaleString();
  document.getElementById("stat-dup").textContent = (sm.duplicate_executions_prevented || 0).toLocaleString();

  // Render Action Breakdown
  const ab = summary.action_breakdown || {};
  const tbody = document.getElementById("action-breakdown-body");
  tbody.innerHTML = "";

  Object.values(ab).forEach(row => {
    if (row.recommended_count > 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="status-pill">${row.action}</span></td>
        <td>${row.recommended_count.toLocaleString()}</td>
        <td>${row.authorized_count.toLocaleString()}</td>
        <td>${row.executed_count.toLocaleString()}</td>
        <td>${formatINR(row.recovered_revenue)}</td>
        <td><strong>${formatPct(row.intervention_success_rate)}</strong></td>
      `;
      tbody.appendChild(tr);
    }
  });
}

// Load Recovery Cases
async function loadCases() {
  const status = document.getElementById("filter-status").value;
  const action = document.getElementById("filter-action").value;
  const search = document.getElementById("filter-search").value;
  const sort = document.getElementById("sort-by").value;

  const params = new URLSearchParams();
  if (status) params.append("status", status);
  if (action) params.append("action", action);
  if (search) params.append("search", search);
  if (sort) params.append("sort", sort);

  try {
    const res = await fetch(`/api/recovery-cases?${params.toString()}`);
    const cases = await res.json();
    renderCasesTable(cases);
  } catch (err) {
    console.error("Failed to load cases:", err);
  }
}

function renderCasesTable(cases) {
  const tbody = document.getElementById("cases-table-body");
  tbody.innerHTML = "";

  if (cases.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center">No matching recovery cases found.</td></tr>`;
    return;
  }

  cases.forEach(c => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${c.event_id}</code></td>
      <td><code>${c.customer_id}</code></td>
      <td><strong>${formatINR(c.amount)}</strong></td>
      <td>${c.diagnosis} <span class="badge">${formatPct(c.confidence)}</span></td>
      <td><strong>${formatPct(c.recoverability_score)}</strong> <span class="badge">${c.recoverability_tier}</span></td>
      <td><span class="status-pill">${c.recommended_action}</span></td>
      <td><span class="status-pill ${c.policy_decision}">${c.policy_decision}</span></td>
      <td><span class="status-pill ${c.execution_status}">${c.execution_status}</span></td>
      <td>${c.recovered_amount > 0 ? `<strong class="text-green">${formatINR(c.recovered_amount)}</strong>` : `<span class="status-pill">${c.recovery_outcome}</span>`}</td>
      <td><button class="btn btn-inspect" data-id="${c.event_id}">Inspect</button></td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll(".btn-inspect").forEach(btn => {
    btn.addEventListener("click", () => openCaseDetail(btn.getAttribute("data-id")));
  });
}

// Case Filter Listeners
document.getElementById("filter-status").addEventListener("change", loadCases);
document.getElementById("filter-action").addEventListener("change", loadCases);
document.getElementById("filter-search").addEventListener("input", debounce(loadCases, 300));
document.getElementById("sort-by").addEventListener("change", loadCases);

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
    const res = await fetch(`/api/recovery-cases/${eventId}`);
    const d = await res.json();

    document.getElementById("modal-title").textContent = `Recovery Case: ${d.event_id}`;
    document.getElementById("modal-pay-id").textContent = d.payment_id;
    document.getElementById("modal-cust-id").textContent = d.customer_id;
    document.getElementById("modal-amount").textContent = formatINR(d.amount);
    document.getElementById("modal-method").textContent = d.payment_method;

    // Phase 4 Intelligence
    document.getElementById("modal-diag-cat").textContent = d.diagnosis;
    document.getElementById("modal-diag-conf").textContent = formatPct(d.diagnosis_confidence);
    document.getElementById("modal-diag-expl").textContent = d.diagnosis_explanation;
    document.getElementById("modal-risk-sig").textContent = d.diagnosis_risk_signal;
    document.getElementById("modal-rec-score").textContent = formatPct(d.recoverability_score);
    document.getElementById("modal-rec-tier").textContent = d.recoverability_tier;

    // Action Expected Values
    const evContainer = document.getElementById("modal-action-scores");
    evContainer.innerHTML = "";
    (d.action_scores || []).forEach(as => {
      const row = document.createElement("div");
      row.className = "ev-bar-item";
      row.innerHTML = `
        <span><strong>${as.action}</strong> (Prob: ${formatPct(as.success_probability)})</span>
        <span>Expected Value: <strong>${formatINR(as.expected_value)}</strong></span>
      `;
      evContainer.appendChild(row);
    });

    // Top Factors
    const factorsList = document.getElementById("modal-top-factors");
    factorsList.innerHTML = "";
    (d.top_positive_factors || []).forEach(f => {
      const li = document.createElement("li");
      li.textContent = f;
      factorsList.appendChild(li);
    });

    // Phase 5 Policy Decision
    const pBadge = document.getElementById("modal-policy-badge");
    pBadge.className = `policy-decision-banner ${d.policy_decision}`;
    pBadge.textContent = `DECISION: ${d.policy_decision} (${d.policy_rule_id || "P010_ACTION_APPROVED"})`;
    document.getElementById("modal-policy-reason").textContent = d.policy_reason;
    document.getElementById("modal-auth-id").textContent = d.authorization_id || "None (Execution not authorized)";

    // Safety Checklist
    const checklistDiv = document.getElementById("modal-safety-checklist");
    checklistDiv.innerHTML = "";
    (d.safety_checklist || []).forEach(item => {
      const cDiv = document.createElement("div");
      cDiv.className = "check-item";
      cDiv.innerHTML = `
        <span class="check-icon ${item.passed ? "passed" : "failed"}">${item.passed ? "✓" : "✕"}</span>
        <span><strong>[${item.rule_id}] ${item.rule_name}:</strong> ${item.description}</span>
      `;
      checklistDiv.appendChild(cDiv);
    });

    // Phase 6 Execution & Outcome
    document.getElementById("modal-exec-status").textContent = d.execution_status;
    document.getElementById("modal-outcome").textContent = d.recovery_outcome;
    document.getElementById("modal-rec-amount").textContent = formatINR(d.recovered_amount);
    document.getElementById("modal-ext-ref").textContent = d.simulated_external_reference || "None";

    // Execution Button State
    const execBtn = document.getElementById("modal-btn-execute");
    if (d.can_execute) {
      execBtn.disabled = false;
      execBtn.textContent = "⚡ Execute Simulated Recovery";
      execBtn.className = "btn btn-success btn-large";
    } else {
      execBtn.disabled = true;
      if (d.execution_status === "EXECUTED") {
        execBtn.textContent = "✓ Already Executed";
        execBtn.className = "btn btn-large";
      } else if (d.policy_decision === "DENY") {
        execBtn.textContent = "✕ Blocked by Safety Policy";
        execBtn.className = "btn btn-large";
      } else if (d.policy_decision === "HUMAN_REVIEW") {
        execBtn.textContent = "⚠️ Requires Human Review";
        execBtn.className = "btn btn-large";
      } else {
        execBtn.textContent = "No Intervention Recommended";
        execBtn.className = "btn btn-large";
      }
    }

    caseModal.classList.remove("hidden");
  } catch (err) {
    alert("Failed to load case: " + err.message);
  } finally {
    hideLoading();
  }
}

// Modal Close Handlers
document.getElementById("modal-close-btn").addEventListener("click", () => caseModal.classList.add("hidden"));
document.querySelector(".modal-backdrop").addEventListener("click", () => caseModal.classList.add("hidden"));

// Modal Execute Recovery Action
document.getElementById("modal-btn-execute").addEventListener("click", async () => {
  if (!currentEventId) return;

  showLoading("Re-validating Authorization & Executing through Phase 6 Simulator...");
  try {
    const res = await fetch(`/api/recovery-cases/${currentEventId}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    const result = await res.json();
    alert(`Execution Completed:\nStatus: ${result.execution_status}\nOutcome: ${result.recovery_outcome}\nRecovered: ${formatINR(result.recovered_amount)}\nRef: ${result.external_reference || "N/A"}`);
    await openCaseDetail(currentEventId);
    loadOverview();
  } catch (err) {
    alert("Execution error: " + err.message);
  } finally {
    hideLoading();
  }
});

// Load Safety Tab
async function loadSafety() {
  try {
    const res = await fetch("/api/safety");
    const data = await res.json();
  } catch (err) {
    console.error("Failed to load safety:", err);
  }
}

// Load Audit Log Tab
async function loadAudit() {
  try {
    const res = await fetch("/api/audit");
    const events = await res.json();
    const tbody = document.getElementById("audit-table-body");
    tbody.innerHTML = "";

    if (events.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center">No audit events recorded yet.</td></tr>`;
      return;
    }

    events.forEach(e => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><code>${e.audit_id}</code></td>
        <td>${e.timestamp}</td>
        <td><span class="status-pill">${e.event_type}</span></td>
        <td><code>${e.payment_id}</code></td>
        <td><code>${e.customer_id}</code></td>
        <td><span class="status-pill">${e.action}</span></td>
        <td><pre style="margin:0; font-size:10px;">${JSON.stringify(e.details)}</pre></td>
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

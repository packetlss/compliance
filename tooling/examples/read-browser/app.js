(() => {
  "use strict";

  const supported = new Map([
    ["compliance.example/inventory-assets-view/v1alpha1", ["Inventory assets", "assets"]],
    ["compliance.example/coverage-assets-view/v1alpha1", ["Current coverage", "assets"]],
    ["compliance.example/coverage-asset-explanation/v1alpha1", ["Coverage explanation", "assignments"]],
    ["compliance.example/assessment-status-view/v1alpha1", ["Assessment status", "assets"]],
    ["compliance.example/assessment-explanation-view/v1alpha1", ["Assessment explanation", "checks"]],
    ["compliance.example/assessment-mappings-view/v1alpha1", ["Mappings / traceability", "mappings"]],
    ["compliance.example/framework-satisfaction-status/v1alpha1", ["Framework satisfaction", "obligations"]],
    ["compliance.example/framework-satisfaction-explanation/v1alpha1", ["Framework explanation", "obligations"]],
    ["compliance.example/policy-diff/v1alpha1", ["Policy diff", "control_changes"]],
  ]);

  const state = { responses: [], selected: -1, filter: "", sort: "source" };
  const files = document.querySelector("#response-files");
  const status = document.querySelector("#load-status");
  const navigation = document.querySelector("#views");
  const content = document.querySelector("#content");
  const filter = document.querySelector("#filter");
  const sort = document.querySelector("#sort");

  const text = value => value === null || value === undefined ? "—" :
    typeof value === "string" ? value : JSON.stringify(value);
  const escape = value => text(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const statusMarkup = value => `<span class="status ${escape(String(value || "").toLowerCase())}">${escape(value)}</span>`;

  function facts(values) {
    return `<dl class="facts">${Object.entries(values).map(([key, value]) =>
      `<div class="fact"><dt>${escape(key.replaceAll("_", " "))}</dt><dd>${escape(value)}</dd></div>`
    ).join("")}</dl>`;
  }

  function rowLabel(row, index) {
    return row.asset_id || row.group_id || row.external_ref || row.id ||
      row.policy_object || row.instance_id || `row ${index + 1}`;
  }

  function rowsFor(document, rowField) {
    let rows = Array.isArray(document[rowField]) ? [...document[rowField]] : [];
    if (state.filter) {
      const needle = state.filter.toLocaleLowerCase();
      rows = rows.filter(row => JSON.stringify(row).toLocaleLowerCase().includes(needle));
    }
    if (state.sort === "label") {
      rows.sort((left, right) => rowLabel(left, 0).localeCompare(rowLabel(right, 0)));
    }
    return rows;
  }

  function card(row, index) {
    const entries = Object.entries(row).filter(([key]) => !["checks", "objectives"].includes(key));
    return `<section class="card"><h3>${escape(rowLabel(row, index))}</h3><dl>${entries.map(([key, value]) =>
      `<dt>${escape(key.replaceAll("_", " "))}</dt><dd>${key.includes("outcome") || key === "state" || key === "coverage_class" ? statusMarkup(value) : `<code>${escape(value)}</code>`}</dd>`
    ).join("")}</dl></section>`;
  }

  function explanation(document) {
    const policies = (document.applicable_policies || []).map(policy =>
      `<section class="card"><h3>${escape(policy.title)}</h3><p class="path">Asset → policy ${escape(policy.reference)}</p><p>${escape(policy.paths)}</p></section>`
    ).join("");
    const objectives = (document.objectives || []).map(objective =>
      `<section class="card"><h3>Objective: ${escape(objective.title)}</h3><p>${escape(objective.statement)}</p><p>Implementation: ${escape(objective.implementation_state)}</p><p>Assessment outcome: ${statusMarkup(objective.historical_outcome)}</p><p>${escape(objective.historical_reason)}</p></section>`
    ).join("");
    const checks = rowsFor(document, "checks").map((item, index) => {
      const check = item.check || {};
      const outcome = item.historical_result?.historical_outcome;
      const evidence = (item.required_evidence || []).map(dependency => {
        const selected = dependency.selected_evidence;
        const retained = selected?.retained_evidence;
        const selection = selected ?
          `; Evidence ${escape(selected.evidence_id)}; digest ${escape(selected.evidence_digest)}; collected ${escape(selected.collected_at)}` : "";
        const collector = retained ?
          `; retained collector ${escape(retained.collector.id)}@${escape(retained.collector.version)} (${escape(retained.match)})` : "";
        return `<li><strong>${escape(dependency.evidence_type)}</strong> (${escape(dependency.dependency_id)}) → ${escape(dependency.selection)}${dependency.inputs ? `; inputs ${escape(dependency.inputs)}` : ""}${selection}${collector}</li>`;
      }).join("");
      return `<section class="card"><h3>Check: ${escape(check.title || rowLabel(item, index))}</h3><p>${escape(check.purpose)}</p><p>${statusMarkup(outcome)}</p><p class="path">Check → required Evidence → result</p><ul>${evidence}</ul></section>`;
    }).join("");
    return policies + objectives + checks || card(document, 0);
  }

  function policyDiff(document) {
    const sections = [
      ["Comparison context", [document.context]],
      ["Scope changes", document.scope_changes || []],
      ["Requirement changes", document.requirement_changes || []],
      ["Control changes", document.control_changes || []],
    ];
    return sections.map(([title, rows]) =>
      `<section><h3>${escape(title)}</h3><div class="cards">${rows.filter(Boolean).map(card).join("") || '<p class="empty">None.</p>'}</div></section>`
    ).join("");
  }

  function rowFieldFor(document, configuredField) {
    if (document.schema === "compliance.example/assessment-status-view/v1alpha1") {
      return document.view === "groups" ? "groups" : "assets";
    }
    return configuredField;
  }

  function assessmentStatus(document, configuredField) {
    const accounting = document.whole_operation ?
      `<section><h3>Whole operation accounting</h3>${card(document.whole_operation, 0)}</section>` : "";
    const rowField = rowFieldFor(document, configuredField);
    const title = rowField === "groups" ? "Frozen group accounting" : "Frozen asset accounting";
    const rows = rowsFor(document, rowField).map(card).join("") || '<p class="empty">None.</p>';
    return `${accounting}<section><h3>${title}</h3><div class="cards">${rows}</div></section>`;
  }

  function framework(document) {
    const context = {
      declaration: document.declaration,
      framework: document.framework,
      scope: document.scope,
      state: document.state,
      statement: document.statement,
    };
    const obligations = rowsFor(document, "obligations").map(card).join("") ||
      '<p class="empty">None.</p>';
    return `<section><h3>Exact declaration and bounded claim</h3>${card(context, 0)}</section>` +
      `<section><h3>Declared obligations</h3><div class="cards">${obligations}</div></section>`;
  }

  function render() {
    navigation.innerHTML = state.responses.map((entry, index) =>
      `<button type="button" data-index="${index}" aria-current="${index === state.selected}">${escape(entry.name)}</button>`
    ).join("");
    if (state.selected < 0) return;
    const entry = state.responses[state.selected];
    const document = entry.document;
    const [label, rowField] = supported.get(document.schema);
    const summary = {
      schema: document.schema,
      operation: document.operation?.operation_id,
      assessment_instant: document.operation?.evaluated_at,
      query_instant: document.query_instant || document.operation?.query_instant,
      historical_outcome: document.historical_outcome,
      implementation_gap: document.implementation_gap,
      current_qualification: document.current_qualification ? "shown separately" : undefined,
    };
    const visibleFacts = Object.fromEntries(Object.entries(summary).filter(([, value]) => value !== undefined));
    let body;
    if (document.schema === "compliance.example/assessment-explanation-view/v1alpha1") {
      body = explanation(document);
    } else if (document.schema === "compliance.example/assessment-status-view/v1alpha1") {
      body = assessmentStatus(document, rowField);
    } else if (document.schema.startsWith("compliance.example/framework-satisfaction-")) {
      body = framework(document);
    } else if (document.schema === "compliance.example/policy-diff/v1alpha1") {
      body = policyDiff(document);
    } else {
      body = rowsFor(document, rowFieldFor(document, rowField)).map(card).join("") || card(document, 0);
    }
    content.className = "";
    content.innerHTML = `<p class="eyebrow">${escape(label)}</p><h2>${escape(entry.name)}</h2>${facts(visibleFacts)}<div class="cards">${body}</div>`;
  }

  function loadResponses(entries) {
    const accepted = [];
    const rejected = [];
    for (const entry of entries) {
      const document = entry.document ?? entry;
      if (!document || !supported.has(document.schema)) {
        rejected.push(entry.name || document?.schema || "unknown response");
        continue;
      }
      accepted.push({ name: entry.name || supported.get(document.schema)[0], document });
    }
    state.responses.push(...accepted);
    if (state.selected < 0 && state.responses.length) state.selected = 0;
    status.textContent = `${accepted.length} supported response(s) loaded${rejected.length ? `; ${rejected.length} unsupported raw/unknown document(s) rejected` : ""}.`;
    render();
    return { accepted: accepted.length, rejected: rejected.length };
  }

  files.addEventListener("change", async event => {
    const entries = [];
    for (const file of event.target.files) {
      try { entries.push({ name: file.name, document: JSON.parse(await file.text()) }); }
      catch { entries.push({ name: file.name, document: null }); }
    }
    loadResponses(entries);
  });
  navigation.addEventListener("click", event => {
    const button = event.target.closest("button[data-index]");
    if (!button) return;
    state.selected = Number(button.dataset.index);
    render();
  });
  filter.addEventListener("input", () => { state.filter = filter.value; render(); });
  sort.addEventListener("change", () => { state.sort = sort.value; render(); });

  window.complianceReadBrowser = { loadResponses };
})();

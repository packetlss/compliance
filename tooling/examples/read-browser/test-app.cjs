"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor() {
    this.className = "";
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.listeners = new Map();
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }
}

const elements = new Map(
  ["#response-files", "#load-status", "#views", "#content", "#filter", "#sort"]
    .map(selector => [selector, new Element()]),
);
global.document = { querySelector: selector => elements.get(selector) };
global.window = {};

const application = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
vm.runInThisContext(application, { filename: "app.js" });

const documents = [
  {
    schema: "compliance.example/assessment-status-view/v1alpha1",
    view: "groups",
    groups: [{
      group_id: "overlap-a",
      frozen_accounting: { selected_assets: 2, expected_result_slots: 2 },
    }],
  },
  {
    schema: "compliance.example/assessment-explanation-view/v1alpha1",
    asset: { id: "host/A" },
    applicable_policies: [{ reference: "policy.example@1", title: "Example policy" }],
    objectives: [],
    checks: [{
      check: { title: "Example check", purpose: "Exercise presentation." },
      historical_result: { historical_outcome: "pass" },
      required_evidence: [{
        dependency_id: "observation",
        evidence_type: "example.evidence/v1",
        selection: "selected",
        selected_evidence: {
          evidence_id: "evidence:exact",
          evidence_digest: `sha256:${"a".repeat(64)}`,
          collected_at: "2026-09-01T00:00:00Z",
          retained_evidence: {
            match: "exact_evidence_id_and_digest",
            collector: { id: "example-collector", version: "1" },
          },
        },
      }],
    }],
  },
  {
    schema: "compliance.example/framework-satisfaction-explanation/v1alpha1",
    obligations: [{
      id: "obligation-one",
      state: "satisfied",
      support: [{ owner: "framework-owner", determination: "affirmative" }],
    }],
  },
  {
    schema: "compliance.example/policy-diff/v1alpha1",
    context: { changed: true, changed_fields: ["operation_id"] },
    scope_changes: [{ identity: "scope-one", change: "modified" }],
    requirement_changes: [{ identity: "objective-one", change: "modified" }],
    control_changes: [{ identity: "check-one", change: "modified" }],
  },
];

const loaded = window.complianceReadBrowser.loadResponses(
  documents.map((document, index) => ({ name: `projection-${index}`, document })),
);
assert.deepEqual(loaded, { accepted: 4, rejected: 0 });

const navigation = elements.get("#views");
const content = elements.get("#content");
function select(index) {
  navigation.listeners.get("click")({
    target: { closest: () => ({ dataset: { index: String(index) } }) },
  });
  return content.innerHTML;
}

assert.match(select(0), /overlap-a/);
assert.match(content.innerHTML, /selected_assets/);

const explanation = select(1);
assert.match(explanation, /evidence:exact/);
assert.match(explanation, /sha256:a{64}/);
assert.match(explanation, /example-collector@1/);
assert.match(explanation, /exact_evidence_id_and_digest/);

const framework = select(2);
assert.match(framework, /framework-owner/);
assert.match(framework, /affirmative/);

const difference = select(3);
for (const expected of (
  ["Comparison context", "operation_id", "Scope changes", "scope-one",
   "Requirement changes", "objective-one", "Control changes", "check-one"]
)) {
  assert.match(difference, new RegExp(expected));
}

const capturePaths = process.argv.slice(2);
if (capturePaths.length) {
  const captures = capturePaths.map(capturePath => ({
    name: path.basename(capturePath),
    document: JSON.parse(fs.readFileSync(capturePath, "utf8")),
  }));
  assert.deepEqual(
    window.complianceReadBrowser.loadResponses(captures),
    { accepted: captures.length, rejected: 0 },
  );
  captures.forEach((capture, index) => {
    const rendered = select(documents.length + index);
    const schemaPattern = capture.document.schema.replace(/[./]/g, "\\$&");
    assert.match(rendered, new RegExp(schemaPattern));
  });
}

assert.deepEqual(
  window.complianceReadBrowser.loadResponses([{
    name: "raw-plan",
    document: { schema: "compliance.example/assessment-plan/v4" },
  }]),
  { accepted: 0, rejected: 1 },
);

console.log("browser projection rendering passed");

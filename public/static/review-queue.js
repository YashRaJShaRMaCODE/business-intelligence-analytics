import { reviewRowsToTsv } from "./review-queue.mjs";
import {
  normalizeReviewDecisions,
  reviewDecisionExport,
  reviewPageCounts,
  updateReviewDecisions,
  visibleReviewRows,
} from "./review-state.mjs";

const button = document.querySelector("#copy-review-page");
const status = document.querySelector("#copy-review-status");
const decisionFilter = document.querySelector("#review-decision-filter");
const decisionSummary = document.querySelector("#review-decision-summary");
const decisionStatus = document.querySelector("#review-decision-status");
const decisionEmpty = document.querySelector("#review-decision-empty");
const reviewRows = [...document.querySelectorAll(".queue-table tbody tr[data-review-key]")];
const snapshot = document.body.dataset.reviewVersion || "unknown";
const storageKey = `catalog-quality-review:v1:${snapshot}`;
let decisions = {};

try {
  decisions = normalizeReviewDecisions(JSON.parse(localStorage.getItem(storageKey) || "{}"));
} catch {
  decisions = {};
  if (decisionStatus) decisionStatus.textContent = "Saved decisions could not be read here; export a page copy to keep your work.";
}

function rowReference(row) {
  const cells = row.cells;
  return {
    key: row.dataset.reviewKey,
    sourceRecord: cells[0].textContent.trim(),
    title: cells[1].textContent.trim(),
    sourceId: cells[2].textContent.trim() === "—" ? "" : cells[2].textContent.trim(),
    type: cells[3].textContent.split("/")[0].trim(),
    releaseYear: cells[3].textContent.split("/")[1]?.trim() || "",
    flags: [...cells[4].querySelectorAll(".issue-tag")].map((tag) => tag.textContent.trim()),
  };
}

function saveDecisions(message) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(decisions));
    if (decisionStatus) decisionStatus.textContent = message;
  } catch {
    if (decisionStatus) decisionStatus.textContent = "Browser storage is unavailable; export a page copy to keep your work.";
  }
}

function applyDecisionFilter() {
  if (!reviewRows.length) return;
  const references = reviewRows.map(rowReference);
  const visible = visibleReviewRows(references, decisions, decisionFilter?.value || "any");
  const visibleKeys = new Set(visible.map((row) => row.key));
  for (const row of reviewRows) {
    const key = row.dataset.reviewKey;
    row.querySelector(".review-decision").value = decisions[key] || "open";
    row.hidden = !visibleKeys.has(key);
  }
  const counts = reviewPageCounts(references, decisions);
  if (decisionSummary) {
    decisionSummary.textContent = `This page: ${counts.open} not reviewed · ${counts.reviewed} reviewed · ${counts.corrected} source corrected · ${counts.source_check} need a source check.`;
  }
  if (decisionEmpty) decisionEmpty.hidden = visible.length > 0;
}

function downloadDecisions() {
  const payload = reviewDecisionExport(reviewRows.map(rowReference), decisions, snapshot);
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "catalog-quality-review-decisions.json";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  if (decisionStatus) decisionStatus.textContent = "Page decisions exported to this device. The source dataset was not changed.";
}

for (const row of reviewRows) {
  row.querySelector(".review-decision").addEventListener("change", (event) => {
    decisions = updateReviewDecisions(decisions, [rowReference(row)], event.target.value);
    saveDecisions("Decision saved in this browser only.");
    applyDecisionFilter();
  });
}

decisionFilter?.addEventListener("change", applyDecisionFilter);
document.querySelectorAll("[data-set-review]").forEach((button) => {
  button.addEventListener("click", () => {
    const visible = reviewRows.filter((row) => !row.hidden).map(rowReference);
    decisions = updateReviewDecisions(decisions, visible, button.dataset.setReview);
    saveDecisions(`Updated ${visible.length} visible decisions in this browser.`);
    applyDecisionFilter();
  });
});

document.querySelector("#export-review-decisions")?.addEventListener("click", downloadDecisions);
document.querySelector("#clear-review-decisions")?.addEventListener("click", () => {
  if (!window.confirm("Clear saved review decisions for this dataset on this device?")) return;
  decisions = {};
  try {
    localStorage.removeItem(storageKey);
    if (decisionStatus) decisionStatus.textContent = "Saved review decisions cleared from this browser.";
  } catch {
    if (decisionStatus) decisionStatus.textContent = "Could not clear browser storage.";
  }
  applyDecisionFilter();
});

applyDecisionFilter();

button?.addEventListener("click", async () => {
  const rows = reviewRows.filter((row) => !row.hidden).map(row => [
    row.cells[0].textContent,
    row.cells[2].textContent,
    row.cells[1].textContent,
    row.cells[4].textContent,
  ]);
  try {
    await navigator.clipboard.writeText(reviewRowsToTsv(rows));
    status.textContent = `Copied ${rows.length} visible review references.`;
  } catch {
    status.textContent = "Clipboard unavailable; use the review CSV export instead.";
  }
});

export const REVIEW_STATES = Object.freeze({
  open: "Not reviewed",
  reviewed: "Reviewed",
  corrected: "Source corrected",
  source_check: "Needs source check",
});

export function normalizeReviewDecisions(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return Object.fromEntries(Object.entries(value).filter(([key, status]) =>
    typeof key === "string" && key.length <= 500 && Object.hasOwn(REVIEW_STATES, status)));
}

export function reviewPageCounts(rows, decisions) {
  const counts = Object.fromEntries(Object.keys(REVIEW_STATES).map((status) => [status, 0]));
  for (const row of rows) {
    const status = REVIEW_STATES[decisions[row.key]] ? decisions[row.key] : "open";
    counts[status] += 1;
  }
  return counts;
}

export function visibleReviewRows(rows, decisions, filter = "any") {
  const status = Object.hasOwn(REVIEW_STATES, filter) ? filter : "any";
  return rows.filter((row) => status === "any" || (decisions[row.key] || "open") === status);
}

export function updateReviewDecisions(decisions, rows, status) {
  if (!Object.hasOwn(REVIEW_STATES, status)) return { ...decisions };
  return Object.fromEntries([
    ...Object.entries(decisions),
    ...rows.map((row) => [row.key, status]),
  ]);
}

export function reviewDecisionExport(rows, decisions, snapshot, exportedAt = new Date().toISOString()) {
  return {
    format: "catalog-quality-review-v1",
    snapshot,
    exported_at: exportedAt,
    decisions: rows.map((row) => ({
      source_record: row.sourceRecord,
      source_id: row.sourceId,
      title: row.title,
      type: row.type,
      release_year: row.releaseYear,
      review_flags: row.flags,
      decision: decisions[row.key] || "open",
    })),
  };
}

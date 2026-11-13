import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeReviewDecisions,
  reviewDecisionExport,
  reviewPageCounts,
  updateReviewDecisions,
  visibleReviewRows,
} from "../public/static/review-state.mjs";

const rows = [
  { key: "v1:1:a", sourceRecord: "1", sourceId: "a", title: "A title", type: "MOVIE", releaseYear: "2020", flags: ["Blank title"] },
  { key: "v1:2:b", sourceRecord: "2", sourceId: "b", title: "B title", type: "SHOW", releaseYear: "2021", flags: ["Invalid release year"] },
];

test("decision state accepts only known statuses and safely defaults unknown entries", () => {
  assert.deepEqual(normalizeReviewDecisions({ [rows[0].key]: "reviewed", bad: "toString", extra: null }), {
    [rows[0].key]: "reviewed",
  });
  assert.deepEqual(normalizeReviewDecisions("corrupt"), {});
});

test("page decisions can be bulk-updated, filtered, and counted", () => {
  const decisions = updateReviewDecisions({}, rows, "reviewed");
  const next = updateReviewDecisions(decisions, [rows[1]], "source_check");
  assert.deepEqual(visibleReviewRows(rows, next, "reviewed"), [rows[0]]);
  assert.deepEqual(visibleReviewRows(rows, next, "source_check"), [rows[1]]);
  assert.deepEqual(reviewPageCounts(rows, next), {
    open: 0, reviewed: 1, corrected: 0, source_check: 1,
  });
});

test("decision export contains source references and dispositions, not private notes", () => {
  const payload = reviewDecisionExport(rows, { [rows[0].key]: "corrected" }, "snapshot-1", "2026-11-13T00:00:00.000Z");
  assert.equal(payload.format, "catalog-quality-review-v1");
  assert.equal(payload.decisions[0].decision, "corrected");
  assert.equal(payload.decisions[1].decision, "open");
  assert.equal(payload.decisions[0].source_record, "1");
  assert.equal(JSON.stringify(payload).includes("private"), false);
  assert.deepEqual(Object.keys(payload.decisions[0]), [
    "source_record", "source_id", "title", "type", "release_year", "review_flags", "decision",
  ]);
});

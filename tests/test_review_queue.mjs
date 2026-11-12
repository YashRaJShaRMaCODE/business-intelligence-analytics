import assert from "node:assert/strict";
import test from "node:test";
import { reviewRowsToTsv } from "../public/static/review-queue.mjs";

test("formats filtered review references as spreadsheet-ready TSV", () => {
  assert.equal(reviewRowsToTsv([["12", "id-12", "A title", "Blank title"]]),
    "Source record\tSource ID\tTitle\tReview flags\n12\tid-12\tA title\tBlank title");
});

test("flattens cell breaks and escapes spreadsheet formulas", () => {
  assert.equal(reviewRowsToTsv([["2", "=1+1", "@SUM(A1)", "Repeated\tID"]]),
    "Source record\tSource ID\tTitle\tReview flags\n2\t'=1+1\t'@SUM(A1)\tRepeated ID");
});

import { reviewRowsToTsv } from "./review-queue.mjs";

const button = document.querySelector("#copy-review-page");
const status = document.querySelector("#copy-review-status");

button?.addEventListener("click", async () => {
  const rows = [...document.querySelectorAll(".queue-table tbody tr")].map(row => [
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

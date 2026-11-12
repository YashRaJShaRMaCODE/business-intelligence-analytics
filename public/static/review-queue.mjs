const safeCell = value => {
  const text = String(value ?? "").replace(/[\t\r\n]+/g, " ").trim();
  return /^[=+\-@]/.test(text) ? `'${text}` : text;
};

export function reviewRowsToTsv(rows) {
  return [["Source record", "Source ID", "Title", "Review flags"], ...rows]
    .map(row => row.map(safeCell).join("\t"))
    .join("\n");
}

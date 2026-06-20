export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') quoted = true;
    else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((c) => c.length > 0));
}

export function csvObjects(text: string): Array<Record<string, string>> {
  const rows = parseCsv(text);
  const header = rows.shift();
  if (!header) return [];
  return rows.map((row) => {
    const obj: Record<string, string> = {};
    for (let i = 0; i < header.length; i += 1) obj[header[i]] = row[i] ?? "";
    return obj;
  });
}

export function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function numericEntries(obj: Record<string, unknown>): Array<[string, number]> {
  return Object.entries(obj).flatMap(([key, value]) => {
    const n = asNumber(value);
    return n === null ? [] : [[key, n] as [string, number]];
  });
}

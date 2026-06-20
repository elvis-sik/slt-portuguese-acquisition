import { describe, expect, it } from "vitest";
import { csvObjects } from "@/lib/parse";

describe("csvObjects", () => {
  it("parses quoted registry notes", () => {
    const rows = csvObjects('run_id,status,notes\nr1,completed,"kept, with comma"\n');
    expect(rows).toEqual([{ run_id: "r1", status: "completed", notes: "kept, with comma" }]);
  });
});

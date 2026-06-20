import { describe, expect, it } from "vitest";
import { getSnapshot } from "@/lib/snapshot";

describe("dashboard snapshot", () => {
  it("indexes current infrastructure-gate artifacts", () => {
    const snapshot = getSnapshot();
    expect(snapshot.runs.some((run) => run.id === "infrastructure-gate-consolidated")).toBe(true);
    expect(snapshot.jobs.some((job) => job.id === "infra-gate-sampler-20260620T0200Z")).toBe(true);
    expect(snapshot.metrics.some((metric) => metric.name === "tokens_per_second")).toBe(true);
    expect(snapshot.metrics.some((metric) => metric.runId === "infrastructure-gate-consolidated")).toBe(true);
    expect(snapshot.artifacts.some((artifact) => artifact.path.endsWith("project_estimate.json"))).toBe(true);
  });
});

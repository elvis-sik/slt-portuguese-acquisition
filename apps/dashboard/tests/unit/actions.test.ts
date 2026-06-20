import { describe, expect, it } from "vitest";
import { validateAction } from "@/lib/action-registry";

describe("action registry", () => {
  it("accepts typed bounded-job actions", () => {
    const action = validateAction("startBoundedJob", {
      jobName: "probe-1",
      templateId: "harmless-status",
      maxHours: "0.25",
      maxEpochs: "2",
      maxSteps: "1200",
      maxTokens: "4096"
    });
    expect(action.args.jobName).toBe("probe-1");
    expect(action.args.maxHours).toBe(0.25);
    expect(action.args.maxEpochs).toBe(2);
    expect(action.args.maxSteps).toBe(1200);
    expect(action.args.maxTokens).toBe(4096);
  });

  it("rejects unsafe job names", () => {
    expect(() =>
      validateAction("startBoundedJob", {
        jobName: "probe; rm -rf",
        templateId: "harmless-status",
        maxHours: "0.25"
      })
    ).toThrow();
  });

  it("rejects unknown actions", () => {
    expect(() => validateAction("shell", {})).toThrow(/Unknown action/);
  });

  it("coerces orchestrator launch args and defaults", () => {
    const action = validateAction("startOrchestrator", { deadlineHours: "8", soft: "35", hard: "50" });
    expect(action.args.deadlineHours).toBe(8);
    expect(action.args.soft).toBe(35);
    expect(action.args.hard).toBe(50);
    expect(action.args.autoStop).toBe(true);
  });

  it("accepts a bare stop-orchestrator action", () => {
    const action = validateAction("stopOrchestrator", {});
    expect(action.type).toBe("stopOrchestrator");
    expect(action.args.kill).toBe(false);
  });

  it("allows bounded-job budgets above the old 2h cap but guards runaway windows", () => {
    expect(validateAction("startBoundedJob", { jobName: "final", templateId: "harmless-status", maxHours: "6" }).args.maxHours).toBe(6);
    expect(() =>
      validateAction("startBoundedJob", { jobName: "final", templateId: "harmless-status", maxHours: "99" })
    ).toThrow();
  });
});

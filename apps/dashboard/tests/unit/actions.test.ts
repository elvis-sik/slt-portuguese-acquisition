import { describe, expect, it } from "vitest";
import { validateAction } from "@/lib/action-registry";

describe("action registry", () => {
  it("accepts typed bounded-job actions", () => {
    const action = validateAction("startBoundedJob", {
      jobName: "probe-1",
      templateId: "harmless-status",
      maxHours: "0.25"
    });
    expect(action.args.jobName).toBe("probe-1");
    expect(action.args.maxHours).toBe(0.25);
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
});

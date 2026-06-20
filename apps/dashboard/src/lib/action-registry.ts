import { z } from "zod";
import type { ActionDefinition } from "./types";

const safeName = z.string().regex(/^[A-Za-z0-9._-]+$/).min(1).max(120);

export const startVmSchema = z.object({});
export const stopVmSchema = z.object({});
export const syncNowSchema = z.object({
  direction: z.enum(["pull", "push-control"]).default("pull")
});
export const startBoundedJobSchema = z.object({
  jobName: safeName,
  templateId: z.enum(["harmless-status", "remote-probe"]),
  // Per-step budgets now come from the orchestrator planner and legitimately exceed 2h
  // (the final run is ~6h). Keep an upper guard so a typo can't request a runaway window.
  maxHours: z.coerce.number().positive().max(12).default(0.25),
  maxEpochs: z.coerce.number().int().positive().max(1000).optional(),
  maxSteps: z.coerce.number().int().positive().max(10_000_000).optional(),
  maxTokens: z.coerce.number().int().positive().max(1_000_000_000).optional()
});
export const stopJobSchema = z.object({ jobName: safeName });
export const startOrchestratorSchema = z.object({
  deadlineHours: z.coerce.number().positive().max(24).default(8),
  soft: z.coerce.number().positive().max(1000).default(35),
  hard: z.coerce.number().positive().max(1000).default(50),
  autoStop: z.coerce.boolean().default(true)
});
export const stopOrchestratorSchema = z.object({
  kill: z.coerce.boolean().default(false)
});
export const runControlSchema = z.object({
  runId: safeName,
  note: z.string().max(500).optional().default("")
});
export const forkFromCheckpointSchema = z.object({
  runId: safeName,
  checkpointId: safeName,
  newRunId: safeName.optional()
});

export const actionSchemas = {
  startVm: startVmSchema,
  stopVm: stopVmSchema,
  syncNow: syncNowSchema,
  startBoundedJob: startBoundedJobSchema,
  stopJob: stopJobSchema,
  checkpointNow: runControlSchema,
  pauseRun: runControlSchema,
  resumeRun: runControlSchema,
  forkFromCheckpoint: forkFromCheckpointSchema,
  startOrchestrator: startOrchestratorSchema,
  stopOrchestrator: stopOrchestratorSchema
};

export type ActionType = keyof typeof actionSchemas;

export const actionDefinitions: ActionDefinition[] = [
  {
    type: "startVm",
    label: "Start VM",
    description: "Start the configured GCP worker.",
    dangerous: false,
    fields: []
  },
  {
    type: "stopVm",
    label: "Stop VM",
    description: "Stop the configured GCP worker.",
    dangerous: false,
    fields: []
  },
  {
    type: "syncNow",
    label: "Sync",
    description: "Pull small live artifacts from the remote worker.",
    dangerous: false,
    fields: [
      {
        name: "direction",
        label: "Direction",
        type: "select",
        options: [
          { label: "Pull artifacts", value: "pull" },
          { label: "Push controls", value: "push-control" }
        ]
      }
    ]
  },
  {
    type: "startBoundedJob",
    label: "Start Job",
    description: "Launch a committed bounded remote job template.",
    dangerous: false,
    fields: [
      { name: "jobName", label: "Job name", type: "text", required: true, placeholder: "dashboard-probe" },
      {
        name: "templateId",
        label: "Template",
        type: "select",
        required: true,
        options: [
          { label: "Harmless status", value: "harmless-status" },
          { label: "Remote probe", value: "remote-probe" }
        ]
      },
      { name: "maxHours", label: "Max wall-clock hours", type: "number", required: true, placeholder: "0.25" },
      { name: "maxEpochs", label: "Max epochs", type: "number", placeholder: "optional" },
      { name: "maxSteps", label: "Max steps", type: "number", placeholder: "optional" },
      { name: "maxTokens", label: "Max tokens", type: "number", placeholder: "optional" }
    ]
  },
  {
    type: "stopJob",
    label: "Stop Job",
    description: "Send TERM to a bounded remote job.",
    dangerous: true,
    fields: [{ name: "jobName", label: "Job name", type: "text", required: true }]
  },
  {
    type: "checkpointNow",
    label: "Checkpoint",
    description: "Request a cooperative checkpoint from a run.",
    dangerous: false,
    fields: [
      { name: "runId", label: "Run id", type: "text", required: true },
      { name: "note", label: "Note", type: "text" }
    ]
  },
  {
    type: "pauseRun",
    label: "Pause",
    description: "Request cooperative pause.",
    dangerous: true,
    fields: [
      { name: "runId", label: "Run id", type: "text", required: true },
      { name: "note", label: "Note", type: "text" }
    ]
  },
  {
    type: "resumeRun",
    label: "Resume",
    description: "Request cooperative resume.",
    dangerous: false,
    fields: [
      { name: "runId", label: "Run id", type: "text", required: true },
      { name: "note", label: "Note", type: "text" }
    ]
  },
  {
    type: "forkFromCheckpoint",
    label: "Fork",
    description: "Create a new run lineage from a checkpoint.",
    dangerous: false,
    fields: [
      { name: "runId", label: "Run id", type: "text", required: true },
      { name: "checkpointId", label: "Checkpoint id", type: "text", required: true },
      { name: "newRunId", label: "New run id", type: "text" }
    ]
  },
  {
    type: "startOrchestrator",
    label: "Start Orchestrator",
    description: "Launch the unattended planner+executor orchestrator on the remote VM.",
    dangerous: true,
    fields: [
      { name: "deadlineHours", label: "Deadline (hours)", type: "number", required: true, placeholder: "8" },
      { name: "soft", label: "Soft cap (USD)", type: "number", placeholder: "35" },
      { name: "hard", label: "Hard cap (USD)", type: "number", placeholder: "50" }
    ]
  },
  {
    type: "stopOrchestrator",
    label: "Stop Orchestrator",
    description: "Cooperatively halt the orchestrator at its next tick (optionally TERM the process).",
    dangerous: true,
    fields: []
  }
];

export function validateAction(type: string, args: unknown): { type: ActionType; args: Record<string, unknown> } {
  if (!(type in actionSchemas)) throw new Error(`Unknown action type: ${type}`);
  const actionType = type as ActionType;
  const parsed = actionSchemas[actionType].parse(args) as Record<string, unknown>;
  return { type: actionType, args: parsed };
}

export type HealthState = "ok" | "warn" | "fail" | "unknown";
export type ActionStatus = "pending" | "running" | "completed" | "failed";

export interface DashboardConfig {
  repoRoot: string;
  dataDir: string;
  dbPath: string;
  envFile: string;
  projectId: string | null;
  zone: string | null;
  vmName: string | null;
  sshHost: string | null;
  remoteRepoPath: string;
  hourlyRateUsd: number;
}

export interface HealthRecord {
  key: string;
  state: HealthState;
  updatedAt: string;
  data: Record<string, unknown>;
}

export interface RunRecord {
  id: string;
  phase: string;
  status: string;
  condition: string;
  model: string;
  seed: string;
  gitCommit: string;
  configPath: string;
  startUtc: string;
  endUtc: string;
  gpuHours: number | null;
  estimatedCostUsd: number | null;
  outputDir: string;
  notes: string;
  parentRunId: string | null;
  parentCheckpointId: string | null;
  checkpointCount: number;
  latestMetrics: Record<string, number>;
  lastHeartbeat: string | null;
}

export interface JobRecord {
  id: string;
  status: string;
  pid: string;
  startUtc: string;
  endUtc: string;
  exitCode: string;
  processAlive: boolean;
  command: string;
  logPath: string;
  outputDir: string;
  lastLogLine: string;
  updatedAt: string;
}

export interface MetricPoint {
  runId: string;
  name: string;
  step: number | null;
  value: number;
  timestampUtc: string | null;
  sourcePath: string;
}

export interface ArtifactRecord {
  path: string;
  kind: string;
  sizeBytes: number;
  mtimeMs: number;
  runId: string | null;
  phase: string | null;
}

export interface ActionRecord {
  id: string;
  type: string;
  status: ActionStatus;
  createdAt: string;
  startedAt: string | null;
  endedAt: string | null;
  args: Record<string, unknown>;
  stdout: string;
  stderr: string;
  exitCode: number | null;
  message: string;
}

export interface Snapshot {
  generatedAt: string;
  config: DashboardConfig;
  summary: {
    runCount: number;
    jobCount: number;
    runningJobCount: number;
    actionCount: number;
    pendingActionCount: number;
    estimatedCostUsd: number | null;
    projectedMedianHours: number | null;
  };
  health: HealthRecord[];
  runs: RunRecord[];
  jobs: JobRecord[];
  metrics: MetricPoint[];
  artifacts: ArtifactRecord[];
  actions: ActionRecord[];
  currentStatus: Record<string, unknown> | null;
  decisionLogTail: string;
  registryRows: number;
}

export interface ActionDefinition {
  type: string;
  label: string;
  description: string;
  dangerous: boolean;
  fields: Array<{
    name: string;
    label: string;
    type: "text" | "number" | "select";
    required?: boolean;
    placeholder?: string;
    options?: Array<{ label: string; value: string }>;
  }>;
}

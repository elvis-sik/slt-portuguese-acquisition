"use client";

import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  AlertTriangle,
  Bot,
  Box,
  ChartSpline,
  CheckCircle2,
  CirclePause,
  GitBranch,
  History,
  Loader2,
  Pause,
  Play,
  RefreshCcw,
  Server,
  Square,
  Terminal,
  Workflow,
  Zap
} from "lucide-react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis
} from "recharts";
import type { ActionDefinition, ArtifactRecord, HealthRecord, JobRecord, MetricPoint, RunRecord, Snapshot } from "@/lib/types";

const queryClient = new QueryClient();

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

function useSnapshot() {
  const query = useQuery({
    queryKey: ["snapshot"],
    queryFn: () => fetchJson<Snapshot>("/api/snapshot"),
    refetchInterval: 10000
  });
  useEffect(() => {
    const events = new EventSource("/api/events");
    events.addEventListener("snapshot", (event) => {
      queryClient.setQueryData(["snapshot"], JSON.parse((event as MessageEvent).data));
    });
    events.onerror = () => events.close();
    return () => events.close();
  }, []);
  return query;
}

export function DashboardShell() {
  return (
    <QueryClientProvider client={queryClient}>
      <Tooltip.Provider delayDuration={180}>
        <Dashboard />
      </Tooltip.Provider>
    </QueryClientProvider>
  );
}

function Dashboard() {
  const { data, isLoading, error } = useSnapshot();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const defaultRun =
    data?.runs.find((run) => Object.keys(run.latestMetrics).length > 0) ??
    data?.runs.find((run) => run.status === "completed") ??
    data?.runs[0] ??
    null;
  const selectedRun = data?.runs.find((run) => run.id === selectedRunId) ?? defaultRun;

  if (isLoading) {
    return (
      <main className="grid min-h-screen place-items-center">
        <div className="flex items-center gap-3 text-sm text-moss">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading dashboard
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="grid min-h-screen place-items-center p-8">
        <div className="max-w-xl rounded-md border border-danger/30 bg-white p-5 text-sm text-danger">
          {error instanceof Error ? error.message : "Dashboard snapshot unavailable"}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <Header snapshot={data} />
      <div className="mx-auto grid max-w-[1800px] gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_420px]">
        <section className="space-y-4">
          <StatusStrip snapshot={data} />
          <Tabs.Root defaultValue="orchestrator" className="rounded-md border border-line bg-white">
            <Tabs.List className="flex flex-wrap border-b border-line bg-panel">
              <Tab value="orchestrator" icon={<Workflow className="h-4 w-4" />} label="Orchestrator" />
              <Tab value="runs" icon={<History className="h-4 w-4" />} label="Experiment runs" />
              <Tab value="figures" icon={<ChartSpline className="h-4 w-4" />} label="Figures" />
              <Tab value="metrics" icon={<Activity className="h-4 w-4" />} label="Metrics" />
              <Tab value="logs" icon={<Terminal className="h-4 w-4" />} label="Jobs" />
              <Tab value="agent" icon={<Bot className="h-4 w-4" />} label="Agent log" />
              <Tab value="artifacts" icon={<Box className="h-4 w-4" />} label="Artifacts" />
            </Tabs.List>
            <Tabs.Content value="orchestrator" className="p-4">
              <p className="mb-3 text-xs text-moss">
                The overnight control loop — the spine of this run. Each <span className="text-ink">tick</span>, the planner picks the next action and the
                executor carries it out, producing the <span className="text-ink">experiment runs</span> and <span className="text-ink">agent logs</span> in the other tabs.
              </p>
              <OrchestratorView snapshot={data} />
            </Tabs.Content>
            <Tabs.Content value="runs" className="p-4">
              <p className="mb-3 text-xs text-moss">
                Training, sampler, and evaluation runs the executor recorded in the registry, produced during orchestrator ticks. <span className="text-ink">Phase</span> is the orchestrator stage that produced each one.
              </p>
              <RunTable runs={data.runs} selected={selectedRun?.id ?? null} onSelect={setSelectedRunId} />
              {selectedRun ? <RunDetail run={selectedRun} snapshot={data} /> : null}
            </Tabs.Content>
            <Tabs.Content value="figures" className="p-4">
              <FigureDeck snapshot={data} selectedRun={selectedRun} />
            </Tabs.Content>
            <Tabs.Content value="metrics" className="p-4">
              <MetricGrid metrics={data.metrics} selectedRun={selectedRun} />
            </Tabs.Content>
            <Tabs.Content value="logs" className="p-4">
              <p className="mb-3 text-xs text-moss">Bounded job processes (the detached runners under results/_jobs) that experiment runs execute through.</p>
              <JobTable jobs={data.jobs} />
            </Tabs.Content>
            <Tabs.Content value="agent" className="p-4">
              <p className="mb-3 text-xs text-moss">
                Raw transcript of each agent call (planner + executor), one per orchestrator tick. The readable view shows the agent&apos;s messages, commands, and structured decision.
              </p>
              <AgentLogPanel />
            </Tabs.Content>
            <Tabs.Content value="artifacts" className="p-4">
              <ArtifactTable artifacts={data.artifacts} />
            </Tabs.Content>
          </Tabs.Root>
        </section>
        <aside className="space-y-4">
          <ControlCenter snapshot={data} selectedRun={selectedRun} />
          <DecisionCockpit snapshot={data} />
          <ActionHistory snapshot={data} />
        </aside>
      </div>
    </main>
  );
}

function Header({ snapshot }: { snapshot: Snapshot }) {
  return (
    <header className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-[1800px] flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div>
          <h1 className="text-lg font-semibold tracking-normal text-ink">SLT Portuguese Control</h1>
          <div className="mt-1 font-mono text-xs text-moss">{snapshot.config.repoRoot}</div>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-moss">
          <span>{new Date(snapshot.generatedAt).toLocaleTimeString()}</span>
          <span className="rounded border border-line px-2 py-1">{snapshot.config.sshHost ?? "no ssh host"}</span>
        </div>
      </div>
    </header>
  );
}

function Tab({ value, icon, label }: { value: string; icon: React.ReactNode; label: string }) {
  return (
    <Tabs.Trigger
      value={value}
      className="focus-ring flex h-11 items-center gap-2 border-r border-line px-4 text-sm text-moss data-[state=active]:bg-white data-[state=active]:text-ink"
    >
      {icon}
      {label}
    </Tabs.Trigger>
  );
}

function StatusStrip({ snapshot }: { snapshot: Snapshot }) {
  const status = (key: string) => snapshot.health.find((h) => h.key === key);
  const vm = status("vm");
  const remote = status("remote");
  const ssh = status("ssh");
  const worker = status("worker");
  const sync = status("sync");
  const vmStatus = textValue(vm?.data.status);
  const vmRunning = vmStatus === "RUNNING";
  const vmKnownStopped = Boolean(vmStatus && !vmRunning);
  const remoteCommit = textValue(remote?.data.git_commit);
  const items = [
    { label: "Worker", state: worker?.state ?? "unknown", value: worker?.updatedAt ? `heartbeat ${timeOnly(worker.updatedAt)}` : "not seen" },
    { label: "VM", state: vmRunning ? "ok" : vmKnownStopped ? "idle" : vm?.state ?? "unknown", value: vmStatus || "not checked" },
    { label: "SSH", state: vmKnownStopped ? "idle" : ssh?.state ?? "unknown", value: sshValue(ssh, vmKnownStopped) },
    { label: "Remote", state: vmKnownStopped ? "idle" : remote?.state ?? "unknown", value: remoteValue(remote, remoteCommit, vmKnownStopped) },
    { label: "Sync", state: vmKnownStopped ? "idle" : sync?.state ?? "unknown", value: syncValue(sync, vmKnownStopped) },
    { label: "Spend", state: "ok", value: dollars(snapshot.summary.estimatedCostUsd) }
  ];
  return (
    <section className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border border-line bg-white p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase text-moss">{item.label}</span>
            <HealthDot state={item.state} />
          </div>
          <div className="mt-2 truncate font-mono text-sm text-ink">{item.value ?? "unknown"}</div>
        </div>
      ))}
    </section>
  );
}

function textValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function timeOnly(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleTimeString();
}

function sshValue(ssh: HealthRecord | undefined, vmOff: boolean): string {
  if (vmOff) return "VM off";
  if (ssh?.state === "ok") return "connected";
  if (ssh?.state === "warn") return "connect failed";
  return textValue(ssh?.data.message) || "not checked";
}

function remoteValue(remote: HealthRecord | undefined, commit: string, vmOff: boolean): string {
  if (vmOff) return "VM off";
  if (remote?.state === "ok") return commit ? commit.slice(0, 12) : "connected";
  if (remote?.state === "warn") return "probe failed";
  return textValue(remote?.data.message) || "not checked";
}

function syncValue(sync: HealthRecord | undefined, vmOff: boolean): string {
  if (vmOff) return "idle";
  if (sync?.state === "ok") return sync.updatedAt ? `last ${timeOnly(sync.updatedAt)}` : "synced";
  if (sync?.state === "warn") return "failed";
  return textValue(sync?.data.message) || "not run";
}

function HealthDot({ state }: { state: string }) {
  const className =
    state === "ok"
      ? "bg-moss"
      : state === "warn"
        ? "bg-caution"
        : state === "fail"
          ? "bg-danger"
          : "bg-line";
  return <span className={`h-2.5 w-2.5 rounded-full ${className}`} />;
}

function IconButton({
  label,
  icon,
  onClick,
  disabled
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          className="focus-ring grid h-9 w-9 place-items-center rounded-md border border-line bg-white text-ink disabled:cursor-not-allowed disabled:opacity-40"
          onClick={onClick}
          disabled={disabled}
          type="button"
          aria-label={label}
        >
          {icon}
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="rounded bg-ink px-2 py-1 text-xs text-white" sideOffset={6}>
          {label}
          <Tooltip.Arrow className="fill-ink" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function RunTable({
  runs,
  selected,
  onSelect
}: {
  runs: RunRecord[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-left text-sm">
        <thead className="border-b border-line text-xs uppercase text-moss">
          <tr>
            <th className="py-2 pr-3">Run</th>
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3">Phase</th>
            <th className="py-2 pr-3">Condition</th>
            <th className="py-2 pr-3">Model</th>
            <th className="py-2 pr-3">GPU h</th>
            <th className="py-2 pr-3">Cost</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.id}
              className={`cursor-pointer border-b border-line/70 ${selected === run.id ? "bg-panel" : "hover:bg-panel/60"}`}
              onClick={() => onSelect(run.id)}
            >
              <td className="max-w-[280px] truncate py-2 pr-3 font-mono text-xs">{run.id}</td>
              <td className="py-2 pr-3"><StatusBadge status={run.status} /></td>
              <td className="py-2 pr-3">{run.phase}</td>
              <td className="py-2 pr-3">{run.condition}</td>
              <td className="py-2 pr-3">{run.model}</td>
              <td className="py-2 pr-3 font-mono text-xs">{num(run.gpuHours)}</td>
              <td className="py-2 pr-3 font-mono text-xs">{dollars(run.estimatedCostUsd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunDetail({ run, snapshot }: { run: RunRecord; snapshot: Snapshot }) {
  const jobs = snapshot.jobs.filter((job) => job.id === run.id || run.notes.includes(job.id));
  const lineage = snapshot.runs.filter((candidate) => candidate.parentRunId === run.id || candidate.id === run.parentRunId);
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-3">
      <div className="rounded-md border border-line bg-panel p-3">
        <div className="text-xs uppercase text-moss">Latest metrics</div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
          {Object.entries(run.latestMetrics).slice(0, 8).map(([key, value]) => (
            <div key={key}>
              <dt className="truncate text-xs text-moss">{key}</dt>
              <dd className="font-mono text-ink">{Number(value).toPrecision(5)}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="rounded-md border border-line bg-panel p-3">
        <div className="text-xs uppercase text-moss">Lineage</div>
        <div className="mt-3 space-y-2 font-mono text-xs">
          <div>{run.parentRunId ? `${run.parentRunId} -> ${run.id}` : run.id}</div>
          {lineage.map((item) => (
            <div key={item.id} className="flex items-center gap-2 text-moss">
              <GitBranch className="h-3.5 w-3.5" />
              {item.id}
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-md border border-line bg-panel p-3">
        <div className="text-xs uppercase text-moss">Related jobs</div>
        <div className="mt-3 space-y-2 text-xs">
          {jobs.length ? jobs.map((job) => <div key={job.id} className="font-mono">{job.id}: {job.status}</div>) : <div className="text-moss">none</div>}
        </div>
      </div>
    </div>
  );
}

type FigureSpec = {
  id: string;
  title: string;
  family: string;
  yLabel: string;
  keys: string[];
  colors: string[];
};

type FigureSeries = {
  key: string;
  label: string;
  color: string;
  metricName: string;
  points: Array<{ x: number; value: number }>;
};

const FIGURE_SPECS: FigureSpec[] = [
  {
    id: "loss",
    title: "Figure 1a target loss and BPB",
    family: "behavior",
    yLabel: "loss / BPB",
    keys: [
      "target_validation_bits_per_byte",
      "validation_bits_per_byte",
      "eval_bpb",
      "val_bpb",
      "bpb",
      "validation_loss",
      "eval_loss",
      "train_loss",
      "loss",
      "last_loss"
    ],
    colors: ["#006d77", "#d97706", "#53745c", "#6d28d9"]
  },
  {
    id: "grammar",
    title: "Figure 1b grammar and lexical probes",
    family: "behavior",
    yLabel: "margin / accuracy",
    keys: [
      "grammar_logprob_margin",
      "grammar_margin",
      "grammar_minimal_pair_accuracy_percent",
      "grammar_accuracy",
      "lexical_probe_accuracy_percent",
      "lexical_accuracy"
    ],
    colors: ["#0f766e", "#be123c", "#7c3aed", "#ca8a04"]
  },
  {
    id: "llc",
    title: "Figure 1c LLC trajectory",
    family: "geometry",
    yLabel: "LLC diagnostic",
    keys: ["normalized_llc_ratio_to_start", "llc_mean", "llc", "local_learning_coefficient", "llc_std"],
    colors: ["#1d4ed8", "#0891b2", "#9333ea", "#475569"]
  },
  {
    id: "sampler",
    title: "Figure S1 sampler diagnostics",
    family: "diagnostic",
    yLabel: "localized loss / trace",
    keys: [
      "sampling_loss",
      "sampling_loss_micro",
      "chain_loss",
      "init_loss",
      "center_loss",
      "seconds_per_chain_step_estimate",
      "peak_memory_bytes"
    ],
    colors: ["#b45309", "#0f766e", "#dc2626", "#2563eb"]
  }
];

function FigureDeck({ snapshot, selectedRun }: { snapshot: Snapshot; selectedRun: RunRecord | null }) {
  const selectedRunIds = useMemo(() => {
    const ids = new Set<string>();
    if (selectedRun) ids.add(selectedRun.id);
    for (const run of snapshot.runs) {
      if (run.status === "completed" && Object.keys(run.latestMetrics).length > 0) ids.add(run.id);
    }
    return ids;
  }, [snapshot.runs, selectedRun]);
  const selectedMetrics = useMemo(
    () => snapshot.metrics.filter((metric) => selectedRunIds.has(metric.runId)),
    [snapshot.metrics, selectedRunIds]
  );
  const figureCards = useMemo(
    () => FIGURE_SPECS.map((spec) => buildFigureSeries(spec, selectedMetrics, snapshot.runs)),
    [selectedMetrics, snapshot.runs]
  );
  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-4">
        {FIGURE_SPECS.map((spec) => (
          <div key={spec.id} className="rounded-md border border-line bg-panel p-3">
            <div className="text-xs uppercase text-moss">{spec.family}</div>
            <div className="mt-1 text-sm font-semibold">{spec.title}</div>
          </div>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {FIGURE_SPECS.map((spec, index) => (
          <ReportFigureCard
            key={spec.id}
            spec={spec}
            series={figureCards[index]}
            selectedRun={selectedRun}
            fallbackNames={spec.keys.slice(0, 5)}
          />
        ))}
      </div>
    </div>
  );
}

function buildFigureSeries(spec: FigureSpec, metrics: MetricPoint[], runs: RunRecord[]): FigureSeries[] {
  const runLabels = new Map(runs.map((run) => [run.id, shortRunLabel(run)]));
  const out: FigureSeries[] = [];
  for (const key of spec.keys) {
    const pointsByRun = new Map<string, MetricPoint[]>();
    for (const metric of metrics) {
      if (!metricNameMatches(metric.name, key)) continue;
      if (!pointsByRun.has(metric.runId)) pointsByRun.set(metric.runId, []);
      pointsByRun.get(metric.runId)!.push(metric);
    }
    for (const [runId, points] of pointsByRun) {
      if (!points.length) continue;
      const color = spec.colors[out.length % spec.colors.length];
      const cleanPoints = downsample(
        points
          .map((point, i) => ({ x: point.step ?? i, value: point.value }))
          .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.value))
          .sort((a, b) => a.x - b.x),
        220
      );
      if (!cleanPoints.length) continue;
      out.push({
        key: `s${out.length}`,
        label: `${runLabels.get(runId) ?? runId} · ${key}`,
        color,
        metricName: key,
        points: cleanPoints
      });
      if (out.length >= 6) return out;
    }
  }
  return out;
}

function ReportFigureCard({
  spec,
  series,
  selectedRun,
  fallbackNames
}: {
  spec: FigureSpec;
  series: FigureSeries[];
  selectedRun: RunRecord | null;
  fallbackNames: string[];
}) {
  const chartData = useMemo(() => toChartData(series), [series]);
  const referenceX = useMemo(() => estimatedTransitionX(series), [series]);
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase text-moss">live real-data figure</div>
          <h3 className="mt-1 text-base font-semibold text-ink">{spec.title}</h3>
        </div>
        <span className="rounded border border-line bg-panel px-2 py-1 font-mono text-xs text-moss">
          {selectedRun?.id ?? "all runs"}
        </span>
      </div>
      <div className="h-[330px] rounded-md border border-line bg-panel p-3">
        {series.length ? (
          <ResponsiveContainer width="100%" height="100%" minWidth={240} minHeight={240}>
            <LineChart data={chartData} margin={{ top: 10, right: 18, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#d8ded5" strokeDasharray="3 3" />
              <XAxis
                dataKey="x"
                tick={{ fontSize: 11 }}
                tickFormatter={(value) => compactNumber(Number(value))}
                type="number"
                domain={["dataMin", "dataMax"]}
              />
              <YAxis tick={{ fontSize: 11 }} width={74} label={{ value: spec.yLabel, angle: -90, position: "insideLeft", fontSize: 11 }} />
              <ChartTooltip formatter={(value, name) => [compactNumber(Number(value)), String(name)]} labelFormatter={(value) => `step ${compactNumber(Number(value))}`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {referenceX !== null ? <ReferenceLine x={referenceX} stroke="#b45309" strokeDasharray="4 4" /> : null}
              {series.map((item) => (
                <Line
                  key={item.key}
                  dataKey={item.key}
                  name={item.label}
                  type="monotone"
                  stroke={item.color}
                  strokeWidth={2.4}
                  dot={item.points.length < 16}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <div className="text-sm font-medium text-ink">Waiting for {spec.family} metrics</div>
              <div className="mt-2 max-w-md font-mono text-xs text-moss">{fallbackNames.join(", ")}</div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function toChartData(series: FigureSeries[]): Array<Record<string, number | null>> {
  const rows = new Map<number, Record<string, number | null>>();
  for (const item of series) {
    for (const point of item.points) {
      const x = Number(point.x.toFixed(6));
      const row = rows.get(x) ?? { x };
      row[item.key] = point.value;
      rows.set(x, row);
    }
  }
  return [...rows.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, row]) => row);
}

function metricNameMatches(actual: string, wanted: string): boolean {
  const a = actual.toLowerCase();
  const w = wanted.toLowerCase();
  return a === w || a.endsWith(`_${w}`) || (w.length > 6 && a.includes(w));
}

function shortRunLabel(run: RunRecord): string {
  if (run.condition) return run.condition.replace(/_/g, " ");
  return run.id.length > 28 ? `${run.id.slice(0, 25)}...` : run.id;
}

function downsample<T>(points: T[], limit: number): T[] {
  if (points.length <= limit) return points;
  const stride = Math.ceil(points.length / limit);
  return points.filter((_, index) => index % stride === 0 || index === points.length - 1);
}

function estimatedTransitionX(series: FigureSeries[]): number | null {
  const grammar = series.find((item) => item.metricName.includes("grammar") && item.points.length >= 4);
  if (!grammar) return null;
  let bestX: number | null = null;
  let bestSlope = -Infinity;
  for (let i = 1; i < grammar.points.length; i += 1) {
    const prev = grammar.points[i - 1];
    const current = grammar.points[i];
    const dx = current.x - prev.x;
    if (dx <= 0) continue;
    const slope = (current.value - prev.value) / dx;
    if (slope > bestSlope) {
      bestSlope = slope;
      bestX = current.x;
    }
  }
  return bestX;
}

function MetricGrid({ metrics, selectedRun }: { metrics: MetricPoint[]; selectedRun: RunRecord | null }) {
  const grouped = useMemo(() => {
    const selected = selectedRun ? metrics.filter((metric) => metric.runId === selectedRun.id) : metrics;
    const groups = new Map<string, MetricPoint[]>();
    for (const metric of selected) {
      if (!groups.has(metric.name)) groups.set(metric.name, []);
      groups.get(metric.name)!.push(metric);
    }
    return [...groups.entries()].slice(0, 6).map(([name, points]) => ({
      name,
      points: points
        .map((point, i) => ({ x: point.step ?? i, value: point.value }))
        .sort((a, b) => Number(a.x) - Number(b.x))
    }));
  }, [metrics, selectedRun]);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {grouped.map((group) => (
        <div key={group.name} className="h-72 rounded-md border border-line bg-panel p-3">
          <div className="mb-3 text-sm font-medium">{group.name}</div>
          <ResponsiveContainer width="100%" height="85%" minWidth={240} minHeight={200}>
            <LineChart data={group.points}>
              <CartesianGrid stroke="#d8ded5" strokeDasharray="3 3" />
              <XAxis dataKey="x" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={70} />
              <ChartTooltip />
              <Line dataKey="value" stroke="#006d77" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ))}
    </div>
  );
}

function JobTable({ jobs }: { jobs: JobRecord[] }) {
  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <details key={job.id} className="rounded-md border border-line bg-panel p-3">
          <summary className="flex cursor-pointer items-center justify-between gap-3">
            <span className="font-mono text-sm">{job.id}</span>
            <StatusBadge status={job.status} />
          </summary>
          <pre className="mt-3 max-h-80 overflow-auto rounded border border-line bg-white p-3 text-xs">{job.lastLogLine || job.command}</pre>
          <div className="mt-2 font-mono text-xs text-moss">
            {job.startUtc} {"->"} {job.endUtc || "running"}
          </div>
        </details>
      ))}
    </div>
  );
}

type AgentRun = {
  run: string;
  kind: "planner" | "executor";
  mtimeMs: number;
  sizeBytes: number;
  hasEvents: boolean;
  eventsPath: string;
  decision: { status?: string | null; gateDecision?: string | null; summary?: string } | null;
};

type AgentEntry =
  | { kind: "message"; text: string; meta?: string }
  | { kind: "reasoning"; text: string }
  | { kind: "command"; command: string; output?: string; exitCode?: number | null }
  | { kind: "files"; files: string[]; summary?: string }
  | { kind: "tool"; name: string; detail?: string }
  | { kind: "error"; text: string }
  | { kind: "decision"; status?: string; gate?: string; summary?: string; next?: string }
  | { kind: "todo"; todos: { text: string; done: boolean }[] }
  | { kind: "other"; label: string; text: string };

function asText(v: unknown): string {
  if (typeof v === "string") return v;
  if (Array.isArray(v)) {
    return v
      .map((p) => (typeof p === "string" ? p : p && typeof (p as Record<string, unknown>).text === "string" ? String((p as Record<string, unknown>).text) : ""))
      .join("");
  }
  return "";
}

function cleanCommand(cmd: unknown): string {
  let c = Array.isArray(cmd) ? cmd.join(" ") : typeof cmd === "string" ? cmd : "";
  c = c.trim();
  const m = c.match(/^(?:\/bin\/)?bash\s+-l?c\s+([\s\S]*)$/);
  if (m) {
    let inner = m[1].trim();
    if ((inner.startsWith('"') && inner.endsWith('"')) || (inner.startsWith("'") && inner.endsWith("'"))) inner = inner.slice(1, -1);
    c = inner;
  }
  return c;
}

// The executor's final answers are emitted as run_decision JSON, so an "assistant message" is often
// a JSON object whose readable prose is its `summary`. Pull that out and keep the verdict as meta.
function summaryFromText(text: string): { summary: string; meta?: string } | null {
  const s = text.trim();
  if (!s.startsWith("{")) return null;
  try {
    const o = JSON.parse(s) as Record<string, unknown>;
    if (!o.summary || !(o.status || o.gate_decision || o.terminal_decision || o.next_action)) return null;
    const head = [String(o.status ?? o.terminal_decision ?? "").trim(), o.gate_decision ? String(o.gate_decision) : ""].filter(Boolean).join(" · ");
    const meta = [head, o.next_action ? `next: ${String(o.next_action)}` : ""].filter(Boolean).join(" · ");
    return { summary: asText(o.summary), meta: meta || undefined };
  } catch {
    return null;
  }
}

function itemToEntry(it: Record<string, unknown>): AgentEntry {
  const t = String(it.type ?? "");
  if (t === "command_execution" || t === "local_shell_call" || t === "shell") {
    const ec = it.exit_code ?? it.exitCode;
    return {
      kind: "command",
      command: cleanCommand(it.command ?? it.cmd),
      output: asText(it.aggregated_output ?? it.output ?? it.stdout) || undefined,
      exitCode: typeof ec === "number" ? ec : ec === null ? null : undefined
    };
  }
  if (t === "reasoning") return { kind: "reasoning", text: asText(it.text ?? it.summary ?? it.content) };
  if (t === "agent_message" || t === "assistant_message" || t === "message") {
    const text = asText(it.text ?? it.content);
    const d = summaryFromText(text);
    return d ? { kind: "message", text: d.summary, meta: d.meta } : { kind: "message", text };
  }
  if (t === "file_change" || t === "patch" || t === "patch_apply" || t === "file_update") {
    const changes = (it.changes ?? it.files) as unknown;
    let files: string[] = [];
    if (Array.isArray(changes)) files = changes.map((c) => (typeof c === "string" ? c : String((c as Record<string, unknown>)?.path ?? (c as Record<string, unknown>)?.file ?? ""))).filter(Boolean);
    else if (changes && typeof changes === "object") files = Object.keys(changes as Record<string, unknown>);
    return { kind: "files", files, summary: asText(it.summary) || undefined };
  }
  if (t === "mcp_tool_call" || t === "function_call" || t === "web_search" || t === "tool_call") {
    return { kind: "tool", name: String(it.tool ?? it.name ?? it.server ?? t), detail: asText(it.query ?? it.arguments ?? it.command) || undefined };
  }
  if (t === "error") return { kind: "error", text: asText(it.message ?? it.text) || JSON.stringify(it) };
  if (t === "todo_list") {
    const raw = (it.items ?? it.todos) as unknown;
    const todos = Array.isArray(raw)
      ? raw.map((x) => {
          const o = (x ?? {}) as Record<string, unknown>;
          return { text: asText(o.text ?? o.title ?? o.content) || String(x), done: Boolean(o.completed ?? o.done ?? o.status === "completed") };
        })
      : [];
    return { kind: "todo", todos };
  }
  const text = asText(it.text ?? it.summary ?? it.content);
  return { kind: "other", label: t || "item", text: text || JSON.stringify(it) };
}

// Parse Codex's `exec --json` event stream into human-readable entries. item.started/item.completed
// pairs collapse to one entry per item id (completed wins), and noisy lifecycle events are dropped.
function parseAgentEvents(content: string): AgentEntry[] {
  const byId = new Map<string, number>();
  const entries: AgentEntry[] = [];
  let i = 0;
  for (const line of content.split(/\r?\n/)) {
    if (!line.trim()) continue;
    i += 1;
    let ev: Record<string, unknown>;
    try {
      ev = JSON.parse(line) as Record<string, unknown>;
    } catch {
      entries.push({ kind: "other", label: "raw", text: line });
      continue;
    }
    const type = String(ev.type ?? "");
    if (type.startsWith("item.") && ev.item && typeof ev.item === "object") {
      const it = ev.item as Record<string, unknown>;
      const entry = itemToEntry(it);
      const id = String(it.id ?? `i${i}`);
      const at = byId.get(id);
      if (at !== undefined) entries[at] = entry;
      else {
        byId.set(id, entries.length);
        entries.push(entry);
      }
      continue;
    }
    if (type === "error" || ev.error) {
      entries.push({ kind: "error", text: asText(ev.message ?? ev.error) || JSON.stringify(ev) });
      continue;
    }
    if (ev.summary && (ev.status || ev.gate_decision || ev.terminal_decision || ev.next_action)) {
      entries.push({
        kind: "decision",
        status: String(ev.status ?? ev.terminal_decision ?? ""),
        gate: ev.gate_decision ? String(ev.gate_decision) : undefined,
        summary: asText(ev.summary),
        next: ev.next_action ? String(ev.next_action) : undefined
      });
      continue;
    }
    // thread.*/turn.* lifecycle events are intentionally dropped from the readable view.
  }
  return entries;
}

function AgentEntryView({ e }: { e: AgentEntry }) {
  if (e.kind === "message")
    return (
      <div className="rounded border border-line bg-white px-2 py-1.5">
        <div className="mb-0.5 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide text-moss">
          <span>assistant</span>
          {e.meta ? <span className="shrink-0 font-mono normal-case">{e.meta}</span> : null}
        </div>
        <div className="whitespace-pre-wrap break-words text-[12px] text-ink">{e.text}</div>
      </div>
    );
  if (e.kind === "reasoning")
    return (
      <div className="px-2 py-1">
        <div className="mb-0.5 text-[10px] uppercase tracking-wide text-moss">thinking</div>
        <div className="whitespace-pre-wrap break-words text-[12px] italic text-moss">{e.text}</div>
      </div>
    );
  if (e.kind === "command") {
    const pending = e.exitCode === undefined || e.exitCode === null;
    const ok = !pending && e.exitCode === 0;
    const badge = pending ? "$" : ok ? "✓" : `✗ ${e.exitCode}`;
    return (
      <div className="rounded border border-line bg-panel px-2 py-1.5">
        <div className="flex items-start gap-2">
          <span className={`shrink-0 font-mono text-[11px] ${pending ? "text-moss" : ok ? "text-ink" : "text-danger"}`}>{badge}</span>
          <code className="min-w-0 whitespace-pre-wrap break-words font-mono text-[11px] text-ink">{e.command}</code>
        </div>
        {e.output ? (
          <details className="mt-1">
            <summary className="cursor-pointer text-[10px] text-moss">output</summary>
            <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-white p-2 font-mono text-[10px] text-ink">{e.output}</pre>
          </details>
        ) : null}
      </div>
    );
  }
  if (e.kind === "files")
    return (
      <div className="rounded border border-line bg-white px-2 py-1.5 text-[11px]">
        <span className="text-moss">edited:</span> <span className="break-words font-mono text-ink">{e.files.join(", ") || e.summary || "(files)"}</span>
      </div>
    );
  if (e.kind === "tool")
    return (
      <div className="rounded border border-line bg-white px-2 py-1.5 text-[11px]">
        <span className="text-moss">tool</span> <span className="font-mono text-ink">{e.name}</span>
        {e.detail ? <div className="mt-0.5 whitespace-pre-wrap break-words text-moss">{e.detail}</div> : null}
      </div>
    );
  if (e.kind === "error")
    return <div className="whitespace-pre-wrap break-words rounded border border-danger/30 bg-white px-2 py-1.5 text-[11px] text-danger">{e.text}</div>;
  if (e.kind === "decision")
    return (
      <div className="rounded border border-ink/30 bg-panel px-2 py-1.5">
        <div className="text-[10px] uppercase tracking-wide text-moss">final · {e.status}{e.gate ? ` · ${e.gate}` : ""}</div>
        {e.summary ? <div className="mt-0.5 whitespace-pre-wrap break-words text-[12px] text-ink">{e.summary}</div> : null}
        {e.next ? <div className="mt-1 text-[11px] text-moss">next: {e.next}</div> : null}
      </div>
    );
  if (e.kind === "todo")
    return (
      <div className="rounded border border-line bg-white px-2 py-1.5 text-[11px]">
        <div className="mb-0.5 text-[10px] uppercase tracking-wide text-moss">plan</div>
        <ul className="grid gap-0.5">
          {e.todos.map((td, i) => (
            <li key={i} className={`break-words ${td.done ? "text-moss line-through" : "text-ink"}`}>{td.done ? "☑" : "☐"} {td.text}</li>
          ))}
        </ul>
      </div>
    );
  return (
    <div className="px-2 py-1 text-[11px]">
      <div className="text-[10px] uppercase tracking-wide text-moss">{e.label}</div>
      <div className="whitespace-pre-wrap break-words text-moss">{e.text}</div>
    </div>
  );
}

// The agent's full Codex event stream — reasoning, messages, tool calls — loaded on request.
// Mounts only when the Agent tab is open (Radix unmounts inactive tab content), and each run's
// heavy events.jsonl is fetched only when that run is selected.
function AgentLogPanel() {
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [loadingContent, setLoadingContent] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  const loadRuns = async () => {
    setError("");
    try {
      const data = await fetchJson<{ runs: AgentRun[] }>("/api/agent-logs");
      setRuns(data.runs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => {
    void loadRuns();
  }, []);

  const openRun = async (run: AgentRun) => {
    setSelected(run.run);
    setContent("");
    setLoadingContent(true);
    try {
      const res = await fetch(`/api/artifacts/${run.eventsPath}`);
      setContent(res.ok ? await res.text() : `failed to load (${res.status})`);
    } catch (e) {
      setContent(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingContent(false);
    }
  };

  const lines = useMemo(() => content.split(/\r?\n/).filter((l) => l.trim()), [content]);
  const entries = useMemo(() => parseAgentEvents(content), [content]);
  const selectedRun = runs?.find((r) => r.run === selected) ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase text-moss">Agent runs</h3>
          <button onClick={() => void loadRuns()} className="focus-ring rounded border border-line px-2 py-0.5 text-xs text-moss">Refresh</button>
        </div>
        {error ? <div className="rounded border border-danger/30 bg-white p-2 text-xs text-danger">{error}</div> : null}
        {runs === null ? (
          <div className="flex items-center gap-2 text-xs text-moss"><Loader2 className="h-3 w-3 animate-spin" /> loading</div>
        ) : runs.length === 0 ? (
          <p className="text-xs text-moss">No agent runs yet. They appear once the orchestrator runs a planner or executor tick.</p>
        ) : (
          <ul className="grid max-h-[560px] gap-1 overflow-y-auto">
            {runs.map((run) => (
              <li key={run.run}>
                <button
                  onClick={() => void openRun(run)}
                  className={`focus-ring w-full rounded border px-2 py-1.5 text-left ${selected === run.run ? "border-ink bg-panel" : "border-line bg-white"}`}
                >
                  <div className="flex items-center justify-between font-mono text-[11px]">
                    <span className="truncate">{run.run}</span>
                    <span className={run.kind === "planner" ? "text-ink" : "text-moss"}>{run.kind}</span>
                  </div>
                  {run.decision ? (
                    <div className="mt-0.5 truncate text-[10px] text-moss">{run.decision.status ?? "?"}{run.decision.gateDecision ? ` · ${run.decision.gateDecision}` : ""}</div>
                  ) : (
                    <div className="mt-0.5 text-[10px] text-moss">{run.hasEvents ? "running…" : "no events"}</div>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="min-w-0">
        {selectedRun === null ? (
          <div className="grid h-full min-h-[200px] place-items-center rounded border border-line bg-white text-xs text-moss">Select a run to inspect the agent's output.</div>
        ) : (
          <div className="rounded border border-line bg-white">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
              <div className="font-mono text-xs text-ink">{selectedRun.run}</div>
              <div className="flex items-center gap-2 text-xs">
                <button onClick={() => setShowRaw((v) => !v)} className="focus-ring rounded border border-line px-2 py-0.5 text-moss">{showRaw ? "Pretty" : "Raw"}</button>
                <a href={`/api/artifacts/${selectedRun.eventsPath}`} className="focus-ring rounded border border-line px-2 py-0.5 text-moss">Download</a>
              </div>
            </div>
            <div className="max-h-[560px] overflow-y-auto p-3">
              {loadingContent ? (
                <div className="flex items-center gap-2 text-xs text-moss"><Loader2 className="h-3 w-3 animate-spin" /> loading events</div>
              ) : lines.length === 0 ? (
                <div className="text-xs text-moss">No events captured yet.</div>
              ) : showRaw ? (
                <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-ink">{content}</pre>
              ) : (
                <div className="grid gap-2">
                  {entries.map((e, i) => (
                    <AgentEntryView key={i} e={e} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ArtifactTable({ artifacts }: { artifacts: ArtifactRecord[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="border-b border-line text-xs uppercase text-moss">
          <tr>
            <th className="py-2 pr-3">Path</th>
            <th className="py-2 pr-3">Kind</th>
            <th className="py-2 pr-3">Run</th>
            <th className="py-2 pr-3">Size</th>
          </tr>
        </thead>
        <tbody>
          {artifacts.map((artifact) => (
            <tr key={artifact.path} className="border-b border-line/70">
              <td className="max-w-[620px] truncate py-2 pr-3 font-mono text-xs">{artifact.path}</td>
              <td className="py-2 pr-3">{artifact.kind}</td>
              <td className="py-2 pr-3 font-mono text-xs">{artifact.runId ?? ""}</td>
              <td className="py-2 pr-3 font-mono text-xs">{bytes(artifact.sizeBytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type OrchestratorState = {
  status?: string;
  stage?: string;
  tick?: number;
  elapsed_hours?: number;
  remaining_hours?: number;
  cumulative_cost_usd?: number;
  soft_cap_usd?: number;
  hard_cap_usd?: number;
  consecutive_failures?: number;
  request_shutdown?: boolean;
  dry_run?: boolean;
  launch_id?: string;
  models?: { planner?: string; executor?: string };
  sandbox?: { planner?: string; executor?: string };
  updated_at?: string;
  last_plan_directive?: { time_budget_hours?: number; rationale?: string; terminal_decision?: string } | null;
  last_executor_decision?: { status?: string; gate_decision?: string; summary?: string } | null;
  history?: Array<{ tick?: number; stage?: string; exec_status?: string; gate_decision?: string; summary?: string; cumulative_cost_usd?: number }>;
};

const ORCH_TERMINAL = new Set(["complete", "halted_deadline", "halted_budget", "halted_operator", "escalate"]);

function Bar({ pct, tone, marker }: { pct: number; tone: string; marker?: number }) {
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="relative h-2 w-full overflow-hidden rounded bg-panel">
      <div className={`h-full ${tone}`} style={{ width: `${clamped}%` }} />
      {marker !== undefined ? (
        <div className="absolute top-0 h-full w-px bg-ink/50" style={{ left: `${Math.max(0, Math.min(100, marker))}%` }} />
      ) : null}
    </div>
  );
}

function OrchestratorView({ snapshot }: { snapshot: Snapshot }) {
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const submit = async (type: string, args: Record<string, unknown> = {}) => {
    setPending(type);
    setMessage("");
    try {
      const result = await fetchJson<{ id: string }>("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, args })
      });
      setMessage(result.id);
      queryClient.invalidateQueries({ queryKey: ["snapshot"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setPending(null);
    }
  };

  const orch = snapshot.orchestrator as OrchestratorState | null;
  const status = orch?.status ?? "idle";
  const running = orch !== null && !ORCH_TERMINAL.has(status);
  const elapsed = orch?.elapsed_hours ?? 0;
  const remaining = Math.max(0, orch?.remaining_hours ?? 0);
  const total = elapsed + remaining;
  const timePct = total > 0 ? (elapsed / total) * 100 : 0;
  const cost = orch?.cumulative_cost_usd ?? 0;
  const hard = orch?.hard_cap_usd ?? 50;
  const soft = orch?.soft_cap_usd ?? 35;
  const costPct = hard > 0 ? (cost / hard) * 100 : 0;
  const plan = orch?.last_plan_directive ?? null;
  const exec = orch?.last_executor_decision ?? null;
  const history = (orch?.history ?? []).slice().reverse();

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      {/* Left: live status + controls */}
      <div className="grid content-start gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold">
            session{orch?.dry_run ? <span className="rounded bg-panel px-1.5 py-0.5 text-[10px] text-moss">DRY RUN</span> : null}
          </div>
          <StatusBadge status={status} />
        </div>

        {orch === null ? (
          <p className="text-xs text-moss">No orchestrator state yet. Start it to run unattended.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-moss">
              <span>stage <span className="text-ink">{orch.stage ?? "?"}</span></span>
              <span>tick {orch.tick ?? 0}</span>
              {orch.launch_id ? <span className="truncate">{orch.launch_id}</span> : null}
              {typeof orch.consecutive_failures === "number" && orch.consecutive_failures > 0 ? (
                <span className="text-danger">{orch.consecutive_failures} fail</span>
              ) : null}
            </div>

            <div>
              <div className="mb-1 flex justify-between text-[11px] text-moss">
                <span>time</span>
                <span className="font-mono">{elapsed.toFixed(2)}h elapsed · {remaining.toFixed(2)}h left</span>
              </div>
              <Bar pct={timePct} tone="bg-moss" />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-[11px] text-moss">
                <span>spend</span>
                <span className="font-mono">${cost.toFixed(2)} / ${hard.toFixed(0)} (soft ${soft.toFixed(0)})</span>
              </div>
              <Bar pct={costPct} tone={cost >= soft ? "bg-danger" : "bg-ink"} marker={hard > 0 ? (soft / hard) * 100 : undefined} />
            </div>

            {plan ? (
              <div className="min-w-0 rounded border border-line bg-panel px-2 py-1.5 text-[11px]">
                <div className="break-words text-moss">planner → <span className="text-ink">{plan.terminal_decision ?? "continue"}</span>, budget {Number(plan.time_budget_hours ?? 0).toFixed(2)}h</div>
                {plan.rationale ? <div className="mt-0.5 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-moss">{plan.rationale}</div> : null}
              </div>
            ) : null}
            {exec ? (
              <div className="min-w-0 rounded border border-line bg-panel px-2 py-1.5 text-[11px]">
                <div className="break-words text-moss">executor → <span className="text-ink">{exec.status ?? "?"}</span> / {exec.gate_decision ?? "?"}</div>
                {exec.summary ? <div className="mt-0.5 max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-moss">{exec.summary}</div> : null}
              </div>
            ) : null}

            <div className="break-words font-mono text-[10px] text-moss">
              {orch.models ? <span>planner {orch.models.planner} · exec {orch.models.executor}</span> : null}
              {orch.sandbox ? <span> · sandbox exec={orch.sandbox.executor}</span> : null}
            </div>
            {orch.request_shutdown ? (
              <div className="rounded border border-line bg-panel px-2 py-1 text-[11px] text-moss">VM shutdown requested — worker will sync and stop (not delete) the VM.</div>
            ) : null}
          </>
        )}

        {running ? (
          <button
            type="button"
            onClick={() => submit("stopOrchestrator")}
            disabled={pending !== null}
            className="focus-ring flex w-full items-center justify-center gap-2 rounded-md border border-danger/40 bg-white px-3 py-2 text-sm font-medium text-danger hover:bg-danger/5 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Square className="h-4 w-4" /> Stop Orchestrator
          </button>
        ) : (
          <ActionForm
            title="Start orchestrator"
            description="Unattended planner+executor. Hard caps and deadline are enforced by the harness."
            fields={[
              { name: "deadlineHours", label: "Deadline (hours)", type: "number", required: true, placeholder: "8", defaultValue: "8" },
              { name: "soft", label: "Soft cap (USD)", type: "number", placeholder: "35", defaultValue: "35" },
              { name: "hard", label: "Hard cap (USD)", type: "number", placeholder: "50", defaultValue: "50" }
            ]}
            icon={<Play className="h-4 w-4" />}
            disabled={pending !== null}
            onSubmit={(args) => submit("startOrchestrator", args)}
          />
        )}
        {message ? <div className="truncate rounded border border-line bg-panel px-2 py-1 font-mono text-xs">{message}</div> : null}
      </div>

      {/* Right: full tick timeline */}
      <div className="min-w-0">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-moss">Tick history</h3>
        {history.length === 0 ? (
          <p className="text-xs text-moss">No ticks yet. Each tick = one planner decision + one executor action.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-line text-[10px] uppercase text-moss">
                <tr>
                  <th className="py-1.5 pr-2">#</th>
                  <th className="py-1.5 pr-2">Stage</th>
                  <th className="py-1.5 pr-2">Executor</th>
                  <th className="py-1.5 pr-2">Gate</th>
                  <th className="py-1.5 pr-2">Cost</th>
                  <th className="py-1.5">Summary</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => {
                  const bad = h.exec_status === "failed" || h.exec_status === "blocked";
                  return (
                    <tr key={i} className="border-b border-line/60 align-top">
                      <td className="py-1.5 pr-2 font-mono text-moss">{h.tick}</td>
                      <td className="py-1.5 pr-2 font-mono">{h.stage}</td>
                      <td className={`py-1.5 pr-2 ${bad ? "text-danger" : "text-ink"}`}>{h.exec_status ?? "—"}</td>
                      <td className="py-1.5 pr-2 text-moss">{h.gate_decision ?? "—"}</td>
                      <td className="py-1.5 pr-2 font-mono text-moss">${Number(h.cumulative_cost_usd ?? 0).toFixed(2)}</td>
                      <td className="py-1.5 text-moss">{h.summary || ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ControlCenter({ snapshot, selectedRun }: { snapshot: Snapshot; selectedRun: RunRecord | null }) {
  const [pending, setPending] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const submit = async (type: string, args: Record<string, unknown> = {}) => {
    setPending(type);
    setMessage("");
    try {
      const result = await fetchJson<{ id: string }>("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, args })
      });
      setMessage(result.id);
      queryClient.invalidateQueries({ queryKey: ["snapshot"] });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setPending(null);
    }
  };
  const runId = selectedRun?.id ?? "";
  const firstJob = snapshot.jobs[0]?.id ?? "";
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Control</h2>
        <div className="flex gap-2">
          <IconButton label="Start VM" icon={<Server className="h-4 w-4" />} onClick={() => submit("startVm")} disabled={pending !== null} />
          <IconButton label="Stop VM" icon={<CirclePause className="h-4 w-4" />} onClick={() => submit("stopVm")} disabled={pending !== null} />
          <IconButton label="Sync" icon={<RefreshCcw className="h-4 w-4" />} onClick={() => submit("syncNow", { direction: "pull" })} disabled={pending !== null} />
        </div>
      </div>
      <div className="grid gap-2">
        <ActionForm
          title="Bounded job"
          description="Wall-clock is the hard safety cap; epochs, steps, and tokens are optional runner limits."
          fields={[
            { name: "jobName", label: "Job name", type: "text", required: true, placeholder: "dashboard-probe", defaultValue: `dashboard-probe-${Date.now()}` },
            {
              name: "templateId",
              label: "Job template",
              type: "select",
              required: true,
              defaultValue: "harmless-status",
              options: [
                { label: "Harmless status probe", value: "harmless-status" },
                { label: "Remote health probe", value: "remote-probe" }
              ]
            },
            { name: "maxHours", label: "Max wall-clock hours", type: "number", required: true, placeholder: "0.25", defaultValue: "0.25" },
            { name: "maxEpochs", label: "Max epochs", type: "number", placeholder: "optional" },
            { name: "maxSteps", label: "Max training steps", type: "number", placeholder: "optional" },
            { name: "maxTokens", label: "Max tokens", type: "number", placeholder: "optional" }
          ]}
          icon={<Play className="h-4 w-4" />}
          disabled={pending !== null}
          onSubmit={(args) => submit("startBoundedJob", args)}
        />
        <ActionForm
          title="Stop job"
          description="Sends TERM to a bounded job by job name."
          fields={[{ name: "jobName", label: "Job name", type: "text", required: true, placeholder: "job name", defaultValue: firstJob }]}
          icon={<Square className="h-4 w-4" />}
          disabled={pending !== null}
          onSubmit={(args) => submit("stopJob", args)}
        />
        <div className="grid grid-cols-3 gap-2">
          <IconButton label="Checkpoint run" icon={<Zap className="h-4 w-4" />} onClick={() => submit("checkpointNow", { runId })} disabled={!runId || pending !== null} />
          <IconButton label="Pause run" icon={<Pause className="h-4 w-4" />} onClick={() => submit("pauseRun", { runId })} disabled={!runId || pending !== null} />
          <IconButton label="Resume run" icon={<Play className="h-4 w-4" />} onClick={() => submit("resumeRun", { runId })} disabled={!runId || pending !== null} />
        </div>
        <ActionForm
          title="Fork"
          description="Creates a new non-destructive lineage from a checkpoint."
          fields={[
            { name: "runId", label: "Run id", type: "text", placeholder: "run id", required: true, defaultValue: runId },
            { name: "checkpointId", label: "Checkpoint id", type: "text", placeholder: "checkpoint id", required: true, defaultValue: "latest" },
            { name: "newRunId", label: "New run id", type: "text", placeholder: "optional new id", defaultValue: "" }
          ]}
          icon={<GitBranch className="h-4 w-4" />}
          disabled={pending !== null}
          onSubmit={(args) => submit("forkFromCheckpoint", args)}
        />
      </div>
      {message ? <div className="mt-3 truncate rounded border border-line bg-panel px-2 py-1 font-mono text-xs">{message}</div> : null}
    </section>
  );
}

function ActionForm({
  title,
  description,
  fields,
  icon,
  disabled,
  onSubmit
}: {
  title: string;
  description?: string;
  fields: Array<ActionDefinition["fields"][number] & { defaultValue?: string }>;
  icon: React.ReactNode;
  disabled?: boolean;
  onSubmit: (args: Record<string, unknown>) => void;
}) {
  return (
    <form
      className="rounded-md border border-line bg-panel p-2"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        onSubmit(
          Object.fromEntries(
            fields.flatMap((field) => {
              const value = form.get(field.name);
              if (!field.required && (value === null || value === "")) return [];
              return [[field.name, value ?? ""]];
            })
          )
        );
      }}
    >
      <div className="mb-2 flex items-center gap-2 text-xs uppercase text-moss">{icon}{title}</div>
      {description ? <p className="mb-2 text-xs leading-relaxed text-moss">{description}</p> : null}
      <div className="grid gap-2">
        {fields.map((field) => (
          <label key={field.name} className="grid gap-1">
            <span className="text-xs uppercase text-moss">{field.label}</span>
            {field.type === "select" ? (
              <select
                className="focus-ring h-9 rounded border border-line bg-white px-2 text-sm"
                name={field.name}
                defaultValue={field.defaultValue ?? field.options?.[0]?.value ?? ""}
                required={field.required}
              >
                {field.options?.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            ) : (
              <input
                className="focus-ring h-9 rounded border border-line bg-white px-2 text-sm"
                name={field.name}
                type={field.type}
                min={field.type === "number" ? "0" : undefined}
                step={field.type === "number" ? "any" : undefined}
                placeholder={field.placeholder}
                defaultValue={field.defaultValue}
                required={field.required}
              />
            )}
          </label>
        ))}
        <button className="focus-ring h-9 rounded-md bg-signal px-3 text-sm font-medium text-white disabled:opacity-50" disabled={disabled} type="submit">
          Queue
        </button>
      </div>
    </form>
  );
}

function DecisionCockpit({ snapshot }: { snapshot: Snapshot }) {
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-moss" />
        <h2 className="text-sm font-semibold">Decision</h2>
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs uppercase text-moss">Gate</dt>
          <dd>{String(snapshot.currentStatus?.gate ?? "unknown")}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-moss">Projected h</dt>
          <dd className="font-mono">{num(snapshot.summary.projectedMedianHours)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-moss">Registry</dt>
          <dd className="font-mono">{snapshot.registryRows}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-moss">Actions</dt>
          <dd className="font-mono">{snapshot.summary.pendingActionCount}/{snapshot.summary.actionCount}</dd>
        </div>
      </dl>
      <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded border border-line bg-panel p-3 text-xs">{snapshot.decisionLogTail}</pre>
    </section>
  );
}

function ActionHistory({ snapshot }: { snapshot: Snapshot }) {
  return (
    <section className="rounded-md border border-line bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <History className="h-4 w-4 text-moss" />
        <h2 className="text-sm font-semibold">Actions</h2>
      </div>
      <div className="space-y-2">
        {snapshot.actions.slice(0, 12).map((action) => (
          <div key={action.id} className="rounded border border-line bg-panel p-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono">{action.type}</span>
              <StatusBadge status={action.status} />
            </div>
            <div className="mt-1 truncate font-mono text-moss">{action.id}</div>
            {action.stderr ? (
              <div className="mt-1 flex items-center gap-1 text-danger">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span className="truncate">{action.stderr}</span>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "completed" || status === "ok"
      ? "border-moss/30 bg-moss/10 text-moss"
      : status === "failed" || status === "fail"
        ? "border-danger/30 bg-danger/10 text-danger"
        : status === "running" || status === "pending"
          ? "border-signal/30 bg-signal/10 text-signal"
          : "border-line bg-white text-moss";
  return <span className={`inline-flex rounded border px-2 py-0.5 text-xs ${cls}`}>{status || "unknown"}</span>;
}

function num(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "n/a";
}

function dollars(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `$${value.toFixed(2)}` : "n/a";
}

function compactNumber(value: number): string {
  if (!Number.isFinite(value)) return "n/a";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${(value / 1_000).toFixed(1)}k`;
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(2);
  if (abs >= 1) return value.toFixed(3);
  return value.toPrecision(3);
}

function bytes(value: number): string {
  if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MiB`;
  if (value > 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${value} B`;
}

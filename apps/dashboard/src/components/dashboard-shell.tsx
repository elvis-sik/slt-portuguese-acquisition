"use client";

import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  Activity,
  AlertTriangle,
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
          <Tabs.Root defaultValue="runs" className="rounded-md border border-line bg-white">
            <Tabs.List className="flex border-b border-line bg-panel">
              <Tab value="runs" icon={<Workflow className="h-4 w-4" />} label="Runs" />
              <Tab value="figures" icon={<ChartSpline className="h-4 w-4" />} label="Figures" />
              <Tab value="metrics" icon={<Activity className="h-4 w-4" />} label="Metrics" />
              <Tab value="logs" icon={<Terminal className="h-4 w-4" />} label="Logs" />
              <Tab value="artifacts" icon={<Box className="h-4 w-4" />} label="Artifacts" />
            </Tabs.List>
            <Tabs.Content value="runs" className="p-4">
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
              <JobTable jobs={data.jobs} />
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

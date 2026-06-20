import { spawn } from "node:child_process";
import path from "node:path";
import type { DashboardConfig } from "./types";

export interface CommandSpec {
  command: string;
  args: string[];
  cwd?: string;
  env?: NodeJS.ProcessEnv;
  timeoutMs?: number;
}

export interface CommandResult {
  command: string[];
  stdout: string;
  stderr: string;
  exitCode: number | null;
  timedOut: boolean;
}

export function localScript(config: DashboardConfig, script: string): string {
  return path.join(config.repoRoot, script);
}

export function runCommand(spec: CommandSpec): Promise<CommandResult> {
  return new Promise((resolve) => {
    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd,
      env: spec.env ?? process.env,
      stdio: ["ignore", "pipe", "pipe"]
    });
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    const timer =
      spec.timeoutMs && spec.timeoutMs > 0
        ? setTimeout(() => {
            timedOut = true;
            child.kill("SIGTERM");
          }, spec.timeoutMs)
        : null;
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      if (timer) clearTimeout(timer);
      resolve({
        command: [spec.command, ...spec.args],
        stdout,
        stderr: `${stderr}${stderr ? "\n" : ""}${error.message}`,
        exitCode: 127,
        timedOut
      });
    });
    child.on("close", (code) => {
      if (timer) clearTimeout(timer);
      resolve({
        command: [spec.command, ...spec.args],
        stdout,
        stderr,
        exitCode: code,
        timedOut
      });
    });
  });
}

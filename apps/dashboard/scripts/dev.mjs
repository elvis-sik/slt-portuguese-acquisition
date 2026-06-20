import { spawn } from "node:child_process";

const children = [
  spawn("pnpm", ["dashboard:worker"], { stdio: "inherit", env: process.env }),
  spawn("pnpm", ["dev"], { stdio: "inherit", env: process.env })
];

const stop = (signal) => {
  for (const child of children) {
    if (!child.killed) child.kill(signal);
  }
};

process.on("SIGINT", () => stop("SIGINT"));
process.on("SIGTERM", () => stop("SIGTERM"));

for (const child of children) {
  child.on("exit", (code, signal) => {
    if (code && code !== 0) {
      stop("SIGTERM");
      process.exitCode = code;
    }
    if (signal) stop(signal);
  });
}

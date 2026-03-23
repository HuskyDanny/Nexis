/**
 * Structured logger for Nexis frontend.
 *
 * Two levels:
 *   - PRODUCTION (info): key steps, state transitions
 *   - DEBUG: verbose payloads, timing
 *
 * Toggle via VITE_LOG_LEVEL env var (default: "info", set to "debug" for verbose).
 */

type LogLevel = "debug" | "info" | "warn" | "error";

const LEVEL_RANK: Record<LogLevel, number> = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const currentLevel: LogLevel =
  (import.meta.env.VITE_LOG_LEVEL as LogLevel) ?? "info";

function shouldLog(level: LogLevel): boolean {
  return LEVEL_RANK[level] >= LEVEL_RANK[currentLevel];
}

function timestamp(): string {
  return new Date().toLocaleTimeString("en-US", { hour12: false });
}

export function createLogger(name: string) {
  const prefix = `[${name}]`;

  return {
    debug: (...args: unknown[]) => {
      if (shouldLog("debug")) console.debug(timestamp(), prefix, ...args);
    },
    info: (...args: unknown[]) => {
      if (shouldLog("info")) console.info(timestamp(), prefix, ...args);
    },
    warn: (...args: unknown[]) => {
      if (shouldLog("warn")) console.warn(timestamp(), prefix, ...args);
    },
    error: (...args: unknown[]) => {
      if (shouldLog("error")) console.error(timestamp(), prefix, ...args);
    },
  };
}

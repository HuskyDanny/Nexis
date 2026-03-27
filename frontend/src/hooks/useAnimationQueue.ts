import { useRef, useCallback, useEffect } from "react";

const MIN_GAP_MS = 200;

/**
 * Queues animation callbacks with a minimum gap between executions.
 * Prevents visual clumping when multiple nodes arrive in quick succession.
 */
export function useAnimationQueue() {
  const queue = useRef<(() => void)[]>([]);
  const lastRun = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushRef = useRef<() => void>(() => {});

  useEffect(() => {
    flushRef.current = () => {
      const now = Date.now();
      const elapsed = now - lastRun.current;

      if (queue.current.length === 0) return;

      if (elapsed >= MIN_GAP_MS) {
        const fn = queue.current.shift();
        fn?.();
        lastRun.current = Date.now();
        if (queue.current.length > 0) {
          timer.current = setTimeout(() => flushRef.current(), MIN_GAP_MS);
        }
      } else {
        timer.current = setTimeout(
          () => flushRef.current(),
          MIN_GAP_MS - elapsed,
        );
      }
    };
  });

  const enqueue = useCallback((fn: () => void) => {
    queue.current.push(fn);
    if (!timer.current) flushRef.current();
  }, []);

  return { enqueue };
}

import { useEffect, useRef, useState } from "react";
import type {
  SSENodeStart,
  SSENodeText,
  SSENodeComplete,
  SSELayerComplete,
  SSESessionComplete,
  SSEError,
  SSEEdgesPayload,
} from "../types/thinking";

interface SSECallbacks {
  onNodeStart?: (data: SSENodeStart) => void;
  onNodeText?: (data: SSENodeText) => void;
  onNodeComplete?: (data: SSENodeComplete) => void;
  onEdges?: (data: SSEEdgesPayload) => void;
  onOpportunity?: (data: Record<string, unknown>) => void;
  onLayerComplete?: (data: SSELayerComplete) => void;
  onSessionComplete?: (data: SSESessionComplete) => void;
  onError?: (data: SSEError) => void;
}

const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 5000;

export function useSSESession(
  sessionId: string | null,
  callbacks?: SSECallbacks,
) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const cbRef = useRef(callbacks);
  const connectRef = useRef<() => void>(() => {});
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync callback ref in effect to avoid ref writes during render
  useEffect(() => {
    cbRef.current = callbacks;
  });

  // Sync connect function ref in effect
  useEffect(() => {
    connectRef.current = () => {
      if (!sessionId) return;
      const url = `/api/thinking/${sessionId}/events`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("node_start", (e: MessageEvent) => {
        cbRef.current?.onNodeStart?.(JSON.parse(e.data));
      });
      es.addEventListener("node_text", (e: MessageEvent) => {
        cbRef.current?.onNodeText?.(JSON.parse(e.data));
      });
      es.addEventListener("node_complete", (e: MessageEvent) => {
        cbRef.current?.onNodeComplete?.(JSON.parse(e.data));
      });
      es.addEventListener("edges", (e: MessageEvent) => {
        cbRef.current?.onEdges?.(JSON.parse(e.data));
      });
      es.addEventListener("opportunity", (e: MessageEvent) => {
        cbRef.current?.onOpportunity?.(JSON.parse(e.data));
      });
      es.addEventListener("layer_complete", (e: MessageEvent) => {
        cbRef.current?.onLayerComplete?.(JSON.parse(e.data));
      });
      es.addEventListener("session_complete", (e: MessageEvent) => {
        cbRef.current?.onSessionComplete?.(JSON.parse(e.data));
        es.close();
        setConnected(false);
      });
      es.addEventListener("error", (e: MessageEvent) => {
        if (e.data) {
          cbRef.current?.onError?.(JSON.parse(e.data));
        }
      });

      es.onopen = () => {
        setConnected(true);
        retriesRef.current = 0;
      };
      es.onerror = () => {
        setConnected(false);
        es.close();
        if (retriesRef.current < MAX_RETRIES) {
          retriesRef.current += 1;
          timeoutRef.current = setTimeout(
            () => connectRef.current(),
            RETRY_DELAY_MS,
          );
        } else {
          cbRef.current?.onError?.({
            error: "SSE connection failed after retries",
          });
        }
      };
    };
  }, [sessionId]);

  useEffect(() => {
    connectRef.current();
    return () => {
      esRef.current?.close();
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setConnected(false);
    };
  }, [sessionId]);

  return { connected };
}

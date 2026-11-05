import { useCallback, useEffect, useRef, useState } from "react";
import type { MirrorState } from "./types";

export type Connection =
  | { phase: "connecting" }
  | { phase: "live"; state: MirrorState; isReconnecting: boolean }
  | { phase: "error"; message: string };

/**
 * Live state from the Mirror API over server-sent events. EventSource reconnects
 * on its own after a dropped connection, so a hiccup keeps the last state on
 * screen with a "reconnecting" flag; only a connection that never opened is an error.
 */
export function useMirror(): { connection: Connection; retry: () => void } {
  const [connection, setConnection] = useState<Connection>({ phase: "connecting" });
  const [attempt, setAttempt] = useState(0);
  const lastState = useRef<MirrorState | undefined>(undefined);

  useEffect(() => {
    const source = new EventSource("/api/events");
    source.onmessage = (event) => {
      const state = JSON.parse(event.data) as MirrorState;
      lastState.current = state;
      setConnection({ phase: "live", state, isReconnecting: false });
    };
    source.onerror = () => {
      if (lastState.current) {
        setConnection({ phase: "live", state: lastState.current, isReconnecting: true });
        return; // EventSource retries by itself
      }
      source.close();
      setConnection({
        phase: "error",
        message: "The Mirror API isn't answering. Start it with `uv run airlock-mirror`, then retry.",
      });
    };
    return () => source.close();
  }, [attempt]);

  const retry = useCallback(() => {
    setConnection({ phase: "connecting" });
    setAttempt((n) => n + 1);
  }, []);

  return { connection, retry };
}

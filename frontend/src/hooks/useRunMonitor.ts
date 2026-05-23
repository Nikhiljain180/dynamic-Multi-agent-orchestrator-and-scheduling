import { useEffect, useRef, useState } from 'react';
import { wsUrl } from '../api/client';

export function useRunMonitor(runId: string | null) {
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [messages, setMessages] = useState<Array<Record<string, unknown>>>([]);
  const [tokens, setTokens] = useState<Array<Record<string, unknown>>>([]);
  const [status, setStatus] = useState<string>('');

  useEffect(() => {
    if (!runId) return;
    const ws = new WebSocket(wsUrl(runId));
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'log') setLogs((prev) => [...prev, payload.data]);
      if (payload.type === 'message') setMessages((prev) => [...prev, payload.data]);
      if (payload.type === 'token_usage') setTokens((prev) => [...prev, payload.data]);
      if (payload.type === 'status') setStatus(payload.data.status);
    };
    return () => ws.close();
  }, [runId]);

  return { logs, messages, tokens, status };
}

export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 2000, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) return;
    let active = true;
    const tick = async () => {
      try {
        const result = await fetcherRef.current();
        if (active) setData(result);
      } catch {
        /* ignore transient errors */
      }
    };
    tick();
    const id = setInterval(tick, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [intervalMs, enabled]);

  return data;
}

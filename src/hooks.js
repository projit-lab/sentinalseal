import { useCallback, useEffect, useRef, useState } from 'react';

// Poll fn every `ms` while the tab is visible. Keeps the last good data on errors
// and reports `offline` after 3 failures in a row.
export function usePoll(fn, ms = 1500, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [failures, setFailures] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const tick = useCallback(async () => {
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
      setFailures(0);
    } catch (e) {
      setError(e);
      setFailures((f) => f + 1);
    }
  }, []);

  useEffect(() => {
    let stopped = false;
    let timer;
    const loop = async () => {
      if (stopped) return;
      if (!document.hidden) await tick();
      timer = setTimeout(loop, failures >= 3 ? 5000 : ms);
    };
    loop();
    return () => { stopped = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, failures >= 3, ...deps]);

  return { data, error, offline: failures >= 3, refresh: tick };
}

// Re-render every second (for live timers).
export function useNow(ms = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

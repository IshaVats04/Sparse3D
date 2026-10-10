import { useCallback, useEffect, useRef, useState } from 'react';
import { getExecution } from '../services/reconstructionService';

/**
 * GET /api/execution, optionally polled (Settings polls every 5s while open).
 * Returns { data, error, loading, refresh, setData } (setData lets a PUT/DELETE response replace the state).
 */
export function useExecution({ pollMs = 0 } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getExecution();
      if (alive.current) setState({ data, error: null, loading: false });
      return data;
    } catch (error) {
      if (alive.current) setState((s) => ({ data: s.data, error, loading: false }));
      return null;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    refresh();
    let timer = null;
    if (pollMs > 0) timer = setInterval(refresh, pollMs);
    return () => {
      alive.current = false;
      if (timer) clearInterval(timer);
    };
  }, [refresh, pollMs]);

  const setData = useCallback((data) => setState({ data, error: null, loading: false }), []);
  return { ...state, refresh, setData };
}

/** Human label for the effective execution target. */
export function targetLabel(exec) {
  if (!exec) return 'This computer';
  if (exec.effective === 'remote') {
    const name = exec.remote && exec.remote.gpu_name;
    return `Colab GPU worker${name ? ` (${name})` : ''}`;
  }
  return 'This computer';
}

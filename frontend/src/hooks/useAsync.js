import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Run an async function on mount / when deps change.
 * Returns { data, error, loading, reload }.
 */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const tick = useRef(0);

  const run = useCallback(() => {
    const id = ++tick.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve()
      .then(() => fnRef.current())
      .then((data) => {
        if (tick.current === id) setState({ data, error: null, loading: false });
      })
      .catch((error) => {
        if (tick.current === id) setState({ data: null, error, loading: false });
      });
  }, []);

  useEffect(() => {
    run();
    return () => {
      tick.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, reload: run };
}

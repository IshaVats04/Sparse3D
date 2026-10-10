import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getHealth } from '../services/reconstructionService';

const HealthContext = createContext(null);

export function HealthProvider({ children }) {
  const [state, setState] = useState({ health: null, error: null, loading: true });

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }));
    try {
      const health = await getHealth();
      setState({ health, error: null, loading: false });
      return health;
    } catch (error) {
      setState({ health: null, error, loading: false });
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo(() => ({ ...state, refresh }), [state, refresh]);
  return <HealthContext.Provider value={value}>{children}</HealthContext.Provider>;
}

export function useHealth() {
  const ctx = useContext(HealthContext);
  if (!ctx) throw new Error('useHealth must be used inside <HealthProvider>');
  return ctx;
}

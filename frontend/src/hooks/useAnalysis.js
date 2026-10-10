import { useAsync } from './useAsync';
import { getAnalysis } from '../services/evaluationService';

/** GET /api/analysis (optionally for one sweep group). `enabled=false` defers the request. */
export function useAnalysis(groupId, enabled = true) {
  return useAsync(
    () => (enabled ? getAnalysis(groupId || undefined) : Promise.resolve(null)),
    [groupId || '', enabled],
  );
}

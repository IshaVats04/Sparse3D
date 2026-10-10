import { useCallback, useEffect, useRef, useState } from 'react';
import { getJob } from '../services/experimentService';
import { TERMINAL_STATUSES } from '../utils/constants';

export const POLL_MS = 1500;
const MAX_CONSECUTIVE_ERRORS = 4;

/**
 * Poll GET /api/jobs/{id} every 1.5s until the job reaches a terminal status.
 * Returns { job, error, loading, isTerminal, refresh }.
 * A 404 stops immediately; network errors are retried a few times before giving up
 * (the error is always surfaced; `refresh()` restarts polling).
 */
export function useExperiment(jobId, { poll = true } = {}) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!!jobId);
  const timer = useRef(null);
  const alive = useRef(true);
  const runId = useRef(0);

  const stop = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const start = useCallback(() => {
    stop();
    if (!jobId) {
      setJob(null);
      setError(null);
      setLoading(false);
      return;
    }
    const id = ++runId.current;
    let failures = 0;
    setLoading(true);
    setError(null);

    const tick = async () => {
      try {
        const data = await getJob(jobId);
        if (!alive.current || runId.current !== id) return;
        failures = 0;
        setJob(data);
        setError(null);
        setLoading(false);
        if (poll && !TERMINAL_STATUSES.includes(data.status)) {
          timer.current = setTimeout(tick, POLL_MS);
        }
      } catch (e) {
        if (!alive.current || runId.current !== id) return;
        failures += 1;
        setError(e);
        setLoading(false);
        const fatal = e && e.status === 404;
        if (poll && !fatal && failures < MAX_CONSECUTIVE_ERRORS) {
          timer.current = setTimeout(tick, POLL_MS * 2);
        }
      }
    };
    tick();
  }, [jobId, poll]);

  useEffect(() => {
    alive.current = true;
    setJob(null);
    start();
    return () => {
      alive.current = false;
      runId.current += 1;
      stop();
    };
  }, [start]);

  const isTerminal = !!job && TERMINAL_STATUSES.includes(job.status);
  return { job, error, loading, isTerminal, refresh: start };
}

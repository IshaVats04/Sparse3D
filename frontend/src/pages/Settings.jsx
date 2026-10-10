import { useState } from 'react';
import { CheckCircle2, Plug, RotateCcw, Save } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Badge from '../components/ui/Badge';
import { Alert, ErrorBanner, Skeleton } from '../components/ui/Feedback';
import ExecutionCard from '../components/experiment/ExecutionCard';
import { useHealth } from '../hooks/useHealth';
import { ApiError, getApiBase, isMock, setApiBase } from '../services/api';
import { getHealth } from '../services/reconstructionService';

async function testConnection(base) {
  if (isMock()) return getHealth();
  const clean = (base || '').trim().replace(/\/+$/, '');
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  let res;
  try {
    res = await fetch(`${clean}/api/health`, { signal: ctrl.signal, headers: { Accept: 'application/json' } });
  } catch (e) {
    throw new ApiError(
      e && e.name === 'AbortError'
        ? 'The connection timed out after 8 seconds.'
        : `Could not reach ${clean || 'the same-origin backend'}. Check the URL, that the server is running, and that CORS is enabled for this origin.`,
      0,
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) throw new ApiError(`The server answered ${res.status} ${res.statusText} for /api/health.`, res.status);
  try {
    return await res.json();
  } catch {
    throw new ApiError('The server responded, but not with JSON. Is this the 3D RECON LAB backend?', res.status);
  }
}

function Flag({ ok, yes = 'Yes', no = 'No', warnInsteadOfFail = false }) {
  if (ok === undefined || ok === null) return <span className="text-slate-500">n/a</span>;
  return <Badge tone={ok ? 'green' : warnInsteadOfFail ? 'amber' : 'red'} dot>{ok ? yes : no}</Badge>;
}

function CapabilityTable({ health }) {
  const e = (health && health.environment) || {};
  const rows = [
    { label: 'Status', value: <Flag ok={health.status === 'healthy'} yes={health.status} no={String(health.status)} /> },
    { label: 'Application', value: `${health.app_name || 'n/a'} ${health.version ? `v${health.version}` : ''}` },
    { label: 'Python', value: e.python_version || 'n/a' },
    { label: 'Platform', value: e.platform || 'n/a' },
    { label: 'COLMAP', value: <Flag ok={e.colmap_available} yes="Available" no="Not found" />, extra: e.colmap_path },
    { label: 'COLMAP CUDA', value: <Flag ok={e.colmap_cuda} warnInsteadOfFail yes="Yes" no="No (CPU only)" /> },
    { label: 'PyTorch', value: <Flag ok={e.torch_available} warnInsteadOfFail yes="Installed" no="Not installed" /> },
    { label: 'Neural reconstruction', value: <Flag ok={e.neural_available} warnInsteadOfFail yes="Available" no="Unavailable" />, extra: e.neural_available === false ? e.neural_reason : null },
    { label: 'CUDA', value: <Flag ok={e.cuda_available} warnInsteadOfFail yes="Available" no="Not available" /> },
    { label: 'Compute device', value: e.device || 'n/a' },
    { label: 'Active jobs', value: e.active_jobs_count ?? 'n/a' },
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-left">
        <thead className="border-b border-line"><tr><th className="th">Capability</th><th className="th">Value</th></tr></thead>
        <tbody className="divide-y divide-line-soft">
          {rows.map((r) => (
            <tr key={r.label}>
              <td className="td text-slate-300">{r.label}</td>
              <td className="td">
                {r.value}
                {r.extra && <div className="mt-1 break-all text-xs text-slate-400">{r.extra}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Settings() {
  const { health, error, loading, refresh } = useHealth();
  const [base, setBase] = useState(getApiBase());
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState(null); // {health} | {error}

  const save = async () => {
    setApiBase(base);
    setSaved(true);
    setTest(null);
    await refresh();
  };
  const reset = async () => {
    setBase('');
    setApiBase('');
    setSaved(true);
    setTest(null);
    await refresh();
  };
  const runTest = async () => {
    setTesting(true);
    setTest(null);
    setSaved(false);
    try {
      setTest({ health: await testConnection(base) });
    } catch (e) {
      setTest({ error: e });
    } finally {
      setTesting(false);
    }
  };

  const shown = (test && test.health) || health;
  const dirty = base.trim().replace(/\/+$/, '') !== getApiBase();

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Point the interface at a backend and check what it can run." />

      <ExecutionCard />

      <Card title="Backend API">
        {isMock() && (
          <Alert tone="info" className="mb-4" title="Mock mode is on">
            Requests are answered by the built-in mock layer, so the URL below is not used.
          </Alert>
        )}
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <Input
            label="API base URL"
            value={base}
            onChange={(e) => { setBase(e.target.value); setSaved(false); }}
            placeholder="Leave empty for same origin (dev proxy), or e.g. https://abc123.ngrok.app"
            helper="Use this to connect to a backend hosted elsewhere, for example on Colab through a tunnel. The server must allow CORS."
            autoComplete="off"
            spellCheck={false}
          />
          <div className="flex flex-wrap gap-2">
            <Button icon={Plug} loading={testing} onClick={runTest}>Test connection</Button>
            <Button variant="primary" icon={Save} onClick={save} disabled={!dirty && !saved}>Save</Button>
            <Button variant="ghost" icon={RotateCcw} onClick={reset}>Reset</Button>
          </div>
        </div>
        {saved && !dirty && (
          <p className="mt-3 flex items-center gap-1.5 text-sm text-emerald-300"><CheckCircle2 className="h-4 w-4" aria-hidden /> Saved. Using {getApiBase() || 'the same origin'}.</p>
        )}
        {test && test.error && <ErrorBanner className="mt-4" error={test.error} title="Connection failed" />}
        {test && test.health && (
          <Alert tone="ok" className="mt-4" title="Connection successful">
            {test.health.app_name} v{test.health.version}, status {test.health.status}. {dirty ? 'Click Save to use this URL.' : ''}
          </Alert>
        )}
      </Card>

      <Card
        title="Environment capabilities"
        subtitle={test && test.health ? 'From the tested URL' : 'From the saved backend'}
        actions={<Button size="sm" onClick={refresh}>Refresh</Button>}
      >
        {loading && !shown ? (
          <div className="space-y-2"><Skeleton className="h-8" /><Skeleton className="h-8" /><Skeleton className="h-8" /></div>
        ) : shown ? (
          <CapabilityTable health={shown} />
        ) : (
          <ErrorBanner error={error || 'No health information is available.'} title="Backend not reachable" onRetry={refresh} />
        )}
      </Card>
    </div>
  );
}

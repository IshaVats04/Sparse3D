import { useState } from 'react';
import { CheckCircle2, ClipboardPaste, Cloud, Download, ExternalLink, Plug, Unplug } from 'lucide-react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Badge from '../ui/Badge';
import { Alert, ErrorBanner, Skeleton } from '../ui/Feedback';
import { useExecution } from '../../hooks/useExecution';
import { disconnectWorker, setExecution } from '../../services/reconstructionService';
import { apiUrl } from '../../services/api';

const MODES = [
  { value: 'local', title: 'This computer', desc: 'Always run experiments on the machine hosting the backend.' },
  { value: 'remote', title: 'Colab GPU worker', desc: 'Always run on your Google Colab GPU. Experiments fail if no worker is connected.' },
  { value: 'auto', title: 'Automatic', desc: 'Use the worker when this computer has no GPU.', suffix: '(use the worker when this computer has no GPU)' },
];

function Chip({ ok, children, neutral = false }) {
  return <Badge tone={neutral ? 'slate' : ok ? 'green' : 'amber'} dot>{children}</Badge>;
}

function yn(v) { return v ? 'yes' : 'no'; }

function StatusChips({ exec }) {
  const l = exec.local || {};
  const r = exec.remote;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <div className="label">This computer</div>
        <div className="flex flex-wrap gap-2">
          <Chip ok={l.gpu}>GPU: {yn(l.gpu)}</Chip>
          <Chip ok={l.neural_available} >Neural: {yn(l.neural_available)}</Chip>
        </div>
        {!l.neural_available && l.neural_reason && <p className="mt-1.5 text-xs text-slate-400">{l.neural_reason}</p>}
      </div>
      <div>
        <div className="label">Colab GPU worker</div>
        {r && r.connected ? (
          <div className="flex flex-wrap gap-2">
            <Chip ok>Connected</Chip>
            {r.host && <Chip neutral>Host: {r.host}</Chip>}
            <Chip ok={r.gpu}>GPU: {r.gpu_name || yn(r.gpu)}</Chip>
            <Chip ok={r.colmap_gpu_usable}>COLMAP CUDA: {yn(r.colmap_gpu_usable)}</Chip>
            <Chip ok={r.neural_available}>Neural: {r.neural_available ? (r.neural_backend || 'yes') : 'no'}</Chip>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Chip ok={false}>{r && r.configured ? 'Disconnected' : 'Not connected'}</Chip>
            {r && r.host && <Chip neutral>Host: {r.host}</Chip>}
          </div>
        )}
        {r && r.error && <p className="mt-1.5 text-xs text-amber-300">{r.error}</p>}
      </div>
    </div>
  );
}

function ColabPanel({ exec, onUpdate }) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const colab = exec.colab || {};
  const steps = Array.isArray(colab.steps) ? colab.steps : [];

  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) setCode(text.trim());
    } catch {
      /* clipboard blocked: the user can paste manually */
    }
  };
  const connect = async () => {
    setBusy(true);
    setError(null);
    try {
      onUpdate(await setExecution({ mode: exec.mode, connection_code: code.trim() }));
      setCode('');
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const last = steps.length - 1;
  return (
    <div className="mt-5 rounded-xl border border-line bg-ink-900/60 p-5">
      <h3 className="text-sm font-semibold text-white">Connect your Colab GPU</h3>
      <ol className="mt-4 space-y-4">
        {steps.map((text, i) => (
          <li key={text} className="flex gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-xs font-bold text-white">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-slate-200">{text}</p>
              {i === 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {colab.notebook_open_url && (
                    <Button variant="primary" size="sm" icon={ExternalLink} href={colab.notebook_open_url} target="_blank" rel="noopener noreferrer">
                      Open notebook in Colab
                    </Button>
                  )}
                  {colab.notebook_download_url && (
                    <Button size="sm" icon={Download} href={apiUrl(colab.notebook_download_url)} download="02_colab_backend.ipynb">
                      Download notebook
                    </Button>
                  )}
                </div>
              )}
              {i === last && (
                <div className="mt-2 space-y-2">
                  <label className="label" htmlFor="conn-code">Connection code</label>
                  <div className="flex flex-wrap gap-2">
                    <input
                      id="conn-code"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && code.trim() && !busy) connect(); }}
                      placeholder="S3D1.…"
                      spellCheck={false}
                      autoComplete="off"
                      className="field min-w-[220px] flex-1 font-mono"
                    />
                    <Button icon={ClipboardPaste} onClick={paste}>Paste</Button>
                    <Button variant="primary" icon={Plug} loading={busy} disabled={!code.trim()} onClick={connect}>Connect</Button>
                  </div>
                  {error && <ErrorBanner error={error} title="Could not connect to the worker" />}
                </div>
              )}
            </div>
          </li>
        ))}
        {steps.length === 0 && (
          <li className="text-sm text-slate-400">The backend did not provide setup steps. Open the notebook, run all cells and paste the printed connection code.</li>
        )}
      </ol>

      <details className="group mt-5 rounded-lg border border-line-soft bg-ink-800/60 px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-slate-200">What does the notebook do?</summary>
        <p className="mt-2 text-sm text-slate-400">
          It installs a CUDA build of COLMAP and the neural model, starts this app&apos;s reconstruction engine on the Colab GPU, opens a private tunnel to it
          and prints the connection code. Your photos are sent only to your own Colab session. Stop the notebook to disconnect.
        </p>
      </details>
    </div>
  );
}

/** Settings card: execution target radios, live status, Colab connection steps. */
export default function ExecutionCard() {
  const { data: exec, error, loading, refresh, setData } = useExecution({ pollMs: 5000 });
  const [busyMode, setBusyMode] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const choose = async (mode) => {
    if (!exec || exec.mode === mode) return;
    setBusyMode(mode);
    setActionError(null);
    try {
      setData(await setExecution({ mode }));
    } catch (e) {
      setActionError(e);
    } finally {
      setBusyMode(null);
    }
  };
  const disconnect = async () => {
    setDisconnecting(true);
    setActionError(null);
    try {
      setData(await disconnectWorker());
    } catch (e) {
      setActionError(e);
    } finally {
      setDisconnecting(false);
    }
  };

  const connected = !!(exec && exec.remote && exec.remote.connected);
  const wantsWorker = !!exec && (exec.mode === 'remote' || exec.mode === 'auto');

  return (
    <Card title="Execution" subtitle="Where experiments run: this computer or a Google Colab GPU worker." actions={<Button size="sm" onClick={refresh}>Refresh</Button>}>
      {loading && !exec ? (
        <div className="space-y-3"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
      ) : !exec ? (
        <ErrorBanner error={error || 'No execution information available.'} title="Could not load the execution settings" onRetry={refresh} />
      ) : (
        <div className="space-y-5">
          {error && <Alert tone="warn" title="Backend not reachable; showing the last known state">{error.message}</Alert>}
          {actionError && <ErrorBanner error={actionError} title="Could not change the execution target" />}

          <div role="radiogroup" aria-label="Execution target" className="grid gap-3 lg:grid-cols-3">
            {MODES.map((m) => {
              const selected = exec.mode === m.value;
              return (
                <button
                  key={m.value}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={busyMode !== null}
                  onClick={() => choose(m.value)}
                  className={`flex items-start gap-3 rounded-xl border p-4 text-left transition disabled:cursor-wait
                    ${selected ? 'border-brand-blue bg-blue-500/10 shadow-glow' : 'border-line bg-ink-900/60 hover:border-line-strong'}`}
                >
                  <span className={`mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 ${selected ? 'border-brand-blue' : 'border-slate-500'}`}>
                    {selected && <span className="h-2 w-2 rounded-full bg-brand-blue" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-white">{m.title}{m.suffix ? <span className="font-normal text-slate-400"> {m.suffix}</span> : null}</span>
                    <span className="mt-0.5 block text-xs text-slate-400">{m.desc}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="rounded-lg border border-line-soft bg-ink-900/50 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-200">
              <Cloud className="h-4 w-4 text-slate-400" aria-hidden />
              Runs on: <strong className="text-white">{exec.effective === 'remote' ? `Colab GPU worker${exec.remote && exec.remote.gpu_name ? ` (${exec.remote.gpu_name})` : ''}` : 'This computer'}</strong>
            </div>
            {exec.reason && <p className="mt-1 text-xs text-slate-400">{exec.reason}</p>}
          </div>

          <StatusChips exec={exec} />

          {connected && (
            <Alert tone="ok" title={`Connected to the Colab GPU worker${exec.remote.gpu_name ? ` (${exec.remote.gpu_name})` : ''}`}>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-1.5 text-sm"><CheckCircle2 className="h-4 w-4" aria-hidden /> New experiments run on the worker{exec.mode === 'local' ? ' once you choose Colab or Automatic' : ''}.</span>
                <Button size="sm" variant="danger" icon={Unplug} loading={disconnecting} onClick={disconnect}>Disconnect</Button>
              </div>
            </Alert>
          )}
          {wantsWorker && !connected && <ColabPanel exec={exec} onUpdate={setData} />}
        </div>
      )}
    </Card>
  );
}

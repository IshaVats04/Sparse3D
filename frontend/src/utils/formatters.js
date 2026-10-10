export function formatDuration(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return 'n/a';
  const s = Math.max(0, Math.round(Number(sec)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h ${m}m ${r}s`;
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
}

export function formatNumber(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 'n/a';
  const n = Number(v);
  if (Number.isInteger(n) && Math.abs(n) >= 1000) return n.toLocaleString();
  return n.toFixed(digits);
}

export function formatInt(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 'n/a';
  return Math.round(Number(v)).toLocaleString();
}

export function formatPercent(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 'n/a';
  return `${Number(v).toFixed(digits)}%`;
}

export function formatSigned(v, digits = 1) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 'n/a';
  const n = Number(v);
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return 'n/a';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(value) {
  if (!value) return 'n/a';
  const d = new Date(String(value).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

export function titleCase(s) {
  if (!s) return '';
  return String(s)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fileExt(name = '') {
  const i = name.lastIndexOf('.');
  return i < 0 ? '' : name.slice(i + 1).toLowerCase();
}

export function truncateMiddle(name, max = 22) {
  if (!name || name.length <= max) return name;
  const keep = Math.floor((max - 1) / 2);
  return `${name.slice(0, keep)}…${name.slice(name.length - keep)}`;
}

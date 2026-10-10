// Single place for all network access. Base URL comes from localStorage 'sparse3d.apiBase'
// ('' = same origin, which the Vite dev proxy forwards to the backend).
import { STORAGE_KEYS } from '../utils/constants';

export class ApiError extends Error {
  constructor(message, status = 0, detail = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

// ---------- base URL ----------
export function getApiBase() {
  try {
    return (localStorage.getItem(STORAGE_KEYS.apiBase) || '').trim().replace(/\/+$/, '');
  } catch {
    return '';
  }
}

export function setApiBase(value) {
  const v = (value || '').trim().replace(/\/+$/, '');
  try {
    if (v) localStorage.setItem(STORAGE_KEYS.apiBase, v);
    else localStorage.removeItem(STORAGE_KEYS.apiBase);
  } catch {
    /* storage unavailable: ignore */
  }
  return v;
}

// ---------- mock mode ----------
function initMock() {
  let on = import.meta.env.VITE_MOCK === '1' || import.meta.env.VITE_MOCK === 'true';
  try {
    const q = new URLSearchParams(window.location.search).get('mock');
    if (q === '1') {
      sessionStorage.setItem(STORAGE_KEYS.mock, '1');
    } else if (q === '0') {
      sessionStorage.removeItem(STORAGE_KEYS.mock);
      on = false;
    }
    if (sessionStorage.getItem(STORAGE_KEYS.mock) === '1') on = true;
  } catch {
    /* ignore */
  }
  return on;
}
const MOCK = initMock();
export function isMock() {
  return MOCK;
}

let mockModule = null;
async function getMock() {
  if (!mockModule) mockModule = await import('./mock.js');
  return mockModule;
}

// Resolve an API-relative path (or absolute/blob/data URL) to a fetchable URL.
export function apiUrl(path) {
  if (!path) return path;
  if (/^(https?:|blob:|data:)/i.test(path)) return path;
  return `${getApiBase()}${path.startsWith('/') ? '' : '/'}${path}`;
}

function describeDetail(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && d.msg ? `${(d.loc || []).filter((x) => x !== 'body').join('.')}: ${d.msg}` : JSON.stringify(d)))
      .join('; ');
  }
  if (typeof detail === 'object' && detail.message) return detail.message;
  return fallback;
}

async function parseError(res) {
  let detail = null;
  try {
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('json')) {
      const body = await res.json();
      detail = body && body.detail !== undefined ? body.detail : body;
    } else {
      const text = await res.text();
      detail = text ? text.slice(0, 300) : null;
    }
  } catch {
    /* ignore */
  }
  return new ApiError(describeDetail(detail, `Request failed (${res.status} ${res.statusText})`), res.status, detail);
}

/**
 * request(path, { method, json, formData, signal })
 * Returns parsed JSON (or null for 204). Throws ApiError on network or HTTP errors.
 */
export async function request(path, { method = 'GET', json, formData, signal } = {}) {
  if (MOCK) {
    const mock = await getMock();
    return mock.handle(method, path, { json, formData });
  }
  const init = { method, signal, headers: { Accept: 'application/json' } };
  if (formData) {
    init.body = formData;
  } else if (json !== undefined) {
    init.body = JSON.stringify(json);
    init.headers['Content-Type'] = 'application/json';
  }
  let res;
  try {
    res = await fetch(apiUrl(path), init);
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    const base = getApiBase();
    throw new ApiError(
      `Cannot reach the backend${base ? ` at ${base}` : ''}. Check that it is running or update the API URL in Settings.`,
      0,
    );
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  if (!ct.includes('json')) return null;
  return res.json();
}

/** Fetch a file as a Blob (downloads). Throws ApiError with a readable message. */
export async function requestBlob(path, { signal } = {}) {
  if (MOCK) {
    const mock = await getMock();
    return mock.handleBlob(path);
  }
  let res;
  try {
    res = await fetch(apiUrl(path), { signal });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new ApiError('Cannot reach the backend. Check that it is running or update the API URL in Settings.', 0);
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const cd = res.headers.get('content-disposition') || '';
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  return { blob, filename: m ? decodeURIComponent(m[1]) : null };
}

/** Fetch an arbitrary URL as ArrayBuffer-ish text for viewers. */
export async function fetchBuffer(url, { signal } = {}) {
  let res;
  try {
    res = await fetch(apiUrl(url), { signal });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new ApiError('Cannot reach the backend to load this file.', 0);
  }
  if (!res.ok) throw await parseError(res);
  return res.arrayBuffer();
}

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

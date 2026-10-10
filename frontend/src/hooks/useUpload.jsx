import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { useParams } from 'react-router-dom';
import { validateImages, listExamples } from '../services/experimentService';
import {
  DEFAULT_CONFIG, IMAGE_EXTENSIONS, MAX_IMAGES, MAX_IMAGE_BYTES, MIN_IMAGES, STORAGE_KEYS,
} from '../utils/constants';
import { fileExt, formatBytes } from '../utils/formatters';
import { datasetCount, datasetKey } from '../utils/datasets';

const WizardContext = createContext(null);

function readJobId() {
  try {
    return sessionStorage.getItem(STORAGE_KEYS.jobId) || null;
  } catch {
    return null;
  }
}

let fileCounter = 0;

/**
 * Shared wizard state: selected files / example set, validation result,
 * configuration, ground-truth file and the current job id (persisted in sessionStorage).
 */
export function WizardProvider({ children }) {
  const [files, setFiles] = useState([]); // [{id, file, name, size, url}]
  const [exampleId, setExampleId] = useState(null);
  const [exampleImages, setExampleImages] = useState([]); // [{name, url}]
  const [exampleName, setExampleName] = useState('');
  const [notices, setNotices] = useState([]); // client-side add errors (strings)
  const [validation, setValidation] = useState(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [config, setConfigState] = useState(DEFAULT_CONFIG);
  const [groundTruth, setGroundTruth] = useState(null);
  const [jobId, setJobIdState] = useState(readJobId);
  const [dataset, setDatasetState] = useState(null); // see utils/datasets.js
  const urlsRef = useRef(new Set());

  const imageCount = dataset ? datasetCount(dataset) : exampleId ? exampleImages.length : files.length;

  // ---------- job id ----------
  const setJobId = useCallback((id) => {
    setJobIdState(id || null);
    try {
      if (id) sessionStorage.setItem(STORAGE_KEYS.jobId, id);
      else sessionStorage.removeItem(STORAGE_KEYS.jobId);
    } catch {
      /* ignore */
    }
  }, []);

  // ---------- files ----------
  const revoke = useCallback((entry) => {
    if (entry && entry.url) {
      URL.revokeObjectURL(entry.url);
      urlsRef.current.delete(entry.url);
    }
  }, []);

  useEffect(() => {
    const urls = urlsRef.current;
    return () => {
      urls.forEach((u) => URL.revokeObjectURL(u));
      urls.clear();
    };
  }, []);

  const addFiles = useCallback((incoming) => {
    const list = Array.from(incoming || []);
    if (!list.length) return;
    const msgs = [];
    const base = exampleId || dataset ? [] : files;
    const next = [...base];
    for (const file of list) {
      const ext = fileExt(file.name);
      if (!IMAGE_EXTENSIONS.includes(ext) && !/^image\/(jpeg|png)$/.test(file.type)) {
        msgs.push(`"${file.name}" is not a supported image type (JPG, PNG, BMP, WebP or TIFF).`);
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        msgs.push(`"${file.name}" is ${formatBytes(file.size)}; the limit is 10 MB per image.`);
        continue;
      }
      if (next.some((f) => f.name === file.name && f.size === file.size)) {
        msgs.push(`"${file.name}" was already added.`);
        continue;
      }
      if (next.length >= MAX_IMAGES) {
        msgs.push(`Maximum ${MAX_IMAGES} images: "${file.name}" was not added.`);
        continue;
      }
      const url = URL.createObjectURL(file);
      if (url) urlsRef.current.add(url);
      fileCounter += 1;
      next.push({ id: `f${fileCounter}`, file, name: file.name, size: file.size, url });
    }
    if (exampleId) {
      setExampleId(null);
      setExampleImages([]);
      setExampleName('');
    }
    if (dataset) setDatasetState(null);
    setFiles(next);
    setNotices(msgs);
  }, [exampleId, dataset, files]);

  const removeFile = useCallback((id) => {
    const target = files.find((f) => f.id === id);
    revoke(target);
    setFiles(files.filter((f) => f.id !== id));
    setNotices([]);
  }, [files, revoke]);

  const clearAll = useCallback(() => {
    files.forEach(revoke);
    setFiles([]);
    setExampleId(null);
    setExampleImages([]);
    setExampleName('');
    setDatasetState(null);
    setValidation(null);
    setValidationError(null);
    setNotices([]);
  }, [files, revoke]);

  const selectExample = useCallback((example) => {
    files.forEach(revoke);
    setFiles([]);
    setExampleId(example.id);
    setExampleName(example.name || example.id);
    setExampleImages(example.images || []);
    setDatasetState(null);
    setNotices([]);
  }, [files, revoke]);

  /** Select (or clear with null) a local-dataset scan / camera selection. */
  const setDataset = useCallback((ds) => {
    if (ds) {
      files.forEach(revoke);
      setFiles([]);
      setExampleId(null);
      setExampleImages([]);
      setExampleName('');
      setNotices([]);
    }
    setDatasetState(ds);
  }, [files, revoke]);

  // ---------- validation ----------
  const validationToken = useRef(0);
  const filesKey = files.map((f) => `${f.name}:${f.size}`).join('|');
  useEffect(() => {
    const count = dataset ? datasetCount(dataset) : exampleId ? exampleImages.length : files.length;
    if (count < (dataset ? MIN_IMAGES : 1)) {
      setValidation(null);
      setValidationError(null);
      setValidating(false);
      return undefined;
    }
    const token = ++validationToken.current;
    setValidating(true);
    setValidationError(null);
    const timer = setTimeout(() => {
      validateImages({ files: files.map((f) => f.file), exampleId, dataset })
        .then((res) => {
          if (validationToken.current !== token) return;
          setValidation(res);
          setValidating(false);
        })
        .catch((e) => {
          if (validationToken.current !== token) return;
          setValidation(null);
          setValidationError(e);
          setValidating(false);
        });
    }, 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filesKey, exampleId, exampleImages.length, datasetKey(dataset)]);

  // ---------- configuration ----------
  const setConfig = useCallback((patch) => {
    setConfigState((c) => ({ ...c, ...patch }));
  }, []);

  // Keep num_views consistent with the number of images.
  useEffect(() => {
    if (imageCount === 0) return;
    setConfigState((c) => {
      const max = Math.min(MAX_IMAGES, Math.max(MIN_IMAGES, imageCount));
      let nv = c.num_views;
      if (c.view_arrangement === 'auto') nv = max;
      else nv = Math.min(Math.max(nv, MIN_IMAGES), max);
      return nv === c.num_views ? c : { ...c, num_views: nv };
    });
  }, [imageCount, config.view_arrangement]);

  const value = useMemo(() => ({
    files, exampleId, exampleName, exampleImages, imageCount, notices,
    validation, validating, validationError,
    config, groundTruth, jobId, dataset,
    addFiles, setDataset, removeFile, clearAll, selectExample, setConfig, setGroundTruth, setJobId,
  }), [
    files, exampleId, exampleName, exampleImages, imageCount, notices, validation, validating,
    validationError, config, groundTruth, jobId, dataset, setDataset, addFiles, removeFile, clearAll, selectExample,
    setConfig, setJobId,
  ]);

  return <WizardContext.Provider value={value}>{children}</WizardContext.Provider>;
}

export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error('useWizard must be used inside <WizardProvider>');
  return ctx;
}

// Convenience alias used by pages: `const { files } = useUpload()`.
export const useUpload = useWizard;

/** Resolve the job id from the route param or the persisted current job; keeps context in sync. */
export function useActiveJobId() {
  const { jobId: param } = useParams();
  const { jobId: current, setJobId } = useWizard();
  useEffect(() => {
    if (param && param !== current) setJobId(param);
  }, [param, current, setJobId]);
  return param || current || null;
}

/** Fetch the example sets once (Upload page + sweep panel). */
export function useExamples() {
  const [state, setState] = useState({ examples: [], loading: true, error: null });
  const load = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    listExamples()
      .then((examples) => setState({ examples: Array.isArray(examples) ? examples : [], loading: false, error: null }))
      .catch((error) => setState({ examples: [], loading: false, error }));
  }, []);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

import { useRef, useState } from 'react';
import { UploadCloud } from 'lucide-react';
import { IMAGE_ACCEPT, MAX_IMAGES, MIN_IMAGES } from '../../utils/constants';

export default function Dropzone({ onFiles, disabled = false, compact = false, hint }) {
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);

  const open = () => { if (!disabled) inputRef.current?.click(); };
  const onDrop = (e) => {
    e.preventDefault();
    setOver(false);
    if (disabled) return;
    onFiles(e.dataTransfer.files);
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Upload images: drag and drop or press Enter to browse"
      onClick={open}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed text-center transition
        ${compact ? 'px-4 py-6' : 'px-6 py-12'}
        ${over ? 'border-brand-blue bg-blue-500/10' : 'border-line-strong bg-ink-800/60 hover:border-brand-blue/70 hover:bg-ink-800'}
        ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-blue-500/10 text-brand-blue">
        <UploadCloud className="h-7 w-7" aria-hidden />
      </div>
      <p className="text-base font-medium text-white">Drag &amp; drop images here or click to browse</p>
      <p className="mt-1 text-xs text-slate-400">JPG, PNG, BMP, WebP, TIFF - Max 10MB each</p>
      <p className="mt-0.5 text-xs text-slate-500">{hint || `Minimum ${MIN_IMAGES} images - Maximum ${MAX_IMAGES} images`}</p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={IMAGE_ACCEPT}
        className="hidden"
        tabIndex={-1}
        onChange={(e) => { onFiles(e.target.files); e.target.value = ''; }}
      />
    </div>
  );
}

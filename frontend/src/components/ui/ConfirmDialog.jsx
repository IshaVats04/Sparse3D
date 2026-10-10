import { useEffect, useRef } from 'react';
import Button from './Button';

/** Modal dialog. Closes on Escape / backdrop click. */
export function Modal({ open, onClose, title, children, footer, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const prev = document.activeElement;
    ref.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      if (prev && prev.focus) prev.focus();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="presentation">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`relative max-h-[90vh] w-full overflow-y-auto rounded-xl border border-line bg-ink-800 p-6 shadow-2xl outline-none ${wide ? 'max-w-3xl' : 'max-w-md'}`}
      >
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <div className="mt-2 text-sm text-slate-300">{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export default function ConfirmDialog({
  open, title, children, confirmLabel = 'Confirm', danger = false, busy = false, onConfirm, onCancel,
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={(
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>Cancel</Button>
          <Button variant={danger ? 'danger' : 'primary'} loading={busy} onClick={onConfirm}>{confirmLabel}</Button>
        </>
      )}
    >
      {children}
    </Modal>
  );
}

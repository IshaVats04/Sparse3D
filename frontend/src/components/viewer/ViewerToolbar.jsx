import { Grid3x3, Maximize2, Minimize2, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';

function ToolButton({ label, onClick, active, disabled, children }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active === undefined ? undefined : active}
      disabled={disabled}
      onClick={onClick}
      className={`flex h-8 w-8 items-center justify-center rounded-lg border text-slate-200 backdrop-blur transition
        disabled:cursor-not-allowed disabled:opacity-40
        ${active ? 'border-brand-blue bg-blue-500/30 text-white' : 'border-line bg-ink-900/80 hover:bg-ink-600'}`}
    >
      {children}
    </button>
  );
}

/** Vertical icon toolbar overlaid on a viewport. */
export default function ViewerToolbar({
  onZoomIn, onZoomOut, onReset, onFullscreen, fullscreen, wireframe, onWireframe, wireframeDisabled,
}) {
  return (
    <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5" role="toolbar" aria-orientation="vertical" aria-label="Viewer tools">
      <ToolButton label="Zoom in" onClick={onZoomIn}><ZoomIn className="h-4 w-4" /></ToolButton>
      <ToolButton label="Zoom out" onClick={onZoomOut}><ZoomOut className="h-4 w-4" /></ToolButton>
      <ToolButton label="Reset view" onClick={onReset}><RotateCcw className="h-4 w-4" /></ToolButton>
      <ToolButton label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'} onClick={onFullscreen}>
        {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
      </ToolButton>
      <ToolButton
        label={wireframeDisabled ? 'Wireframe (mesh modes only)' : 'Toggle wireframe'}
        onClick={onWireframe}
        active={wireframe}
        disabled={wireframeDisabled}
      >
        <Grid3x3 className="h-4 w-4" />
      </ToolButton>
    </div>
  );
}

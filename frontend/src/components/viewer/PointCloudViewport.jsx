import { useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { GizmoHelper, GizmoViewport, OrbitControls } from '@react-three/drei';
import { DoubleSide, Vector3 } from 'three';
import { Loader2, RefreshCw } from 'lucide-react';
import ViewerToolbar from './ViewerToolbar';
import { BACKGROUNDS, DEFAULT_VIEW_OPTIONS, ORIENTATIONS } from './ViewOptionsMenu';
import { buildFrustumGeometry, computeNormalization, usePlyGeometry } from './plyUtils';
import Segmented from '../ui/Segmented';
import ErrorBoundary from '../ui/ErrorBoundary';
import { formatInt } from '../../utils/formatters';

const HOME = [2.4, 1.7, 3.2];

function Frustums({ cameras, center, size }) {
  const geoms = useMemo(
    () => cameras
      .filter((c) => Array.isArray(c.position) && c.position.length === 3 && c.position.every(Number.isFinite))
      .map((c) => ({ name: c.name, geometry: buildFrustumGeometry(c.position, center, size) })),
    [cameras, center, size],
  );
  useEffect(() => () => geoms.forEach((g) => g.geometry.dispose()), [geoms]);
  return (
    <>
      {geoms.map((g) => (
        <lineSegments key={g.name} geometry={g.geometry}>
          <lineBasicMaterial color="#fbbf24" />
        </lineSegments>
      ))}
    </>
  );
}

function Scene({ pc, mesh, mode, options, cameras, wireframe, apiRef, controlsRef, camera: cam }) {
  const base = mode === 'points' ? (pc || mesh) : (mesh || pc);
  const norm = useMemo(() => (base ? computeNormalization(base) : null), [base]);
  const orientation = ORIENTATIONS[options.orientation] || ORIENTATIONS['y-up'];

  useEffect(() => {
    apiRef.current = {
      zoom(factor) {
        const ctl = controlsRef.current;
        if (!ctl) return;
        const dir = new Vector3().subVectors(cam.position, ctl.target).multiplyScalar(factor);
        cam.position.copy(ctl.target).add(dir);
        ctl.update();
      },
      reset() {
        const ctl = controlsRef.current;
        cam.position.set(...HOME);
        if (ctl) { ctl.target.set(0, 0, 0); ctl.update(); }
      },
    };
  }, [apiRef, controlsRef, cam]);

  const hasColor = (g) => !!(g && g.getAttribute('color'));
  const meshHasFaces = !!(mesh && mesh.index);
  const showMesh = mode !== 'points' && mesh && meshHasFaces;
  const pointsGeom = showMesh ? null : (mode === 'points' ? (pc || (mesh && !meshHasFaces ? mesh : null)) : (mesh && !meshHasFaces ? mesh : pc));

  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[3, 5, 4]} intensity={1.2} />
      <directionalLight position={[-4, -2, -3]} intensity={0.35} />
      {options.showAxes && <axesHelper args={[1.6]} />}
      {norm && (
        <group rotation={orientation.rotation}>
          <group scale={norm.scale} position={[-norm.center.x * norm.scale, -norm.center.y * norm.scale, -norm.center.z * norm.scale]}>
            {pointsGeom && (
              <points geometry={pointsGeom}>
                <pointsMaterial
                  size={options.pointSize * 0.006}
                  sizeAttenuation
                  vertexColors={hasColor(pointsGeom)}
                  color={hasColor(pointsGeom) ? '#ffffff' : '#9db4ff'}
                />
              </points>
            )}
            {showMesh && (
              <mesh geometry={mesh}>
                <meshStandardMaterial
                  vertexColors={mode === 'textured' && hasColor(mesh)}
                  color={mode === 'textured' && hasColor(mesh) ? '#ffffff' : '#93a4ff'}
                  wireframe={wireframe}
                  side={DoubleSide}
                  flatShading={!mesh.getAttribute('normal')}
                  roughness={0.7}
                  metalness={0.05}
                />
              </mesh>
            )}
            {options.showCameras && cameras && cameras.length > 0 && (
              <Frustums cameras={cameras} center={norm.center} size={0.18 / norm.scale} />
            )}
          </group>
        </group>
      )}
      <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.1} autoRotate={options.autoRotate} autoRotateSpeed={1.2} />
      <GizmoHelper alignment="bottom-left" margin={[56, 56]}>
        <GizmoViewport axisColors={['#ef4444', '#22c55e', '#3b82f6']} labelColor="white" />
      </GizmoHelper>
    </>
  );
}

function CanvasWithScene(props) {
  const { options } = props;
  const apiRef = props.apiRef;
  const controlsRef = useRef(null);
  return (
    <Canvas
      dpr={[1, 2]}
      frameloop={options.autoRotate ? 'always' : 'demand'}
      camera={{ position: HOME, fov: 45, near: 0.01, far: 200 }}
      gl={{ antialias: true }}
      onCreated={({ camera }) => { camera.lookAt(0, 0, 0); }}
    >
      <color attach="background" args={[BACKGROUNDS[options.background]?.color || '#05070f']} />
      <SceneBridge {...props} apiRef={apiRef} controlsRef={controlsRef} />
    </Canvas>
  );
}

// Grabs the R3F camera and hands it to Scene (keeps Scene free of store hooks for easier testing).
function SceneBridge(props) {
  const camera = useThree((s) => s.camera);
  return <Scene {...props} camera={camera} />;
}

/**
 * WebGL viewport for one reconstruction result.
 * Loads result.files.point_cloud (and result.files.mesh on demand) with PLYLoader.
 */
export default function PointCloudViewport({
  result, options = DEFAULT_VIEW_OPTIONS, height = 420, showModeSwitch = true, className = '',
}) {
  const files = (result && result.files) || {};
  const pcUrl = files.point_cloud || null;
  const meshUrl = files.mesh || null;
  const [mode, setMode] = useState(pcUrl ? 'points' : meshUrl ? 'mesh' : 'points');
  const [wireframe, setWireframe] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef(null);
  const apiRef = useRef({});

  const needMesh = !!meshUrl && (mode !== 'points' || !pcUrl);
  const pc = usePlyGeometry(pcUrl, !!pcUrl);
  const mesh = usePlyGeometry(meshUrl, needMesh);

  useEffect(() => {
    const onFs = () => setFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener('fullscreenchange', onFs);
    return () => document.removeEventListener('fullscreenchange', onFs);
  }, []);

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else el.requestFullscreen?.().catch(() => {});
  };

  const active = mode === 'points' ? pc : mesh;
  const nothing = !pcUrl && !meshUrl;
  const meshUnavailable = !meshUrl;
  const info = [];
  if (result && result.point_count != null) info.push(`${formatInt(result.point_count)} pts`);
  if (result && result.mesh) info.push(`${formatInt(result.mesh.triangle_count)} tris`);

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden rounded-xl border border-line ${className}`}
      style={{ height, background: BACKGROUNDS[options.background]?.color }}
    >
      {nothing ? (
        <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-400">
          This run did not produce a point cloud or mesh file.
        </div>
      ) : (
        <>
          <ErrorBoundary
            resetKey={options.background}
            fallback={(e) => (
              <div className="flex h-full items-center justify-center px-6 text-center text-sm text-red-300">
                The 3D view could not start (WebGL may be unavailable): {String(e.message || e)}
              </div>
            )}
          >
            <CanvasWithScene
              pc={pc.geometry}
              mesh={mesh.geometry}
              mode={mode}
              options={options}
              cameras={result ? result.cameras : null}
              wireframe={wireframe}
              apiRef={apiRef}
            />
          </ErrorBoundary>

          {active.loading && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/30" role="status">
              <span className="inline-flex items-center gap-2 rounded-full bg-ink-900/90 px-4 py-2 text-sm text-slate-200">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Loading {mode === 'points' ? 'point cloud' : 'mesh'}...
              </span>
            </div>
          )}
          {active.error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink-950/80 px-6 text-center" role="alert">
              <p className="text-sm text-red-300">Could not load the {mode === 'points' ? 'point cloud' : 'mesh'}: {active.error.message}</p>
              <button type="button" onClick={active.retry} className="inline-flex items-center gap-2 rounded-lg border border-line bg-ink-700 px-3 py-1.5 text-xs text-white hover:bg-ink-600">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
              </button>
            </div>
          )}

          <ViewerToolbar
            onZoomIn={() => apiRef.current.zoom?.(0.8)}
            onZoomOut={() => apiRef.current.zoom?.(1.25)}
            onReset={() => apiRef.current.reset?.()}
            onFullscreen={toggleFullscreen}
            fullscreen={fullscreen}
            wireframe={wireframe}
            onWireframe={() => setWireframe((w) => !w)}
            wireframeDisabled={mode === 'points'}
          />

          {info.length > 0 && (
            <div className="pointer-events-none absolute bottom-3 right-3 rounded-md bg-black/50 px-2 py-1 font-mono text-[11px] text-slate-300">
              {info.join(' | ')}
            </div>
          )}

          {showModeSwitch && (
            <div className="absolute inset-x-0 bottom-3 flex justify-center">
              <Segmented
                label="Render mode"
                value={mode}
                onChange={setMode}
                className="shadow-lg"
                options={[
                  { value: 'points', label: 'Point Cloud', disabled: !pcUrl, title: pcUrl ? undefined : 'No point cloud file' },
                  { value: 'mesh', label: 'Mesh', disabled: meshUnavailable, title: meshUnavailable ? 'No mesh was generated for this run (enable Generate Mesh)' : undefined },
                  { value: 'textured', label: 'Textured', disabled: meshUnavailable, title: meshUnavailable ? 'No mesh was generated for this run (enable Generate Mesh)' : undefined },
                ]}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

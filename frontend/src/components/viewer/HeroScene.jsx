import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float32BufferAttribute, LatheGeometry, Vector2, Color } from 'three';

// Decorative vase (not data): half solid, half wireframe + point cloud, slowly rotating.
function buildVase() {
  const pts = [];
  const N = 42;
  for (let i = 0; i <= N; i += 1) {
    const t = i / N;
    const y = (t - 0.5) * 2.2;
    const body = 0.42 + 0.34 * Math.sin(Math.PI * Math.min(1, t * 1.15)) ** 1.2;
    const neck = t > 0.72 ? 0.2 + 0.22 * (1 - (t - 0.72) / 0.28) ** 2 : 0;
    const lip = t > 0.96 ? 0.07 * ((t - 0.96) / 0.04) : 0;
    const base = t < 0.06 ? -0.12 * (1 - t / 0.06) : 0;
    const r = t > 0.72 ? Math.max(0.2, neck + 0.04 + lip) : Math.max(0.2, body + base);
    pts.push(new Vector2(r, y));
  }
  return pts;
}

function colorize(geometry) {
  const pos = geometry.getAttribute('position');
  const colors = new Float32Array(pos.count * 3);
  const a = new Color('#3b82f6');
  const b = new Color('#8b5cf6');
  const c = new Color('#e5e7eb');
  const tmp = new Color();
  for (let i = 0; i < pos.count; i += 1) {
    const y = pos.getY(i);
    const t = (y + 1.1) / 2.2;
    const band = Math.abs(Math.sin(t * 16)) > 0.92 ? 1 : 0;
    tmp.copy(a).lerp(b, t);
    if (band) tmp.lerp(c, 0.7);
    colors[i * 3] = tmp.r;
    colors[i * 3 + 1] = tmp.g;
    colors[i * 3 + 2] = tmp.b;
  }
  geometry.setAttribute('color', new Float32BufferAttribute(colors, 3));
}

function Vase() {
  const group = useRef(null);
  const { solid, wire } = useMemo(() => {
    const profile = buildVase();
    const s = new LatheGeometry(profile, 48, 0, Math.PI);
    const w = new LatheGeometry(profile, 28, Math.PI, Math.PI);
    colorize(s);
    colorize(w);
    return { solid: s, wire: w };
  }, []);
  useEffect(() => () => { solid.dispose(); wire.dispose(); }, [solid, wire]);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.35;
  });
  return (
    <group ref={group} rotation={[0.12, 0, 0]}>
      <mesh geometry={solid}>
        <meshStandardMaterial vertexColors side={2} roughness={0.45} metalness={0.15} />
      </mesh>
      <mesh geometry={wire}>
        <meshBasicMaterial vertexColors wireframe transparent opacity={0.85} />
      </mesh>
      <points geometry={wire}>
        <pointsMaterial size={0.035} vertexColors sizeAttenuation />
      </points>
    </group>
  );
}

export default function HeroScene() {
  return (
    <Canvas dpr={[1, 2]} camera={{ position: [0, 0.2, 4.2], fov: 38 }} gl={{ alpha: true, antialias: true }}>
      <ambientLight intensity={0.8} />
      <directionalLight position={[3, 4, 5]} intensity={1.6} color="#c7d2fe" />
      <pointLight position={[-3, -1, 2]} intensity={12} color="#8b5cf6" />
      <Vase />
    </Canvas>
  );
}

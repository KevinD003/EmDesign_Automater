import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react';
import { Canvas } from '@react-three/fiber';
import * as THREE from 'three';
import type { ColorStop, Stitch } from '../../types/design';
import { buildThreadScene } from '../../lib/thread3d';

interface TrueView3DProps {
  stitches?: Stitch[];
  colorStops?: ColorStop[];
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Thread tubes for one scene — one TubeGeometry mesh per color run. */
function Threads({ stitches, colorStops }: TrueView3DProps) {
  const scene = useMemo(() => buildThreadScene(stitches ?? [], colorStops ?? []), [stitches, colorStops]);
  const radius = Math.max(scene.extent * 0.006, 0.18); // ~thread thickness relative to design size

  const meshes = useMemo(() => {
    return scene.paths.map((p) => {
      const curve = new THREE.CatmullRomCurve3(p.points.map(([x, y, z]) => new THREE.Vector3(x, y, z)));
      const segments = clamp(p.points.length, 2, 4000);
      return { geometry: new THREE.TubeGeometry(curve, segments, radius, 5, false), color: p.color };
    });
  }, [scene, radius]);

  // Dispose geometries when they change / on unmount.
  useEffect(() => () => meshes.forEach((m) => m.geometry.dispose()), [meshes]);

  return (
    <group>
      {meshes.map((m, i) => (
        <mesh key={i} geometry={m.geometry}>
          <meshStandardMaterial color={m.color} roughness={0.4} metalness={0.05} />
        </mesh>
      ))}
    </group>
  );
}

/**
 * TrueView 3D realistic preview (spec §4.7): renders stitches as lit thread tubes on a
 * fabric plane. Drag to rotate, scroll to zoom. No OrbitControls dep — rotation/zoom are
 * local state applied to the scene group + camera distance.
 *
 * NOTE: visual output is not automatically verifiable (headless). The geometry builder
 * (lib/thread3d.ts) is unit-tested; the render itself needs a human eyeball.
 */
export function TrueView3D({ stitches = [], colorStops = [] }: TrueView3DProps) {
  const scene = useMemo(() => buildThreadScene(stitches, colorStops), [stitches, colorStops]);
  const [rot, setRot] = useState({ x: -0.55, y: 0 });
  const [zoom, setZoom] = useState(1);
  const drag = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    setRot({ x: -0.55, y: 0 });
    setZoom(1);
  }, [stitches]);

  if (stitches.length === 0) {
    return (
      <div className="canvas-wrap">
        <div className="canvas-overlay">
          <p className="canvas-title">TrueView 3D</p>
          <p className="muted">Load or create a design to see the 3D thread preview.</p>
        </div>
      </div>
    );
  }

  const dist = (scene.extent * 1.7) / zoom;
  const onDown = (e: ReactPointerEvent) => {
    drag.current = { x: e.clientX, y: e.clientY };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: ReactPointerEvent) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.x;
    const dy = e.clientY - drag.current.y;
    drag.current = { x: e.clientX, y: e.clientY };
    setRot((r) => ({ x: clamp(r.x + dy * 0.01, -1.5, 0.4), y: r.y + dx * 0.01 }));
  };
  const onUp = () => {
    drag.current = null;
  };
  const onWheel = (e: ReactWheelEvent) => {
    setZoom((z) => clamp(z * (e.deltaY > 0 ? 0.9 : 1.1), 0.3, 6));
  };

  const fabric = scene.extent * 1.5;

  return (
    <div
      className="trueview-wrap"
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerLeave={onUp}
      onWheel={onWheel}
    >
      <Canvas camera={{ position: [0, 0, dist], fov: 42, near: 0.1, far: dist * 12 }}>
        <color attach="background" args={['#0c0e12']} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[dist, dist, dist]} intensity={1.15} />
        <directionalLight position={[-dist, 0, dist * 0.6]} intensity={0.35} />
        <group rotation={[rot.x, rot.y, 0]}>
          <mesh position={[0, 0, -0.8]}>
            <planeGeometry args={[fabric, fabric]} />
            <meshStandardMaterial color="#e9e5db" roughness={1} />
          </mesh>
          <Threads stitches={stitches} colorStops={colorStops} />
        </group>
      </Canvas>
      <div className="canvas-badge">TrueView 3D · drag to rotate · scroll to zoom</div>
    </div>
  );
}

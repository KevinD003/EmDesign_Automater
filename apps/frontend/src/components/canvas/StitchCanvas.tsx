import { useEffect, useMemo, useState } from 'react';
import { Stage, Layer, Line } from 'react-konva';
import type { KonvaEventObject } from 'konva/lib/Node';
import type { ColorStop, Stitch } from '../../types/design';

interface StitchCanvasProps {
  stitches?: Stitch[];
  colorStops?: ColorStop[];
  /** Only render stitches up to this index (null = all). Drives the stitch-player animation. */
  limit?: number | null;
  /** Highlight this color stop (dim the others), or null for no emphasis. */
  selectedStop?: number | null;
  widthPx?: number;
  heightPx?: number;
}

interface Run {
  points: number[];
  color: string;
  stop: number; // 1-based color stop this run belongs to
}

const FALLBACK_COLORS = ['#e11d48', '#2563eb', '#16a34a', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d'];

/**
 * Canvas design editor (spec §3). Renders the raw stitch list as color-grouped
 * polylines: consecutive STITCH commands form a line; JUMP/TRIM/COLOR_CHANGE/END
 * break it. Fits the design to view; scroll to zoom, drag to pan; dims non-selected stops.
 */
export function StitchCanvas({
  stitches = [],
  colorStops = [],
  limit = null,
  selectedStop = null,
  widthPx = 900,
  heightPx = 560,
}: StitchCanvasProps) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    setScale(1);
    setPos({ x: 0, y: 0 });
  }, [stitches]);

  const fit = useMemo(() => {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const s of stitches) {
      if (s.x < minX) minX = s.x;
      if (s.y < minY) minY = s.y;
      if (s.x > maxX) maxX = s.x;
      if (s.y > maxY) maxY = s.y;
    }
    if (!Number.isFinite(minX)) return { scale: 1, offsetX: 0, offsetY: 0, w: 0, h: 0 };
    const w = Math.max(maxX - minX, 1);
    const h = Math.max(maxY - minY, 1);
    const s = Math.min(widthPx / w, heightPx / h) * 0.9;
    return {
      scale: s,
      offsetX: (widthPx - w * s) / 2 - minX * s,
      offsetY: (heightPx - h * s) / 2 - minY * s,
      w: maxX - minX,
      h: maxY - minY,
    };
  }, [stitches, widthPx, heightPx]);

  const runs = useMemo(() => {
    const out: Run[] = [];
    const n = limit == null ? stitches.length : Math.min(limit, stitches.length);
    let cur: number[] = [];
    let stopIdx = 0;
    const colorAt = (i: number) => colorStops[i]?.hex ?? FALLBACK_COLORS[i % FALLBACK_COLORS.length];
    for (let i = 0; i < n; i += 1) {
      const s = stitches[i];
      if (s.command === 'STITCH') {
        cur.push(fit.offsetX + s.x * fit.scale, fit.offsetY + s.y * fit.scale);
      } else {
        if (cur.length >= 4) out.push({ points: cur, color: colorAt(stopIdx), stop: stopIdx + 1 });
        cur = [];
        if (s.command === 'COLOR_CHANGE') stopIdx += 1;
      }
    }
    if (cur.length >= 4) out.push({ points: cur, color: colorAt(stopIdx), stop: stopIdx + 1 });
    return out;
  }, [stitches, colorStops, fit, limit]);

  if (stitches.length === 0) {
    return (
      <div className="canvas-wrap">
        <div className="canvas-overlay">
          <p className="canvas-title">No design loaded</p>
          <p className="muted">
            Click <b>Open</b> in the toolbar to load a .DST / .PES file.
          </p>
        </div>
      </div>
    );
  }

  const onWheel = (e: KonvaEventObject<WheelEvent>) => {
    e.evt.preventDefault();
    const factor = e.evt.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.max(0.2, Math.min(10, s * factor)));
  };
  const onDragEnd = (e: KonvaEventObject<DragEvent>) => {
    setPos({ x: e.target.x(), y: e.target.y() });
  };

  return (
    <div className="canvas-wrap">
      <Stage
        width={widthPx}
        height={heightPx}
        className="stitch-stage"
        draggable
        scaleX={scale}
        scaleY={scale}
        x={pos.x}
        y={pos.y}
        onWheel={onWheel}
        onDragEnd={onDragEnd}
      >
        <Layer>
          {runs.map((r, i) => {
            const active = selectedStop == null || r.stop === selectedStop;
            return (
              <Line
                key={i}
                points={r.points}
                stroke={r.color}
                strokeWidth={(r.stop === selectedStop ? 1.8 : 1) / scale}
                opacity={active ? 1 : 0.12}
                lineCap="round"
                lineJoin="round"
              />
            );
          })}
        </Layer>
      </Stage>
      <div className="canvas-badge">
        {stitches.length.toLocaleString()} stitches · {fit.w.toFixed(0)}×{fit.h.toFixed(0)} mm · scroll to zoom, drag to pan
      </div>
    </div>
  );
}

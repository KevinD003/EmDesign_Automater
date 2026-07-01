import { useEffect, useMemo, useState } from 'react';
import { Stage, Layer, Group, Line } from 'react-konva';
import type { KonvaEventObject } from 'konva/lib/Node';
import type { ColorStop, Stitch } from '../../types/design';
import { buildRuns, computeBounds } from '../../lib/stitches';

interface StitchCanvasProps {
  stitches?: Stitch[];
  colorStops?: ColorStop[];
  /** Only render stitches up to this index (null = all). Drives the stitch-player animation. */
  limit?: number | null;
  /** Highlight this color stop (dim the others), or null for no emphasis. */
  selectedStop?: number | null;
  /** Called when a run is clicked (its stop) or empty canvas is clicked (null). */
  onSelectStop?: (stop: number | null) => void;
  widthPx?: number;
  heightPx?: number;
}

/**
 * Canvas design editor (spec §3). Renders color-grouped polylines (via the pure
 * `buildRuns`) in a fit-to-view Group; the Stage handles zoom (wheel) and pan (drag).
 * Click a run to select its color stop; click empty canvas to deselect.
 */
export function StitchCanvas({
  stitches = [],
  colorStops = [],
  limit = null,
  selectedStop = null,
  onSelectStop,
  widthPx = 900,
  heightPx = 560,
}: StitchCanvasProps) {
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    setScale(1);
    setPos({ x: 0, y: 0 });
  }, [stitches]);

  const bounds = useMemo(() => computeBounds(stitches), [stitches]);
  const fit = useMemo(() => {
    const w = Math.max(bounds.maxX - bounds.minX, 1);
    const h = Math.max(bounds.maxY - bounds.minY, 1);
    const s = Math.min(widthPx / w, heightPx / h) * 0.9;
    return {
      scale: s,
      offsetX: (widthPx - w * s) / 2 - bounds.minX * s,
      offsetY: (heightPx - h * s) / 2 - bounds.minY * s,
    };
  }, [bounds, widthPx, heightPx]);
  const runs = useMemo(() => buildRuns(stitches, colorStops, limit), [stitches, colorStops, limit]);

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
  const onDragEnd = (e: KonvaEventObject<DragEvent>) => setPos({ x: e.target.x(), y: e.target.y() });
  const onStageClick = (e: KonvaEventObject<MouseEvent>) => {
    if (e.target === e.target.getStage()) onSelectStop?.(null);
  };
  const pxPerMm = fit.scale * scale; // effective px per design-mm, for constant stroke width

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
        onClick={onStageClick}
        onTap={onStageClick}
      >
        <Layer>
          <Group scaleX={fit.scale} scaleY={fit.scale} x={fit.offsetX} y={fit.offsetY}>
            {runs.map((r, i) => {
              const active = selectedStop == null || r.stop === selectedStop;
              return (
                <Line
                  key={i}
                  points={r.points}
                  stroke={r.color}
                  strokeWidth={(r.stop === selectedStop ? 2 : 1.2) / pxPerMm}
                  opacity={active ? 1 : 0.12}
                  lineCap="round"
                  lineJoin="round"
                  hitStrokeWidth={6 / pxPerMm}
                  onClick={() => onSelectStop?.(r.stop)}
                  onTap={() => onSelectStop?.(r.stop)}
                />
              );
            })}
          </Group>
        </Layer>
      </Stage>
      <div className="canvas-badge">
        {stitches.length.toLocaleString()} stitches · {(bounds.maxX - bounds.minX).toFixed(0)}×
        {(bounds.maxY - bounds.minY).toFixed(0)} mm · click a color · scroll zoom · drag pan
      </div>
    </div>
  );
}

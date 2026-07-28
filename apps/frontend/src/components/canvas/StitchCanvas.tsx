import { useEffect, useMemo, useRef, useState } from 'react';
import { Stage, Layer, Group, Line, Circle, Rect } from 'react-konva';
import type { KonvaEventObject } from 'konva/lib/Node';
import type { Group as KonvaGroup } from 'konva/lib/Group';
import type { ColorStop, Stitch } from '../../types/design';
import { buildRuns, computeBounds } from '../../lib/stitches';
import { useDesignStore } from '../../store/designStore';

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

const DEFAULT_HOOP = { minX: 0, minY: 0, maxX: 100, maxY: 100 }; // mm, when drawing on a blank canvas
const FABRIC_MARGIN_MM = 6; // fabric backdrop extends this far beyond the design bounds
const THREAD_WIDTH_MM = 0.4; // draw stitches at physical thread width (min 1.2 screen px)

/**
 * Canvas design editor (spec §3). Renders color-grouped polylines (via the pure
 * `buildRuns`); the Stage handles zoom (wheel) and pan (drag). In a manual-digitizing
 * tool (Run/Satin/Fill) it switches to DRAW mode: each click drops a point (converted
 * to design-mm via the fit Group), rendered as a live polyline for the Toolbar to commit.
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
  const groupRef = useRef<KonvaGroup>(null);
  const activeTool = useDesignStore((s) => s.activeTool);
  const draft = useDesignStore((s) => s.draft);
  const addDraftPoint = useDesignStore((s) => s.addDraftPoint);
  const drawing = activeTool !== 'select';
  const closed = activeTool === 'fill' || activeTool === 'satin';

  useEffect(() => {
    setScale(1);
    setPos({ x: 0, y: 0 });
  }, [stitches]);

  const hasStitches = stitches.length > 0;
  const bounds = useMemo(() => (hasStitches ? computeBounds(stitches) : DEFAULT_HOOP), [stitches, hasStitches]);
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

  // Blank canvas, not drawing → the "load a design" hint.
  if (!hasStitches && !drawing) {
    return (
      <div className="canvas-wrap">
        <div className="canvas-overlay">
          <p className="canvas-title">No design loaded</p>
          <p className="muted">
            Click <b>Open</b> to load a file, <b>Digitize</b> an image, or pick <b>Run/Satin/Fill</b> to draw.
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
    if (drawing) {
      const p = groupRef.current?.getRelativePointerPosition();
      if (p) addDraftPoint({ x: p.x, y: p.y });
      return;
    }
    if (e.target === e.target.getStage()) onSelectStop?.(null);
  };

  const pxPerMm = fit.scale * scale;
  const draftPts = draft.flatMap((p) => [p.x, p.y]);

  return (
    <div className="canvas-wrap">
      <Stage
        width={widthPx}
        height={heightPx}
        className="stitch-stage"
        draggable={!drawing}
        scaleX={scale}
        scaleY={scale}
        x={pos.x}
        y={pos.y}
        onWheel={onWheel}
        onDragEnd={onDragEnd}
        onClick={onStageClick}
        onTap={onStageClick}
        style={{ cursor: drawing ? 'crosshair' : 'default' }}
      >
        <Layer>
          <Group ref={groupRef} scaleX={fit.scale} scaleY={fit.scale} x={fit.offsetX} y={fit.offsetY}>
            {/* Fabric backdrop — light like real fabric, so dark threads stay visible */}
            <Rect
              x={bounds.minX - FABRIC_MARGIN_MM}
              y={bounds.minY - FABRIC_MARGIN_MM}
              width={bounds.maxX - bounds.minX + 2 * FABRIC_MARGIN_MM}
              height={bounds.maxY - bounds.minY + 2 * FABRIC_MARGIN_MM}
              fill="#e9e5da"
              cornerRadius={2 / pxPerMm}
              listening={false}
            />
            {/* Hoop outline when drawing on a blank canvas */}
            {!hasStitches && (
              <Rect
                x={bounds.minX}
                y={bounds.minY}
                width={bounds.maxX - bounds.minX}
                height={bounds.maxY - bounds.minY}
                stroke="#8a8474"
                strokeWidth={0.5 / pxPerMm}
                dash={[2 / pxPerMm, 2 / pxPerMm]}
                listening={false}
              />
            )}
            {runs.map((r, i) => {
              const active = selectedStop == null || r.stop === selectedStop;
              return (
                <Line
                  key={i}
                  points={r.points}
                  stroke={r.color}
                  strokeWidth={Math.max(
                    THREAD_WIDTH_MM * (r.stop === selectedStop ? 1.4 : 1),
                    (r.stop === selectedStop ? 2 : 1.2) / pxPerMm,
                  )}
                  opacity={active ? 1 : 0.12}
                  lineCap="round"
                  lineJoin="round"
                  hitStrokeWidth={6 / pxPerMm}
                  listening={!drawing}
                  onClick={() => !drawing && onSelectStop?.(r.stop)}
                  onTap={() => !drawing && onSelectStop?.(r.stop)}
                />
              );
            })}
            {/* Live draft path + vertices */}
            {draft.length > 0 && (
              <>
                <Line
                  points={draftPts}
                  stroke="#7c5cff"
                  strokeWidth={1.5 / pxPerMm}
                  closed={closed && draft.length >= 3}
                  fill={closed && draft.length >= 3 ? 'rgba(124,92,255,0.15)' : undefined}
                  lineCap="round"
                  lineJoin="round"
                  dash={[3 / pxPerMm, 2 / pxPerMm]}
                  listening={false}
                />
                {draft.map((p, i) => (
                  <Circle key={i} x={p.x} y={p.y} radius={2.4 / pxPerMm} fill="#7c5cff" listening={false} />
                ))}
              </>
            )}
          </Group>
        </Layer>
      </Stage>
      <div className="canvas-badge">
        {drawing
          ? `Drawing ${activeTool} — click to add points (${draft.length}), then Finish. Esc cancels.`
          : `${stitches.length.toLocaleString()} stitches · ${(bounds.maxX - bounds.minX).toFixed(0)}×${(bounds.maxY - bounds.minY).toFixed(0)} mm · click a color · scroll zoom · drag pan`}
      </div>
    </div>
  );
}

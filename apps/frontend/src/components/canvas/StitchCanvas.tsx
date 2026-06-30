import { Stage, Layer } from 'react-konva';
import type { Stitch } from '../../types/design';

interface StitchCanvasProps {
  stitches?: Stitch[];
  widthPx?: number;
  heightPx?: number;
}

/**
 * Canvas design editor (spec §3). Mounts a Konva stage to prove the renderer wiring.
 * TODO: draw stitches — group consecutive STITCH commands into Konva <Line> polylines
 * (mm → px via lib/units.mmToPx), color by ColorStop, skip JUMP/TRIM travel.
 */
export function StitchCanvas({ stitches = [], widthPx = 880, heightPx = 560 }: StitchCanvasProps) {
  return (
    <div className="canvas-wrap">
      <Stage width={widthPx} height={heightPx} className="stitch-stage">
        <Layer>{/* TODO: stitch geometry */}</Layer>
      </Stage>
      <div className="canvas-overlay">
        <p className="canvas-title">Stitch canvas</p>
        <p className="muted">
          {stitches.length} stitches loaded · Konva renderer stub — implement in{' '}
          <code>StitchCanvas.tsx</code>
        </p>
      </div>
    </div>
  );
}

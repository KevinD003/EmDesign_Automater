import { ConnectMethod, StitchType, UnderlayType } from '../types/design';
import type { Design, DesignObject, Point } from '../types/design';

/**
 * Manual-digitizing helpers (pure, unit-tested). A drawn path/region becomes a
 * DesignObject with a contour; the backend `/api/designs/rebuild` regenerates the
 * stitches for it (Run = running stitch along the path, Fill = tatami, Satin = column).
 */
export type ManualTool = 'run' | 'satin' | 'fill';

const SPEC: Record<ManualTool, { stitchType: StitchType; density: number; underlay: UnderlayType; label: string }> = {
  run: { stitchType: StitchType.RunningDouble, density: 0, underlay: UnderlayType.None, label: 'Run' },
  satin: { stitchType: StitchType.Satin, density: 3.5, underlay: UnderlayType.CenterWalk, label: 'Satin' },
  fill: { stitchType: StitchType.Tatami, density: 1.4, underlay: UnderlayType.EdgeWalk, label: 'Fill' },
};

export function minPointsFor(tool: ManualTool): number {
  return tool === 'run' ? 2 : 3;
}

/** True if a design came from an imported machine file (has stitches but no editable objects). */
export function isImportedNotEditable(design: Design | null): boolean {
  return !!design && design.objects.length === 0 && design.stitches.length > 0;
}

/**
 * Append a drawn object to a design (or start a fresh one). Returns a Design ready to
 * POST to /api/designs/rebuild. Adds a default color stop when the canvas is blank.
 */
export function buildManualDesign(
  design: Design | null,
  tool: ManualTool,
  points: Point[],
  selectedStop: number | null,
): Design {
  const base: Design =
    design ?? {
      name: 'Untitled',
      widthMm: 100,
      heightMm: 100,
      stitchCount: 0,
      version: 1,
      status: 'draft',
      colorStops: [],
      objects: [],
      stitches: [],
    };

  let stops = base.colorStops;
  let stopNumber: number;
  if (stops.length === 0) {
    stopNumber = 1;
    stops = [
      { stopNumber: 1, threadBrand: 'Manual', catalogNumber: '—', threadName: 'Color 1', hex: '#3a6ea5', stitchCount: 0 },
    ];
  } else {
    stopNumber = selectedStop ?? stops[stops.length - 1].stopNumber;
  }

  const seq = base.objects.reduce((m, o) => Math.max(m, o.sequenceOrder), 0) + 1;
  const spec = SPEC[tool];
  const obj: DesignObject = {
    sequenceOrder: seq,
    name: `${spec.label} ${seq}`,
    stitchType: spec.stitchType,
    colorStop: stopNumber,
    density: spec.density,
    stitchAngle: 0,
    underlayType: spec.underlay,
    pullCompensation: 0,
    connectMethod: ConnectMethod.Trim,
    stitchCount: 0,
    contour: points,
  };

  return { ...base, colorStops: stops, objects: [...base.objects, obj] };
}

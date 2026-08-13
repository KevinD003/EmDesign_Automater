/**
 * STITCHIQ shared data model (TypeScript side).
 *
 * MIRRORS apps/backend/app/models/design.py — keep both in sync.
 * Derived from spec §8 (DB schema), §4.3 (stitch types), §4.8 (formats), §4.9 (worksheet).
 * See docs/DATA-MODEL.md.
 */

/** Raw stitch command — subset of pyembroidery's command set that we render. */
export type StitchCommand =
  | 'STITCH'
  | 'JUMP'
  | 'TRIM'
  | 'COLOR_CHANGE'
  | 'STOP'
  | 'END';

/** A single machine instruction at a point (coordinates in millimetres). */
export interface Stitch {
  x: number;
  y: number;
  command: StitchCommand;
}

/**
 * Supported stitch types (spec §4.3).
 *
 * Every member has a generator behind it in the backend. v2 Part 43 removed the
 * thirteen that did not: eleven (cross-stitch, chenille, photo-stitch, motif,
 * and so on) fell through `rebuild_design`'s final `else` and silently returned
 * a byte-identical tatami fill, and `BACKSTITCH` / `REDWORK` were byte-identical
 * to running double / single. Mirrors `StitchType` in models/design.py — keep in
 * sync, and do not add a name here before the generator exists.
 */
export enum StitchType {
  Satin = 'SATIN',
  Tatami = 'TATAMI', // Fill
  ContourFill = 'CONTOUR_FILL', // rows follow the outline (v2 Part 24b)
  SpiralFill = 'SPIRAL_FILL', // curved fill: one continuous spiral (v2 Part 26)
  RadialFill = 'RADIAL_FILL', // curved fill: sunburst spokes (v2 Part 26)
  RunningSingle = 'RUNNING_SINGLE',
  RunningDouble = 'RUNNING_DOUBLE',
  RunningTriple = 'RUNNING_TRIPLE',
  Applique = 'APPLIQUE',
  Manual = 'MANUAL', // provenance, not a generator: a path the user placed by hand
}

/** Underlay strategies (spec §4.3). */
export enum UnderlayType {
  None = 'NONE',
  CenterWalk = 'CENTER_WALK',
  EdgeWalk = 'EDGE_WALK',
  DoubleZigzag = 'DOUBLE_ZIGZAG',
  Parallel = 'PARALLEL',
  Contour = 'CONTOUR',
}

/** How an object connects to the next in sequence. */
export enum ConnectMethod {
  Trim = 'TRIM',
  TravelRun = 'TRAVEL_RUN',
  Jump = 'JUMP',
}

export interface LabColor {
  l: number;
  a: number;
  b: number;
}

export interface Point {
  x: number;
  y: number;
}

/** A thread in a brand catalogue (spec §8 thread_database). */
export interface Thread {
  id?: string;
  brand: string;
  productLine: string;
  catalogNumber: string;
  colorName: string;
  hex: string;
  lab?: LabColor;
  weight?: number; // wt, e.g. 40
  fiberType?: string; // polyester, rayon, …
  discontinued?: boolean;
}

/** One color change in the stitching sequence (spec §8 color_stops, §4.9). */
export interface ColorStop {
  id?: string;
  stopNumber: number;
  threadBrand: string;
  catalogNumber: string;
  threadName: string;
  hex: string;
  /**
   * Needle penetrations sewn in this thread — what an operator means by
   * "stitches". Mirrors ColorStop.penetration_count.
   *
   * Until 2026-08-14 this was `stitchCount` and carried a STREAM SPAN: entries
   * in `Design.stitches`, jumps and trims included, measured before the tie-off
   * pass ran. Three fields shared the name across two spaces, and the worksheet
   * printed spans under a header of penetrations, so its rows did not sum to
   * its own total.
   */
  penetrationCount: number;
  /**
   * Stream entries attributed to this stop, tie-offs included. Diagnostic, and
   * optional here because nothing in the UI reads it — the backend always sends
   * it, and a caller constructing a ColorStop by hand should not have to
   * invent one.
   */
  streamSpan?: number;
}

/** A digitized object — one shape with its stitch settings (spec §8 design_objects). */
export interface DesignObject {
  id?: string;
  sequenceOrder: number;
  name: string;
  stitchType: StitchType;
  colorStop: number; // references ColorStop.stopNumber
  density: number; // stitches/mm or lines/cm
  stitchAngle: number; // degrees from horizontal
  underlayType: UnderlayType;
  pullCompensation: number; // mm per side
  entryPoint?: Point;
  exitPoint?: Point;
  connectMethod: ConnectMethod;
  /** Needle penetrations in this object. See the note on ColorStop. */
  penetrationCount: number;
  /** Stream entries in this object's span — jumps and trims included. Diagnostic. */
  streamSpan?: number;
  /**
   * Region outline in design mm space (populated by the digitizer). Presence of a
   * contour makes the object regenerable via POST /api/designs/rebuild.
   */
  contour?: Point[];
  /** Interior holes (e.g. letter counters like 'o'); carved out of the fill. */
  holes?: Point[][];
  /**
   * Stitch Flow (v2 Part 62): a user-drawn direction line [start, end] in design
   * mm. Rebuild lays this object's tatami rows along it; absent means the
   * automatic angle. Fill/tatami objects only.
   */
  flowLine?: Point[] | null;
  /**
   * Divided flow (v2 Part 63): an optional divide line that splits a tatami
   * object into two flow regions. Each side sews at the angle of the direction
   * line (flowLine / flowLineB) whose midpoint lies on it; an unclaimed side
   * uses the automatic angle. Without a divide, flowLineB is ignored.
   */
  flowDivide?: Point[] | null;
  flowLineB?: Point[] | null;
}

export type DesignStatus = 'draft' | 'digitized' | 'approved' | 'exported';

/** The full design (spec §8 designs). */
export interface Design {
  id?: string;
  name: string;
  widthMm: number;
  heightMm: number;
  hoopSize?: string; // e.g. "100x100"
  fabricType?: string;
  stitchCount: number;
  colorStops: ColorStop[];
  objects: DesignObject[];
  stitches: Stitch[]; // flat raw list for rendering
  version: number;
  status: DesignStatus;
  createdAt?: string; // ISO 8601
  /**
   * Things the digitizer did that would otherwise be silent (v2 Part 25):
   * artwork regions too small to sew at this hoop, a colour count that could
   * not be honoured, fine source detail the physical size cannot express.
   * Absent on designs saved before this field existed.
   */
  warnings?: string[];
  /**
   * Artwork the digitizer left unstitched because it matched the garment
   * colour, in mm² (DET3). The rule is right — you let the cloth show rather
   * than cover it in its own colour — but it deletes artwork on a colour
   * match, and its removal is subtracted from the coverage bases, so without
   * this number a design could lose a fifth of its foreground while every
   * quality metric still read as if it had sewn everything.
   */
  substrateRemovedMm2?: number;
  /** The garment colour the removal above was judged against, `#RRGGBB`. */
  substrateColorUsed?: string | null;
  /**
   * False means that colour was READ OFF THE IMAGE BORDER rather than
   * supplied — a guess about the customer's garment that decides which of
   * their artwork survives, and worth surfacing as correctable.
   */
  substrateColorDeclared?: boolean;
}

/** One row of the worksheet color sequence (spec §4.9). */
export interface WorksheetColorRow {
  stop: number;
  threadBrand: string;
  catalogNumber: string;
  colorName: string;
  hex: string;
  objects: string;
  stitchCount: number;
  /** Actual thread consumed by this color, mm (sum of stitch-segment lengths). */
  threadLengthMm: number;
}

/** Production worksheet — derived view of a Design (spec §4.9). */
export interface Worksheet {
  designName: string;
  designId?: string;
  version: number;
  widthMm: number;
  heightMm: number;
  hoopSize?: string;
  estimatedStitchCount: number;
  estimatedSewMinutes: number;
  fabricType?: string;
  stabilizer?: string;
  needle?: string;
  colorSequence: WorksheetColorRow[];
  totalTrims: number;
  totalColorChanges: number;
  qualityFlags: string[];
  placementGuide?: string;
}

/** Pre-export validation result (spec §4.8). */
export interface ValidationReport {
  passed: boolean;
  issues: string[];
  warnings: string[];
}

/** Format-conversion payloads (spec §4.8). */
export interface ConvertRequest {
  inputFileBase64: string;
  fromFormat: string;
  toFormat: string;
}

export interface ConvertResponse {
  outputFileBase64: string;
  stitchCount: number;
  colors: number;
  warnings: string[];
}

/** Phase 8 — optimization engine (mirrors models/design.py). */
export interface PathMetrics {
  stitchCount: number;
  colorChanges: number;
  trims: number;
  jumpCount: number;
  travelMm: number;
}

export interface OptimizeReport {
  reordered: boolean;
  before: PathMetrics;
  after: PathMetrics;
  colorChangesSaved: number;
  travelSavedMm: number;
  trimsSaved: number;
  note?: string | null;
}

export interface OptimizeResult {
  design: Design;
  report: OptimizeReport;
}

export interface QualityFinding {
  severity: 'info' | 'warn' | 'error';
  code: string;
  message: string;
  count: number;
}

export interface QualityReport {
  score: number;
  grade: string;
  metrics: PathMetrics;
  findings: QualityFinding[];
  /** Longest single stitch, mm. Optional: absent on reports from older backends. */
  maxStitchMm?: number;
  /** Mean stitch length, mm. */
  meanStitchMm?: number;
  /** Jump density — jumps per 1000 stitches. */
  jumpsPer1000?: number;
  /** true = fits the design's hoop, false = overflows, null = no hoop set. */
  hoopFit?: boolean | null;
}

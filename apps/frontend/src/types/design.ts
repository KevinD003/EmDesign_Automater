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

/** Supported stitch types (spec §4.3). */
export enum StitchType {
  Satin = 'SATIN',
  Tatami = 'TATAMI', // Fill
  RunningSingle = 'RUNNING_SINGLE',
  RunningDouble = 'RUNNING_DOUBLE',
  RunningTriple = 'RUNNING_TRIPLE',
  Backstitch = 'BACKSTITCH',
  Stemstitch = 'STEMSTITCH',
  CrossStitch = 'CROSS_STITCH',
  Zigzag = 'ZIGZAG',
  EStitch = 'E_STITCH',
  MotifFill = 'MOTIF_FILL',
  MotifRun = 'MOTIF_RUN',
  ContourFill = 'CONTOUR_FILL',
  AccordionFill = 'ACCORDION_FILL',
  Laydown = 'LAYDOWN',
  Manual = 'MANUAL',
  PhotoStitch = 'PHOTO_STITCH',
  GradientBlend = 'GRADIENT_BLEND',
  Applique = 'APPLIQUE',
  Chenille = 'CHENILLE',
  Redwork = 'REDWORK',
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
  stitchCount: number;
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
  stitchCount: number;
  /**
   * Region outline in design mm space (populated by the digitizer). Presence of a
   * contour makes the object regenerable via POST /api/designs/rebuild.
   */
  contour?: Point[];
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

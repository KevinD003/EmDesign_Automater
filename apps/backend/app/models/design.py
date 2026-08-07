"""STITCHIQ shared data model (Python / Pydantic v2 side).

MIRRORS apps/frontend/src/types/design.ts — keep both in sync.
Derived from spec §8 (DB schema), §4.3 (stitch types), §4.8 (formats), §4.9 (worksheet).

The camelCase alias generator makes JSON match the TypeScript interfaces exactly
(e.g. Python ``width_mm`` <-> JSON ``widthMm``). See docs/DATA-MODEL.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )


def enum_str(v) -> str:
    """Canonical string of an enum-or-string field (v2 Part 66).

    `use_enum_values=True` above means every enum field on a validated model
    is ALREADY a plain string — but code that also receives raw enum members
    (hand-built objects, pyembroidery constants) grew eight copies of the
    `v.value if hasattr(v, "value") else v` dance across services, scripts
    and the pipeline. This is the one implementation; the per-service
    normalisers delegate to it.
    """
    return v.value if isinstance(v, Enum) else str(v)


class StitchCommand(str, Enum):
    STITCH = "STITCH"
    JUMP = "JUMP"
    TRIM = "TRIM"
    COLOR_CHANGE = "COLOR_CHANGE"
    STOP = "STOP"
    END = "END"


class StitchType(str, Enum):
    """Every member here has a generator behind it. That is the whole rule.

    v2 Part 43 removed thirteen members that did not. The enum used to declare 23
    and the engine produced **nine distinct streams**: selecting `CROSS_STITCH`,
    `CHENILLE`, `PHOTO_STITCH` or eight others fell through `rebuild_design`'s
    final `else` and returned a byte-identical tatami fill, with nothing to tell
    you. `BACKSTITCH` was byte-identical to `RUNNING_DOUBLE` and `REDWORK` to
    `RUNNING_SINGLE`. An API that advertises a capability and quietly substitutes
    another is worse than one that never offered it.

    They are listed in `LEGACY_STITCH_TYPES` below so designs saved while they
    existed still load, mapped to what they actually produced at the time.
    Re-adding any of them is a one-line change *once its generator exists*.
    """

    SATIN = "SATIN"
    TATAMI = "TATAMI"  # Fill
    RUNNING_SINGLE = "RUNNING_SINGLE"
    RUNNING_DOUBLE = "RUNNING_DOUBLE"
    RUNNING_TRIPLE = "RUNNING_TRIPLE"
    CONTOUR_FILL = "CONTOUR_FILL"
    # Curved fills (v2 Part 26): rows spiral out from / radiate through the
    # region instead of running straight. User-selectable via rebuild — the
    # "curved fill effects" the desktop suites sell as a premium feature.
    SPIRAL_FILL = "SPIRAL_FILL"
    RADIAL_FILL = "RADIAL_FILL"
    APPLIQUE = "APPLIQUE"
    # Not a generator — provenance. It marks a path the user placed by hand, and
    # rebuild deliberately runs along it rather than re-deriving a fill, so the
    # edit survives. It produces the same stream as RUNNING_SINGLE by design.
    MANUAL = "MANUAL"


# Removed in Part 43, mapped to the stream each one actually produced, so a
# design saved before then keeps loading and rebuilding identically.
LEGACY_STITCH_TYPES: dict[str, StitchType] = {
    "BACKSTITCH": StitchType.RUNNING_DOUBLE,   # was `passes=2`, i.e. a double run
    "REDWORK": StitchType.RUNNING_SINGLE,      # was `passes=1`
    # All eleven of these hit the `else` branch and came out as tatami.
    "STEMSTITCH": StitchType.TATAMI,
    "CROSS_STITCH": StitchType.TATAMI,
    "ZIGZAG": StitchType.TATAMI,
    "E_STITCH": StitchType.TATAMI,
    "MOTIF_FILL": StitchType.TATAMI,
    "MOTIF_RUN": StitchType.TATAMI,
    "ACCORDION_FILL": StitchType.TATAMI,
    "LAYDOWN": StitchType.TATAMI,
    "PHOTO_STITCH": StitchType.TATAMI,
    "GRADIENT_BLEND": StitchType.TATAMI,
    "CHENILLE": StitchType.TATAMI,
}


class UnderlayType(str, Enum):
    NONE = "NONE"
    CENTER_WALK = "CENTER_WALK"
    EDGE_WALK = "EDGE_WALK"
    DOUBLE_ZIGZAG = "DOUBLE_ZIGZAG"
    PARALLEL = "PARALLEL"
    CONTOUR = "CONTOUR"


class ConnectMethod(str, Enum):
    TRIM = "TRIM"
    TRAVEL_RUN = "TRAVEL_RUN"
    JUMP = "JUMP"


class LabColor(CamelModel):
    l: float
    a: float
    b: float


class Point(CamelModel):
    x: float
    y: float


class Stitch(CamelModel):
    x: float
    y: float
    command: StitchCommand = StitchCommand.STITCH


class Thread(CamelModel):
    id: str | None = None
    brand: str
    product_line: str = ""
    catalog_number: str
    color_name: str
    hex: str
    lab: LabColor | None = None
    weight: float | None = None
    fiber_type: str | None = None
    discontinued: bool = False


class ColorStop(CamelModel):
    id: str | None = None
    stop_number: int
    thread_brand: str
    catalog_number: str
    thread_name: str
    hex: str
    stitch_count: int = 0


class DesignObject(CamelModel):
    id: str | None = None
    sequence_order: int
    name: str
    stitch_type: StitchType
    color_stop: int  # references ColorStop.stop_number
    density: float = 0.0
    stitch_angle: float = 0.0
    underlay_type: UnderlayType = UnderlayType.NONE
    pull_compensation: float = 0.0
    entry_point: Point | None = None
    exit_point: Point | None = None
    connect_method: ConnectMethod = ConnectMethod.TRIM
    stitch_count: int = 0
    # Region outline in design mm space (populated by the digitizer). Presence of a
    # contour makes the object REGENERABLE: /api/designs/rebuild can re-fill it with
    # new density/angle. Imported stitch files have no contours (objects empty anyway).
    contour: list[Point] | None = None
    # Interior holes (e.g. letter counters like 'o'); carved out of the fill.
    holes: list[list[Point]] | None = None
    # Stitch Flow (v2 Part 62): a user-drawn direction line for FILL objects, in
    # design mm, [start, end]. When present, rebuild lays this object's tatami
    # rows along the line instead of the automatic principal axis; when absent
    # (every design saved before Part 62 — the field defaults to None), rebuild
    # is untouched. Removing the line returns the object to its automatic angle,
    # which is why the override never overwrites `stitch_angle`.
    flow_line: list[Point] | None = None
    # Divided flow (v2 Part 63): an optional divide line, in design mm, that
    # splits a TATAMI object into two flow regions. Each side sews at the angle
    # of the direction line whose MIDPOINT lies on that side (`flow_line` and
    # `flow_line_b` are both candidates; first claim wins), falling back to the
    # automatic angle for a side no line claims. Without a divide, `flow_line_b`
    # is ignored and behaviour is exactly Part 62's. Both default to None, so
    # every earlier design loads and rebuilds untouched.
    flow_divide: list[Point] | None = None
    flow_line_b: list[Point] | None = None

    @field_validator("stitch_type", mode="before")
    @classmethod
    def _migrate_removed_stitch_types(cls, v):
        """Accept a design saved while the phantom types still existed (Part 43).

        Rejecting them would 422 a design that used to load, so they map to the
        stream each one really produced. This is a data migration, not an offer:
        the values are gone from the enum, so nothing new can be created with one.
        """
        if isinstance(v, str) and v in LEGACY_STITCH_TYPES:
            return LEGACY_STITCH_TYPES[v]
        return v


class Design(CamelModel):
    id: str | None = None
    name: str
    width_mm: float = 0.0
    height_mm: float = 0.0
    hoop_size: str | None = None
    fabric_type: str | None = None
    stitch_count: int = 0
    color_stops: list[ColorStop] = Field(default_factory=list)
    objects: list[DesignObject] = Field(default_factory=list)
    stitches: list[Stitch] = Field(default_factory=list)
    version: int = 1
    status: str = "draft"
    created_at: str | None = None
    # Things the digitizer did that the user would otherwise never learn about
    # (v2 Part 25): regions dropped as unsewably small at this hoop size, a
    # colour count that could not be honoured, and similar. Silent loss was a
    # measured defect — a 40x40mm hoop took the badge fixture from 21 objects
    # to 4 with nothing said. Empty list == nothing to report.
    warnings: list[str] = Field(default_factory=list)


class WorksheetColorRow(CamelModel):
    stop: int
    thread_brand: str
    catalog_number: str
    color_name: str
    hex: str
    objects: str
    stitch_count: int
    thread_length_mm: float = 0.0  # actual thread consumed by this color (sum of stitch lengths)


class Worksheet(CamelModel):
    design_name: str
    design_id: str | None = None
    version: int = 1
    width_mm: float = 0.0
    height_mm: float = 0.0
    hoop_size: str | None = None
    estimated_stitch_count: int = 0
    estimated_sew_minutes: float = 0.0
    fabric_type: str | None = None
    stabilizer: str | None = None
    needle: str | None = None
    color_sequence: list[WorksheetColorRow] = Field(default_factory=list)
    total_trims: int = 0
    total_color_changes: int = 0
    quality_flags: list[str] = Field(default_factory=list)
    placement_guide: str | None = None


class ValidationReport(CamelModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ConvertRequest(CamelModel):
    input_file_base64: str
    from_format: str
    to_format: str


class ConvertResponse(CamelModel):
    output_file_base64: str
    stitch_count: int
    colors: int
    warnings: list[str] = Field(default_factory=list)


# ── Phase 8: optimization engine (classical baseline; neural methods are future) ──


class PathMetrics(CamelModel):
    stitch_count: int = 0
    color_changes: int = 0
    trims: int = 0
    jump_count: int = 0
    travel_mm: float = 0.0  # total jump/travel distance between stitches


class OptimizeReport(CamelModel):
    reordered: bool = False
    before: PathMetrics
    after: PathMetrics
    color_changes_saved: int = 0
    travel_saved_mm: float = 0.0
    trims_saved: int = 0
    note: str | None = None


class OptimizeResult(CamelModel):
    design: Design
    report: OptimizeReport


class QualityFinding(CamelModel):
    severity: str  # 'info' | 'warn' | 'error'
    code: str
    message: str
    count: int = 0


class QualityReport(CamelModel):
    score: int = 100  # 0..100
    grade: str = "A"  # A/B/C/D/F
    metrics: PathMetrics
    findings: list[QualityFinding] = Field(default_factory=list)
    # Consolidated stream stats (defaulted so pre-existing payloads stay valid).
    max_stitch_mm: float = 0.0   # longest STITCH-to-STITCH step
    mean_stitch_mm: float = 0.0  # average STITCH-to-STITCH step
    jumps_per_1000: float = 0.0  # jump rate per 1,000 stream entries (target ≤5)
    hoop_fit: bool | None = None  # None = no/unparseable hoop on the design

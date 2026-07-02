"""STITCHIQ shared data model (Python / Pydantic v2 side).

MIRRORS apps/frontend/src/types/design.ts — keep both in sync.
Derived from spec §8 (DB schema), §4.3 (stitch types), §4.8 (formats), §4.9 (worksheet).

The camelCase alias generator makes JSON match the TypeScript interfaces exactly
(e.g. Python ``width_mm`` <-> JSON ``widthMm``). See docs/DATA-MODEL.md.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
    )


class StitchCommand(str, Enum):
    STITCH = "STITCH"
    JUMP = "JUMP"
    TRIM = "TRIM"
    COLOR_CHANGE = "COLOR_CHANGE"
    STOP = "STOP"
    END = "END"


class StitchType(str, Enum):
    SATIN = "SATIN"
    TATAMI = "TATAMI"  # Fill
    RUNNING_SINGLE = "RUNNING_SINGLE"
    RUNNING_DOUBLE = "RUNNING_DOUBLE"
    RUNNING_TRIPLE = "RUNNING_TRIPLE"
    BACKSTITCH = "BACKSTITCH"
    STEMSTITCH = "STEMSTITCH"
    CROSS_STITCH = "CROSS_STITCH"
    ZIGZAG = "ZIGZAG"
    E_STITCH = "E_STITCH"
    MOTIF_FILL = "MOTIF_FILL"
    MOTIF_RUN = "MOTIF_RUN"
    CONTOUR_FILL = "CONTOUR_FILL"
    ACCORDION_FILL = "ACCORDION_FILL"
    LAYDOWN = "LAYDOWN"
    MANUAL = "MANUAL"
    PHOTO_STITCH = "PHOTO_STITCH"
    GRADIENT_BLEND = "GRADIENT_BLEND"
    APPLIQUE = "APPLIQUE"
    CHENILLE = "CHENILLE"
    REDWORK = "REDWORK"


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


class WorksheetColorRow(CamelModel):
    stop: int
    thread_brand: str
    catalog_number: str
    color_name: str
    hex: str
    objects: str
    stitch_count: int


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

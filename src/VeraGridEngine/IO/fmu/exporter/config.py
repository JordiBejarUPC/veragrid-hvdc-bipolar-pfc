from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import platform
import re
import uuid


class InterfaceType(str, Enum):
    CO_SIMULATION = "co-simulation"


class IntegrationMethod(str, Enum):
    BACKWARD_EULER = "backward_euler"
    TRAPEZOIDAL = "trapezoidal"
    BDF2 = "bdf2"


class TargetPlatform(str, Enum):
    WIN64 = "win64"
    LINUX64 = "linux64"
    DARWIN64 = "darwin64"


def detect_target_platform() -> TargetPlatform:
    system = platform.system().lower()
    if system == "windows":
        return TargetPlatform.WIN64
    if system == "darwin":
        return TargetPlatform.DARWIN64
    return TargetPlatform.LINUX64


def library_suffix(target_platform: TargetPlatform) -> str:
    if target_platform == TargetPlatform.WIN64:
        return ".dll"
    if target_platform == TargetPlatform.DARWIN64:
        return ".dylib"
    return ".so"


def sanitize_identifier(name: str) -> str:
    text = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not text:
        text = "GeneratedModel"
    if text[0].isdigit():
        text = f"M_{text}"
    return text


@dataclass(slots=True)
class ExportConfig:
    model_name: str
    output_path: Path
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))
    interface_type: InterfaceType = InterfaceType.CO_SIMULATION
    target_platform: TargetPlatform = field(default_factory=detect_target_platform)
    integration_method: IntegrationMethod = IntegrationMethod.BACKWARD_EULER
    fixed_step: float = 1e-4
    build_dir: Path | None = None
    staging_dir: Path | None = None
    model_identifier: str | None = None
    debug: bool = False
    keep_build_dir: bool = False
    include_snapshot_resource: bool = True
    include_export_model_resource: bool = True
    compile_binary: bool = True
    max_newton_iterations: int = 10
    newton_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        self.output_path = Path(self.output_path)
        self.build_dir = None if self.build_dir is None else Path(self.build_dir)
        self.staging_dir = None if self.staging_dir is None else Path(self.staging_dir)
        if self.fixed_step <= 0.0:
            raise ValueError("fixed_step must be positive")
        if self.max_newton_iterations <= 0:
            raise ValueError("max_newton_iterations must be positive")
        if self.newton_tolerance <= 0.0:
            raise ValueError("newton_tolerance must be positive")
        self.model_identifier = sanitize_identifier(self.model_identifier or self.model_name)

    @property
    def output_dir(self) -> Path:
        return self.output_path.parent

    @property
    def library_name(self) -> str:
        return f"{self.model_identifier}{library_suffix(self.target_platform)}"

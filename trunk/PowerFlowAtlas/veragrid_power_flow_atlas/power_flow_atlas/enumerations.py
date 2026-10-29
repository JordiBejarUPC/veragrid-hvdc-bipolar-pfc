from enum import Enum


class AtlasBuildStatus(Enum):
    """Status returned while constructing an atlas or a patch."""

    Ready = "Ready"
    InvalidInput = "Invalid input"
    UnsupportedTopology = "Unsupported topology"
    UnsupportedInjectionModel = "Unsupported injection model"
    UnsupportedControlRegime = "Unsupported control regime"
    AnchorNotConverged = "Anchor not converged"
    SingularJacobian = "Singular Jacobian"
    InternalFailure = "Internal failure"


class AtlasQueryStatus(Enum):
    """Status returned after evaluating an atlas query."""

    CertifiedSeries = "Certified series"
    CertifiedNewton = "Certified Newton correction"
    FullPowerFlowFallback = "Full power-flow fallback"
    OutsideAtlas = "Outside atlas"
    RegimeMismatch = "Control-regime mismatch"
    InvalidInput = "Invalid input"
    Failed = "Failed"


class SeriesEvaluationMethod(Enum):
    """Method used to evaluate a directional voltage series at the target."""

    Polynomial = "Polynomial"
    Pade = "Pade"


class AtlasFallbackMode(Enum):
    """Fallback policy applied after a non-certified series evaluation."""

    NoneMode = "None"
    NewtonCorrection = "Newton correction"
    FullPowerFlow = "Full power flow"


class AtlasStorageStatus(Enum):
    """Status returned while saving or loading an atlas artifact."""

    Saved = "Saved"
    Loaded = "Loaded"
    InvalidPath = "Invalid path"
    InvalidFormat = "Invalid format"
    InputOutputFailure = "Input/output failure"
    FactorizationFailure = "Factorization failure"

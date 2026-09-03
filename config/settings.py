"""
Settings models for ECPypsi using Pydantic v2.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

from pydantic import BaseSettings

class AppSettings(BaseSettings):
    """
    Application settings for ECPypsi.

    Attributes
    ----------
    default_data_folder : str
        Default data folder path.
    color_scheme : str
        Color scheme ('light' or 'dark').
    last_used_folder : str
        Last used data folder.
    """
    default_data_folder: str = "./data/raw"
    color_scheme: str = "light"
    last_used_folder: str = "./data/raw"

    class Config:
        env_file = ".env"

"""
Now the old one
"""



class GeneralSettings(BaseModel):
    color_scheme: str = Field(default="light", description="UI color scheme")
    last_open_folder: Optional[str] = Field(default=None, description="Last used data folder")
    export_folder: Optional[str] = Field(default=None, description="Default export folder")

class TruncationSettings(BaseModel):
    lower_bound: float = Field(default=150.0, description="Lower wavenumber bound")
    upper_bound: float = Field(default=3400.0, description="Upper wavenumber bound")

class SpikeRemovalSettings(BaseModel):
    method: str = Field(default="modified_zscore", description="Spike removal method")
    threshold: float = Field(default=6.0, description="Z-score threshold")

class CalibrationSettings(BaseModel):
    offset: float = Field(default=0.0, description="Calibration offset")
    scale: float = Field(default=1.0, description="Calibration scale factor")

class SmoothingSettings(BaseModel):
    method: str = Field(default="savitzky_golay", description="Smoothing method")
    window_length: int = Field(default=11, description="Smoothing window length")
    polyorder: int = Field(default=3, description="Polynomial order for Savitzky-Golay")

class BaselineSettings(BaseModel):
    method: str = Field(default="als", description="Baseline correction method")
    poly_order: int = Field(default=3, description="Polynomial order for polynomial baseline")
    als_lambda: float = Field(default=1e5, description="ALS lambda parameter")
    als_p: float = Field(default=0.01, description="ALS p parameter")

class NormalizationSettings(BaseModel):
    method: str = Field(default="minmax", description="Normalization method")
    region: Optional[List[float]] = Field(default=None, description="Region for peak normalization")

class PeakFittingSettings(BaseModel):
    method: str = Field(default="voigt", description="Peak fitting method")
    max_peaks: int = Field(default=5, description="Maximum number of peaks")
    fit_region: Optional[List[float]] = Field(default=None, description="Region for fitting")

class ComponentAnalysisSettings(BaseModel):
    method: str = Field(default="pca", description="Component analysis method")
    n_components: int = Field(default=2, description="Number of components")

class ECPypsiSettings(BaseModel):
    general: GeneralSettings = GeneralSettings()
    truncation: TruncationSettings = TruncationSettings()
    spike_removal: SpikeRemovalSettings = SpikeRemovalSettings()
    calibration: CalibrationSettings = CalibrationSettings()
    smoothing: SmoothingSettings = SmoothingSettings()
    baseline: BaselineSettings = BaselineSettings()
    normalization: NormalizationSettings = NormalizationSettings()
    peak_fitting: PeakFittingSettings = PeakFittingSettings()
    component_analysis: ComponentAnalysisSettings = ComponentAnalysisSettings()

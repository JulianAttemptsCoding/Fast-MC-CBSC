"""CBSC-ZDC v2.2: auditable neutron ZDC FastMC implementation."""

from .contracts import DetectorSpec, NEUTRON_MASS_GEV
from .models.system import CBSCOutput, CBSCZDC

__all__ = ["CBSCZDC", "CBSCOutput", "DetectorSpec", "NEUTRON_MASS_GEV"]
__version__ = "0.3.0"

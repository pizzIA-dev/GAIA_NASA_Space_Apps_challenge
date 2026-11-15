"""SDK Python oficial de Earth Trend Studio (nombre provisional)."""

from earth_trend_client.client import EarthTrendAPIError, EarthTrendClient
from earth_trend_client.models import ConfidenceInterval, HypothesisTest, Run, Statistics

__all__ = ["ConfidenceInterval", "EarthTrendAPIError", "EarthTrendClient", "HypothesisTest", "Run", "Statistics"]
__version__ = "0.1.0"

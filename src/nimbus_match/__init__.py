"""
Nimbus Match package: Times New Roman metric-compatible font generator.
"""

from nimbus_match.builder import build_single_style
from nimbus_match.comparison import generate_comparison_image
from nimbus_match.orchestrator import main as check_and_build

__all__ = [
    "build_single_style",
    "generate_comparison_image",
    "check_and_build",
]

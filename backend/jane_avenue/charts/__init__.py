"""Server-rendered charts (matplotlib). Every element is computed from real model output."""
from .montecarlo import (
    DEFAULT_PATHS,
    MAX_PATHS,
    build_monte_carlo_figure,
    path_indices,
    render_monte_carlo,
    summarise,
)

__all__ = ["DEFAULT_PATHS", "MAX_PATHS", "build_monte_carlo_figure", "path_indices", "render_monte_carlo", "summarise"]

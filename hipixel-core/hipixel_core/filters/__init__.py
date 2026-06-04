"""hipixel_core.filters package."""

from hipixel_core.filters.aces import ACESToneMappingFilter
from hipixel_core.filters.anime4k import Anime4KFilter
from hipixel_core.filters.base import Filter
from hipixel_core.filters.cas import CASFilter
from hipixel_core.filters.nafnet import NAFNetFilter
from hipixel_core.filters.real_esrgan import RealESRGANFilter
from hipixel_core.filters.rife import RIFEFilter

#: Registry of all built-in filters by name.
FILTER_REGISTRY: dict[str, type[object]] = {
    "real_esrgan": RealESRGANFilter,
    "anime4k": Anime4KFilter,
    "nafnet": NAFNetFilter,
    "cas": CASFilter,
    "aces": ACESToneMappingFilter,
    "rife": RIFEFilter,
}


def get_filter(name: str) -> object:
    """Instantiate a filter by its registry name.

    Args:
        name:  Filter name as used in preset JSON (e.g. ``"real_esrgan"``).

    Returns:
        A new filter instance (not yet set up).

    Raises:
        ``KeyError`` if the name is not in the registry.
    """
    cls = FILTER_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(FILTER_REGISTRY)
        raise KeyError(f"Unknown filter '{name}'. Available filters: {available}")
    return cls()


__all__ = [
    "FILTER_REGISTRY",
    "ACESToneMappingFilter",
    "Anime4KFilter",
    "CASFilter",
    "Filter",
    "NAFNetFilter",
    "RIFEFilter",
    "RealESRGANFilter",
    "get_filter",
]

"""Valfria Jupyter-vyer. Beräkningsmodulerna importerar aldrig detta paket."""

__all__ = ["Grundplan"]


def __getattr__(name):
    if name == "Grundplan":
        from .grundplan import Grundplan

        return Grundplan
    raise AttributeError(name)

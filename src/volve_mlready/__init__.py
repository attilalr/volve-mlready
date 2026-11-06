"""Volve ML-ready: load the co-registered seismic cubes and well-tied porosity dataset."""
from .loader import CUBES, TABLES, VolveMLReady
from .download import download, verify

__version__ = '1.0.0'
__all__ = ['VolveMLReady', 'CUBES', 'TABLES', 'download', 'verify']

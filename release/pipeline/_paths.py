"""Shared paths for the pipeline.

All scripts read and write under DATA, the working tree of the Volve subset
(default: <repo>/release/data/volve). Override with the VOLVE_DATA environment variable.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('VOLVE_DATA', REPO / 'data' / 'volve')).resolve()
PREP = DATA / 'prepared'

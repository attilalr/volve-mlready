"""Plot style shared by the example notebooks (matplotlib only).

Colour by job: seismic amplitude is diverging (blue <-> red, neutral grey at zero),
magnitudes (Vp, porosity) are sequential single-hue blue. Wells are drawn in ink and
direct-labelled rather than given 11 categorical colours.
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SURFACE = '#fcfcfb'
INK, INK2, INK3 = '#0b0b0b', '#52514e', '#8c8b86'
GRID = '#e6e5e1'
BLUE = '#2a78d6'                       # single series / sequential accent
BLUE_RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#2a78d6',
             '#1c5cab', '#184f95', '#104281', '#0d366b']

# diverging: equal arms, grey midpoint (zero amplitude reads as "nothing")
SEISMIC = LinearSegmentedColormap.from_list(
    'seismic_div', ['#0d366b', '#2a78d6', '#9ec5f4', '#f0efec', '#f4a3a2', '#e34948', '#8c1d1d'])
SEQUENTIAL = LinearSegmentedColormap.from_list('blue_seq', BLUE_RAMP)


def apply():
    mpl.rcParams.update({
        'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'figure.dpi': 110, 'savefig.dpi': 150, 'savefig.bbox': 'tight',
        'font.size': 9, 'axes.titlesize': 10, 'axes.titleweight': 'bold',
        'axes.titlelocation': 'left', 'axes.labelsize': 9,
        'text.color': INK, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
        'xtick.color': INK3, 'ytick.color': INK3, 'xtick.labelcolor': INK2, 'ytick.labelcolor': INK2,
        'axes.edgecolor': GRID, 'axes.linewidth': 0.8,
        'axes.grid': False, 'grid.color': GRID, 'grid.linewidth': 0.6,
        'axes.spines.top': False, 'axes.spines.right': False,
        'legend.frameon': False, 'lines.linewidth': 2,
        'image.cmap': 'blue_seq',
    })
    if 'seismic_div' not in plt.colormaps():
        plt.colormaps.register(SEISMIC)
        plt.colormaps.register(SEQUENTIAL)


def sym_limits(a, pct=98):
    """Symmetric colour limits for amplitude, clipped at a percentile of |a|."""
    import numpy as np
    v = float(np.nanpercentile(np.abs(a), pct))
    return -v, v

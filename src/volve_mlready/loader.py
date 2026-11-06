"""Loader for the Volve ML-ready seismic-well dataset (numpy + pandas only).

    from volve_mlready import VolveMLReady
    v = VolveMLReady('/path/to/volve-mlready-v1.0.0')
    amp = v.cube('ps_amplitude')            # (901, 385, 605) float32, memory-mapped
    vox = v.wells('voxels')                 # one row per (well, voxel), target PHIE
    x = amp[vox.IZ, vox.IY, vox.IX]          # amplitude at each well voxel

Index convention for every array on the ST0202 depth grid:  C[iz, iy, ix]
    iz -> depth below MSL  z = z0 + dz*iz          (z0 = 0 m, dz = 5 m)
    iy -> inline index      il = il0 + iy          (il0 = 9985)
    ix -> crossline index   xl = xl0 + ix          (xl0 = 1932)
    (il, xl) -> (X, Y) in ED50 / UTM zone 31N (EPSG:23031) via the affine in the grid JSON.
"""
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

CUBES = {
    'ps_amplitude': 'st0202_ps_amplitude_depth.npy',
    'vp': 'vp_on_st0202_depth.npy',
    'pp_amplitude': 'pp_amplitude_on_st0202_depth.npy',
    'vp_native': 'vp_st10010_native_depth.npy',
    'pp_time_native': 'pp_poststack_st0202_time.npy',
}
TABLES = {'voxels': 'wells_voxels.csv', 'samples': 'wells_samples.csv', 'index': 'wells_index.csv'}


class VolveMLReady:
    def __init__(self, root):
        self.root = Path(root)
        self.grid = json.load(open(self.root / 'grid_st0202_depth.json'))
        g = self.grid
        X, Y = g['affine_ilxl_to_XY']['X'], g['affine_ilxl_to_XY']['Y']
        self._M = np.array([[X[0], X[1]], [Y[0], Y[1]]])
        self._off = np.array([X[2], Y[2]])
        self._Minv = np.linalg.inv(self._M)
        self.shape = tuple(g['shape_zyx'])

    # ---------------- arrays ----------------
    def cube(self, name='ps_amplitude', mmap=True):
        """Load a cube by short name (see CUBES). Memory-mapped by default."""
        return np.load(self.root / CUBES[name], mmap_mode='r' if mmap else None)

    def native_geometry(self, name):
        """Geometry JSON of a native-grid array ('vp_native' or 'pp_time_native')."""
        return json.load(open(self.root / CUBES[name].replace('.npy', '.json')))

    # ---------------- wells ----------------
    def wells(self, table='voxels'):
        """'voxels' (training table), 'samples' (raw log samples) or 'index' (one row per well)."""
        with zipfile.ZipFile(self.root / 'wells.zip') as z, z.open(TABLES[table]) as f:
            return pd.read_csv(f)

    def trajectory(self, npd):
        """Deviation survey of one well: MD, INC, AZI, TVD_DF, TVDSS, X, Y."""
        with zipfile.ZipFile(self.root / 'wells.zip') as z, z.open(f'trajectories/{npd}.csv') as f:
            return pd.read_csv(f)

    # ---------------- coordinates ----------------
    def ilxl_to_xy(self, il, xl):
        il, xl = np.asarray(il, float), np.asarray(xl, float)
        X = self._M[0, 0] * il + self._M[0, 1] * xl + self._off[0]
        Y = self._M[1, 0] * il + self._M[1, 1] * xl + self._off[1]
        return X, Y

    def xy_to_ilxl(self, X, Y):
        rhs = np.vstack([np.ravel(X) - self._off[0], np.ravel(Y) - self._off[1]])
        il, xl = self._Minv @ rhs
        return il.reshape(np.shape(X)), xl.reshape(np.shape(X))

    def index_to_world(self, iz, iy, ix):
        """Grid indices -> (X, Y, z_TVDSS) at the cell centre."""
        g = self.grid
        X, Y = self.ilxl_to_xy(g['il0'] + np.asarray(iy) * g['il_step'],
                               g['xl0'] + np.asarray(ix) * g['xl_step'])
        return X, Y, g['z0'] + np.asarray(iz) * g['dz']

    def world_to_index(self, X, Y, z):
        """(X, Y, z_TVDSS) -> nearest grid indices (iz, iy, ix); may fall outside the cube."""
        g = self.grid
        il, xl = self.xy_to_ilxl(X, Y)
        iy = np.rint((il - g['il0']) / g['il_step']).astype(int)
        ix = np.rint((xl - g['xl0']) / g['xl_step']).astype(int)
        iz = np.rint((np.asarray(z) - g['z0']) / g['dz']).astype(int)
        return iz, iy, ix

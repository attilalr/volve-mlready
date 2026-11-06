#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ST0202 PS PSDM full-offset post-stack (DEPTH) SEG-Y -> numpy cube + grid geometry.

Outputs:
  prepared/cubo_st0202_depth.npy   float32 (nz, n_il, n_xl) = (901, 385, 605)
  prepared/cubo_st0202_geom.json   inlines, crosslines, depths (m) and the affine
                                   (il, xl) -> (X, Y), ED50 / UTM zone 31N

Index convention: C[iz, iy, ix]; depth = z0 + dz*iz, il = il0 + iy, xl = xl0 + ix.
The affine is a least-squares fit to the trace-header bin-centre coordinates
(CDP_X/CDP_Y with the coordinate scalar) of 4000 traces; RMS residual ~0.05 m.
Usage: python pipeline/preparar_cubo_volve.py
"""
import os, json
import numpy as np
import segyio
from pathlib import Path

from _paths import DATA, PREP
SEGY = DATA / 'seismic' / 'st0202' / 'stacks' / 'ST0202R08_PSDM_FULL_OFFSET_DEPTH_POSTSTACK.segy'
OUT_NPY = DATA / 'prepared' / 'cubo_st0202_depth.npy'
OUT_GEOM = DATA / 'prepared' / 'cubo_st0202_geom.json'


def main():
    OUT_NPY.parent.mkdir(parents=True, exist_ok=True)
    with segyio.open(str(SEGY), iline=189, xline=193) as f:
        ilines = np.asarray(f.ilines, dtype=int)
        xlines = np.asarray(f.xlines, dtype=int)
        depths = np.asarray(f.samples, dtype=float)          # metros (Z = profundidade)
        n_il, n_xl, nz = len(ilines), len(xlines), len(depths)
        print(f'ilines {ilines.min()}-{ilines.max()} n={n_il} | '
              f'xlines {xlines.min()}-{xlines.max()} n={n_xl} | '
              f'depth {depths.min()}-{depths.max()} n={nz} dz={depths[1]-depths[0]}')

        # cubo (il, xl, z) -> transpoe para (z, il, xl)
        cube = segyio.tools.cube(f)                            # (n_il, n_xl, nz) float32
        cube = np.ascontiguousarray(np.transpose(cube, (2, 0, 1)).astype(np.float32))
        print('cube shape (nz,n_il,n_xl) =', cube.shape, 'dtype', cube.dtype,
              'nan?', bool(np.isnan(cube).any()))

        # ---- afim (il,xl) -> (X,Y) a partir dos headers de traco ----
        scal = f.header[0][segyio.TraceField.SourceGroupScalar]
        s = float(scal)
        s = (1.0/abs(s)) if s < 0 else (abs(s) if s != 0 else 1.0)
        il_h = np.empty(f.tracecount); xl_h = np.empty(f.tracecount)
        X = np.empty(f.tracecount); Y = np.empty(f.tracecount)
        # amostra esparsa de tracos para ajustar a afim (rapido e suficiente)
        idx = np.linspace(0, f.tracecount - 1, num=min(4000, f.tracecount)).astype(int)
        il_s = np.empty(len(idx)); xl_s = np.empty(len(idx))
        Xs = np.empty(len(idx)); Ys = np.empty(len(idx))
        for j, t in enumerate(idx):
            h = f.header[int(t)]
            il_s[j] = h[segyio.TraceField.INLINE_3D]
            xl_s[j] = h[segyio.TraceField.CROSSLINE_3D]
            Xs[j] = h[segyio.TraceField.CDP_X] * s
            Ys[j] = h[segyio.TraceField.CDP_Y] * s

    # ajuste afim: X = a*il + b*xl + c ; Y = d*il + e*xl + g
    A = np.column_stack([il_s, xl_s, np.ones_like(il_s)])
    cx, *_ = np.linalg.lstsq(A, Xs, rcond=None)
    cy, *_ = np.linalg.lstsq(A, Ys, rcond=None)
    resX = Xs - A @ cx; resY = Ys - A @ cy
    print(f'afim ajustada. RMS residuo X={np.sqrt((resX**2).mean()):.3f} m '
          f'Y={np.sqrt((resY**2).mean()):.3f} m (n={len(idx)} tracos)')
    print(f'  X = {cx[0]:.5f}*il + {cx[1]:.5f}*xl + {cx[2]:.3f}')
    print(f'  Y = {cy[0]:.5f}*il + {cy[1]:.5f}*xl + {cy[2]:.3f}')

    OUT_NPY.unlink(missing_ok=True)   # hard-link safe
    np.save(OUT_NPY, cube)
    geom = dict(
        survey='ST0202', domain='depth', crs='ED50 / UTM zone 31N (EPSG:23031)',
        shape_zyx=list(cube.shape), axis_order='(iz=depth, iy=inline, ix=crossline)',
        il0=int(ilines[0]), il_step=int(ilines[1]-ilines[0]), n_il=n_il,
        xl0=int(xlines[0]), xl_step=int(xlines[1]-xlines[0]), n_xl=n_xl,
        z0=float(depths[0]), dz=float(depths[1]-depths[0]), nz=nz,
        ilines=ilines.tolist(), xlines=xlines.tolist(), depths=depths.tolist(),
        affine_ilxl_to_XY=dict(X=cx.tolist(), Y=cy.tolist(),
                               note='X=X[0]*il+X[1]*xl+X[2]; idem Y'),
        segy=SEGY.relative_to(DATA).as_posix(),
    )
    json.dump(geom, open(OUT_GEOM, 'w'), indent=2)
    print('salvo:', OUT_NPY, f'({OUT_NPY.stat().st_size/1e6:.0f} MB)')
    print('salvo:', OUT_GEOM)


if __name__ == '__main__':
    main()

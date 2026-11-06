#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Interval P-velocity (Vp): SEG-Y -> native cube -> co-registered on the ST0202 depth grid.

Input : seismic/st0202/velocities/ST10010ZC11_MIG_VEL.segy
        (ST10010 2011 TTI migration velocity model, depth, 0-4500 m @ 20 m, ED50/UTM31N)
Output: prepared/vel_st10010_depth.npy + vel_st10010_geom.json   native grid (nz, n_il, n_xl)
        prepared/vel_coreg_st0202.npy                            ST0202 grid (901, 385, 605)

Co-registration: the velocity grid uses the same inline/crossline numbering and bin
geometry as ST0202 (affines agree to < 0.3 m), so the lateral step is an integer
il/xl offset (crop). Vertically, Vp is linearly interpolated from 20 m to 5 m.

This is a smooth migration-velocity model, not a well-calibrated property volume.

Extracted from the research scripts canal_velocidade_volve.py / escada_velocidade_volve.py
(same algorithm, same output). Idempotent.
Usage: python pipeline/preparar_velocidade.py
"""
import json

import numpy as np
import segyio

from _paths import DATA, PREP

SEGY = DATA / 'seismic' / 'st0202' / 'velocities' / 'ST10010ZC11_MIG_VEL.segy'
VEL_NPY = PREP / 'vel_st10010_depth.npy'
VEL_GEOM = PREP / 'vel_st10010_geom.json'
VEL_COREG = PREP / 'vel_coreg_st0202.npy'
GRID = PREP / 'cubo_st0202_geom.json'


def preparar_velocidade():
    """SEG-Y -> native npy (nz, n_il, n_xl) + geometry/affine."""
    if VEL_NPY.exists() and VEL_GEOM.exists():
        return
    PREP.mkdir(parents=True, exist_ok=True)
    with segyio.open(str(SEGY), iline=189, xline=193) as f:
        ilines = np.asarray(f.ilines, int)
        xlines = np.asarray(f.xlines, int)
        depths = np.asarray(f.samples, float)
        cube = segyio.tools.cube(f)                                  # (n_il, n_xl, nz)
        cube = np.ascontiguousarray(np.transpose(cube, (2, 0, 1)).astype(np.float32))
        scal = float(f.header[0][segyio.TraceField.SourceGroupScalar])
        s = (1.0 / abs(scal)) if scal < 0 else (abs(scal) if scal else 1.0)
        idx = np.linspace(0, f.tracecount - 1, num=min(4000, f.tracecount)).astype(int)
        il_s, xl_s, Xs, Ys = (np.empty(len(idx)) for _ in range(4))
        for j, t in enumerate(idx):
            h = f.header[int(t)]
            il_s[j] = h[segyio.TraceField.INLINE_3D]
            xl_s[j] = h[segyio.TraceField.CROSSLINE_3D]
            Xs[j] = h[segyio.TraceField.CDP_X] * s
            Ys[j] = h[segyio.TraceField.CDP_Y] * s
    A = np.column_stack([il_s, xl_s, np.ones_like(il_s)])
    cx, *_ = np.linalg.lstsq(A, Xs, rcond=None)
    cy, *_ = np.linalg.lstsq(A, Ys, rcond=None)
    print(f'vel cube {cube.shape} | depth {depths.min()}-{depths.max()} dz={depths[1] - depths[0]} '
          f'| Vp {np.nanmin(cube):.0f}-{np.nanmax(cube):.0f} m/s')
    VEL_NPY.unlink(missing_ok=True)   # hard-link safe
    np.save(VEL_NPY, cube)
    geom = dict(shape_zyx=list(cube.shape), z0=float(depths[0]), dz=float(depths[1] - depths[0]),
                il0=int(ilines[0]), il_step=int(ilines[1] - ilines[0]), n_il=len(ilines),
                xl0=int(xlines[0]), xl_step=int(xlines[1] - xlines[0]), n_xl=len(xlines),
                affine_ilxl_to_XY=dict(X=cx.tolist(), Y=cy.tolist()))
    json.dump(geom, open(VEL_GEOM, 'w'), indent=2)


def prepara_vel_coreg():
    """Native Vp -> ST0202 depth grid (integer il/xl crop + linear interpolation in depth)."""
    if VEL_COREG.exists():
        return
    preparar_velocidade()
    V = np.load(VEL_NPY, mmap_mode='r')                          # (nz_v, n_il_v, n_xl_v)
    gv = json.load(open(VEL_GEOM))
    ga = json.load(open(GRID))
    dil = ga['il0'] - gv['il0']
    dxl = ga['xl0'] - gv['xl0']
    nz, ny, nx = ga['nz'], ga['n_il'], ga['n_xl']
    Vsub = np.asarray(V[:, dil:dil + ny, dxl:dxl + nx], np.float32)
    out = np.empty((nz, ny, nx), np.float32)
    ratio = ga['dz'] / gv['dz']                                  # 5 / 20 = 0.25
    nzv = Vsub.shape[0]
    for iz in range(nz):
        p = iz * ratio
        k0 = int(p)
        fr = p - k0
        if k0 + 1 < nzv:
            out[iz] = (1 - fr) * Vsub[k0] + fr * Vsub[k0 + 1]
        else:
            out[iz] = Vsub[min(k0, nzv - 1)]
    VEL_COREG.unlink(missing_ok=True)   # hard-link safe
    np.save(VEL_COREG, out)
    print(f'co-registered Vp saved: {out.shape} -> {VEL_COREG.name}')


if __name__ == '__main__':
    prepara_vel_coreg()

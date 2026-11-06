#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Co-register the PP post-stack (TIME) onto the ST0202 DEPTH grid.

For each column (iy, ix) of the depth grid (5 m):
  1. PP two-way time at each depth: TWT(z) = cumsum(2*dz / Vp), with the co-registered
     migration velocity (preparar_velocidade.py);
  2. (iy, ix) -> nearest bin of the decimated PP grid (25 m);
  3. the PP trace is linearly interpolated at those TWTs -> PP in depth.

The time-depth relation is the migration velocity, not a well calibration.
Output: prepared/pp_coreg_st0202.npy (901, 385, 605), aligned with amplitude and Vp.
Usage:  python pipeline/preparar_pp_coreg.py
"""
import json
import numpy as np
from pathlib import Path
import preparar_velocidade as EV

from _paths import PREP
OUT = PREP/'pp_coreg_st0202.npy'


def main():
    if OUT.exists():
        print('ja existe:', OUT.name); return
    EV.prepara_vel_coreg()
    Vc = np.load(EV.VEL_COREG)                                # (901,385,605) profundidade
    PP = np.load(PREP/'pp_poststack_time.npy')               # (nI,nX,ns) tempo
    g = json.load(open(PREP/'pp_geom_time.json'))
    ga = json.load(open(PREP/'cubo_st0202_geom.json'))
    nz, ny, nx = ga['nz'], ga['n_il'], ga['n_xl']; dz = ga['dz']
    t_axis = g['t0_ms'] + g['dt_ms']*np.arange(g['ns'])       # ms
    # mapeamento lateral (iy,ix)->(iI,iX): mesma numeracao de linha, PP decimado
    # numero de inline do voxel = ga['il0']+iy ; idx PP = (num - g['il0'])/il_step
    out = np.empty((nz, ny, nx), np.float32)
    for iy in range(ny):
        iI = int(round((ga['il0']+iy - g['il0'])/g['il_step']))
        iI = min(max(iI, 0), g['n_il']-1)
        for ix in range(nx):
            iX = int(round((ga['xl0']+ix - g['xl0'])/g['xl_step']))
            iX = min(max(iX, 0), g['n_xl']-1)
            v = Vc[:, iy, ix].astype(np.float64)
            v = np.where(v > 100, v, np.nan)
            twt = np.nancumsum(2.0*dz/v)*1000.0                # ms por profundidade
            out[:, iy, ix] = np.interp(twt, t_axis, PP[iI, iX], left=PP[iI, iX, 0],
                                       right=PP[iI, iX, -1]).astype(np.float32)
        if iy % 40 == 0:
            print(f'  coluna inline {iy}/{ny}', end='\r', flush=True)
    print()
    OUT.unlink(missing_ok=True)   # hard-link safe
    np.save(OUT, out)
    print(f'PP co-registrado (profundidade): {out.shape} salvo {OUT.name}')


if __name__ == '__main__':
    main()

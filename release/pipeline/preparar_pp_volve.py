#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stack the ST0202 PZ PrSDM CIP gathers (PP, TIME) -> PP post-stack cube in time.

The input is pre-stack: several traces per (il, xl) bin, one per offset/angle class.
Stack = plain mean of all traces in a bin (no extra mute or weighting).
PP acoustic reflectivity (header: "positive = increase in acoustic impedance").
The gathers are on a decimated grid (every 2nd inline and crossline, 25 m).

Outputs: prepared/pp_poststack_time.npy (n_il, n_xl, ns) + prepared/pp_geom_time.json
Usage:   python pipeline/preparar_pp_volve.py   (reads the 20 GB gathers SEG-Y)
"""
import json
import numpy as np
import segyio
from pathlib import Path

from _paths import DATA, PREP
SEGY = DATA/'seismic'/'st0202'/'prestacks'/'PP_PZ_gathers_PP_time.segy'
OUT = PREP/'pp_poststack_time.npy'
GEOM = PREP/'pp_geom_time.json'


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with segyio.open(str(SEGY), iline=189, xline=193, ignore_geometry=True) as f:
        n = f.tracecount
        il = f.attributes(segyio.TraceField.INLINE_3D)[:].astype(np.int32)
        xl = f.attributes(segyio.TraceField.CROSSLINE_3D)[:].astype(np.int32)
        ns = len(f.samples); dt_ms = (f.samples[1]-f.samples[0])
        print(f'{n} tracos | {len(np.unique(il))} inlines × {len(np.unique(xl))} xlines | '
              f'ns={ns} dt={dt_ms} ms')
        ils = np.unique(il); xls = np.unique(xl)
        il_ix = {v: i for i, v in enumerate(ils)}; xl_ix = {v: i for i, v in enumerate(xls)}
        nI, nX = len(ils), len(xls)
        soma = np.zeros((nI, nX, ns), np.float64); cont = np.zeros((nI, nX), np.int32)
        # afim (il,xl)->(X,Y) por amostra de headers
        scal = f.header[0][segyio.TraceField.SourceGroupScalar]; s = float(scal)
        s = (1.0/abs(s)) if s < 0 else (abs(s) if s else 1.0)
        idx = np.linspace(0, n-1, min(4000, n)).astype(int)
        il_s = il[idx].astype(float); xl_s = xl[idx].astype(float)
        Xs = f.attributes(segyio.TraceField.CDP_X)[idx].astype(float)*s
        Ys = f.attributes(segyio.TraceField.CDP_Y)[idx].astype(float)*s
        # empilha em blocos (evita carregar 20 GB de uma vez, mas usa a RAM com folga)
        BLK = 200000
        for a in range(0, n, BLK):
            b = min(a+BLK, n)
            tr = f.trace.raw[a:b]                              # (blk, ns)
            ii = np.array([il_ix[v] for v in il[a:b]]); xx = np.array([xl_ix[v] for v in xl[a:b]])
            np.add.at(soma, (ii, xx), tr)
            np.add.at(cont, (ii, xx), 1)
            print(f'  empilhado {b}/{n}', end='\r', flush=True)
    print()
    stack = (soma / np.maximum(cont, 1)[:, :, None]).astype(np.float32)
    A = np.column_stack([il_s, xl_s, np.ones_like(il_s)])
    cx = np.linalg.lstsq(A, Xs, rcond=None)[0]; cy = np.linalg.lstsq(A, Ys, rcond=None)[0]
    OUT.unlink(missing_ok=True)   # hard-link safe
    np.save(OUT, stack)
    geom = dict(shape=[nI, nX, ns], il0=int(ils[0]), il_step=int(ils[1]-ils[0]), n_il=nI,
                xl0=int(xls[0]), xl_step=int(xls[1]-xls[0]), n_xl=nX,
                t0_ms=0.0, dt_ms=float(dt_ms), ns=ns, domain='PP_TWT',
                affine_ilxl_to_XY=dict(X=cx.tolist(), Y=cy.tolist()))
    json.dump(geom, open(GEOM, 'w'), indent=2)
    print(f'PP pos-stack: {stack.shape} | bins vazios: {(cont==0).sum()} | salvo {OUT.name}')
    print('geom:', GEOM.name, '| il_step', geom['il_step'], 'xl_step', geom['xl_step'])


if __name__ == '__main__':
    main()

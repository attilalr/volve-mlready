#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Parse COMPASS (Landmark) survey exports from the full Volve release (via Databricks).

Each `..._ACTUAL` file (and the 15/9-19 `*_Standard_Survey_NPD.txt`) has a SURVEY LIST:
  MD | Inc | Azim | TVD (RKB) | X-Offset | Y-Offset | UTM E/W | UTM N/S | DLS
-> keeps UTM E/W, UTM N/S (absolute, ED50 / UTM31N) and TVD AS GIVEN (from the drill floor).
   The datum correction to MSL (TVDSS = TVD - EDF) is applied later, in amarre_volve.py.
15/9-19 A is skipped on purpose: it is positioned from the independent OSDU trajectory.
Output: trajectories_pdf/{NPD}.csv with MD, Inclination, Azimuth, TVD, X, Y
(the folder name is historical: it first held surveys parsed from PDF reports).
Usage:  python pipeline/parse_compass_survey.py
"""
import re, os, glob, warnings
import pandas as pd
from pathlib import Path
import registry as dv
warnings.filterwarnings('ignore')

from _paths import DATA
DBX = DATA / 'dbx_extract'
OUT = DATA / 'trajectories_pdf'


def norm(s):
    """Normaliza nome de poço p/ casar fonte↔censo (F-wells e serie 15/9-19)."""
    s = s.upper().replace('15/9-', '').replace('159-', '')
    return re.sub(r'[\s/_]', '', s)


def wellbore_name(path):
    for l in open(path, errors='replace'):
        m = re.match(r'\s*WELLBORE NAME:\s*(.+)', l)
        if m:
            return m.group(1).strip()
    return None


def parse_compass(path):
    txt = open(path, errors='replace').read().splitlines()
    kbmsl = 0.0
    for l in txt:
        m = re.search(r'KB-MSL:\s*([\d.]+)', l)
        if m:
            kbmsl = float(m.group(1))
    try:
        i = next(k for k, l in enumerate(txt) if l.strip() == 'SURVEY LIST')
    except StopIteration:
        return None, kbmsl
    rows = []
    for l in txt[i+3:]:
        p = l.split()
        if len(p) >= 8 and re.match(r'-?\d+\.?\d*$', p[0]):
            try:
                rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[3]),
                             float(p[6]), float(p[7])))          # MD,Inc,Azi,TVD,UTM_E,UTM_N
            except ValueError:
                pass
    return rows, kbmsl


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    name2npd = {norm(nm): npd for npd, nm in dv.WELL_NAMES.items()}   # nome(norm) -> NPD (censo)

    # surveys COMPASS de duas pastas: F-wells (surveys/*_ACTUAL) e serie 19 (w19/*.txt)
    files = sorted(glob.glob(str(DBX / 'surveys' / '*_ACTUAL'))) + \
        sorted(glob.glob(str(DBX / 'w19' / '*.txt')))
    print('\nTrajetorias geradas (COMPASS, UTM absoluto, TVD como fornecido/RKB):')
    for sf in files:
        wb = wellbore_name(sf)                          # nome do header (robusto)
        if not wb:
            continue
        key = norm(wb)
        if key not in name2npd:
            continue                                    # so poços com PHIF (censo)
        npd = name2npd[key]
        if npd == 'NPD-3145':
            continue                                    # 19A: manter OSDU (ancora independente)
        rows, kbmsl = parse_compass(sf)
        if not rows:
            print(f'  {wb}: sem estacoes'); continue
        df = pd.DataFrame(rows, columns=['MD', 'Inclination', 'Azimuth', 'TVD', 'X', 'Y'])
        # TVD COMO FORNECIDO (RKB/DF). A correcao de datum (TVD - EDF) e aplicada em amarre_volve.py.
        df.to_csv(OUT / f'{npd}.csv', index=False)
        print(f'  {wb:<14} ({npd}): {len(df):3d} est.  MD {df.MD.min():.0f}-{df.MD.max():.0f}  '
              f'TVD(RKB) {df.TVD.min():.0f}-{df.TVD.max():.0f}  (KB-MSL={kbmsl}; corrigido no amarre)')


if __name__ == '__main__':
    main()

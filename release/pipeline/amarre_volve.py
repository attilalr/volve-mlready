#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Well tie: LAS (PHIF) + deviation survey -> samples and voxels on the ST0202 depth grid.

For each wellbore with an effective-porosity log (PHIF) AND a deviation survey:
  1. absolute (X, Y, TVD) per survey station (station_xyz):
       COMPASS export  -> X/Y (ED50 / UTM31N) and TVD already absolute;
       OSDU trajectory -> wellhead lat/lon projected to UTM31N + minimum curvature;
  2. (X, Y, TVD) interpolated at each log depth (MD), no extrapolation past the survey;
  3. depth datum: TVDSS = TVD - EDF  (drill-floor elevation above MSL, see below);
  4. (X, Y) -> (inline, crossline) by the inverse grid affine, TVDSS -> iz; nearest cell;
  5. keep samples inside the cube with finite PHIF (PHIF is renamed PHIE).
  Upscaling: one mean PHIE per (well, voxel) of 12.5 x 12.5 x 5 m.

Depth datum. The cube is referenced to mean sea level (the F-11 T2 checkshot states
"Depth datum: MSL"); surveys and logs are measured from the drill floor, EDF metres
above MSL. EDF comes ONLY from metadata: LAS header (EDF) or, when absent, the
documented table EDF_FALLBACK (54.9 m for the Volve F platform, 25.0 m for the
15/9-19 exploration wells; both also equal the KB-MSL in the COMPASS headers).
Z is never calibrated against the target (that would leak the target into the tie).

Outputs: prepared/wells_volve.csv (voxels), prepared/wells_volve_samples.csv (samples)
Usage:   python pipeline/amarre_volve.py
(Inline comments are in Portuguese; the module was written for a Portuguese-language project.)
"""
import os, json, glob, warnings
import numpy as np
import pandas as pd
import lasio
from pathlib import Path
from pyproj import Transformer

warnings.filterwarnings('ignore')
from _paths import DATA, PREP
WL = DATA / 'welllogs'
TRAJ = DATA / 'trajectories'          # formato OSDU (MD,Incl,Azi,SurfaceX/Y lat/lon)
TRAJ_PDF = DATA / 'trajectories_pdf'  # formato EOWR PDF (MD,Incl,Azi,TVD,X,Y absolutos UTM31 ED50)
GEOM = DATA / 'prepared' / 'cubo_st0202_geom.json'
OUT = DATA / 'prepared' / 'wells_volve.csv'              # UPSCALED por voxel (treino)
OUT_SAMPLES = DATA / 'prepared' / 'wells_volve_samples.csv'  # amostras cruas (QC/traco)

# LAS com curva de porosidade efetiva PHIF (um por poco). WELL header = id NPD.
PHIF_GLOBS = ['*_CPI.las', 'WLC_PETRO_COMPUTED_OUTPUT_1*.LAS']
PORO_CURVE = 'PHIF'

# O LAS do F-11T2 vem do extrato Databricks e traz WELL='15/9-F-11 T2'; o resto do
# projeto (trajectories_pdf/F-11T2.csv, dataset_volve.WELL_ORDER) usa a chave 'F-11T2'.
WELL_ALIAS = {'15/9-F-11 T2': 'F-11T2'}

# --- Elevacao do piso de perfuracao (EDF, m acima do MSL) por poco -----------
# Usado so quando o cabecalho LAS nao traz EDF. Duas sondas no conjunto:
#
#  * Plataforma F (Maersk Inspirer) — EDF = 54,9 m.
#    Explicito no LAS de F-11A/F-11B/F-11T2/F-1C/F-15D ("PD=MSL, EDF=54.900,
#    EGL=-91.000, LMF=DF"). Os demais poços F herdam: TODOS os surveys da
#    plataforma comecam em MD=TVD=145,9 = 54,9 (EDF) + 91,0 (lamina d'agua),
#    i.e. a primeira estacao esta no fundo do mar.
#
#  * Poços exploratorios 15/9-19 (A, SR) — EDF = 25,0 m.
#    Dos checkshots (checkshot_15_9_19A.txt, checkshot_15_9_19_SR.txt), que
#    tabulam TVD contra TVDSS: TVD = TVDSS + 25,00. Coerente com o survey
#    comecando em MD=TVD=109 = 25,0 + 84,0 (lamina d'agua no 15/9-19).
EDF_FALLBACK = {
    'NPD-3145': (25.0, 'checkshot_15_9_19A.txt: TVD = TVDSS + 25.00'),
    'NPD-2105': (25.0, 'checkshot_15_9_19_SR.txt: TVD = TVDSS + 25.00'),
    'NPD-7224': (54.9, 'F platform (survey starts at MD=TVD=145.9 = 54.9 EDF + 91.0 water depth)'),
    'NPD-5599': (54.9, 'F platform (survey starts at MD=TVD=145.9 = 54.9 EDF + 91.0 water depth)'),
    'NPD-7223': (54.9, 'F platform (survey starts at MD=TVD=145.9 = 54.9 EDF + 91.0 water depth)'),
    'NPD-7264': (54.9, 'F platform (survey starts at MD=TVD=145.9 = 54.9 EDF + 91.0 water depth)'),
}


def edf_do_poco(las, npd):
    """Elevacao do piso de perfuracao (m acima do MSL) + a fonte da informacao.

    Prioridade: cabecalho LAS (EDF) > tabela documentada EDF_FALLBACK. Quando os
    dois existem, confere a coerencia — divergencia e erro de dado, nao detalhe.
    """
    edf_las = None
    if 'EDF' in las.well and las.well['EDF'].value not in (None, ''):
        try:
            edf_las = float(las.well['EDF'].value)
        except (TypeError, ValueError):
            edf_las = None
    edf_tab, fonte_tab = EDF_FALLBACK.get(npd, (None, None))
    if edf_las is not None:
        if edf_tab is not None and abs(edf_las - edf_tab) > 0.1:
            raise ValueError(f'{npd}: EDF do LAS ({edf_las}) diverge da tabela '
                             f'({edf_tab}, {fonte_tab}) — resolver antes de amarrar.')
        return edf_las, 'LAS header (EDF)'
    if edf_tab is not None:
        return edf_tab, fonte_tab
    raise ValueError(f'{npd}: sem EDF no LAS e sem entrada em EDF_FALLBACK. '
                     f'O datum de Z e obrigatorio — nao amarrar sem ele.')


def min_curvature(md, inc_deg, azi_deg):
    """Integra deviation survey -> (north, east, tvd) offsets (m) a partir do cabecote."""
    inc = np.radians(inc_deg); azi = np.radians(azi_deg)
    n = len(md)
    north = np.zeros(n); east = np.zeros(n); tvd = np.zeros(n)
    for i in range(1, n):
        dMD = md[i] - md[i-1]
        I1, I2, A1, A2 = inc[i-1], inc[i], azi[i-1], azi[i]
        cosb = np.cos(I2 - I1) - np.sin(I1)*np.sin(I2)*(1 - np.cos(A2 - A1))
        cosb = np.clip(cosb, -1.0, 1.0)
        beta = np.arccos(cosb)
        rf = 1.0 if beta < 1e-9 else (2.0/beta)*np.tan(beta/2.0)
        north[i] = north[i-1] + (dMD/2)*(np.sin(I1)*np.cos(A1)+np.sin(I2)*np.cos(A2))*rf
        east[i]  = east[i-1]  + (dMD/2)*(np.sin(I1)*np.sin(A1)+np.sin(I2)*np.sin(A2))*rf
        tvd[i]   = tvd[i-1]   + (dMD/2)*(np.cos(I1)+np.cos(I2))*rf
    return north, east, tvd


def station_xyz(tj, tr):
    """Absolute (X, Y, TVD from drill floor) at each survey station.

    COMPASS/PDF format: X, Y, TVD are already absolute.
    OSDU format: wellhead lat/lon (ED50; SurfaceX holds the LATITUDE, SurfaceY the
    LONGITUDE) + minimum curvature. min_curvature() returns offsets that start at 0 at
    the FIRST STATION, which is not at the drill floor (15/9-19 A starts at
    MD = TVD = 109 m, the seabed). The first station's TVD must be added back;
    leaving it out put 15/9-19 A 109 m too shallow (fixed in v1.0.0, see CHANGELOG).
    """
    if {'X', 'Y', 'TVD'} <= set(tj.columns):
        return tj.X.values, tj.Y.values, tj.TVD.values
    lat0, lon0 = float(tj.SurfaceX.iloc[0]), float(tj.SurfaceY.iloc[0])
    X0, Y0 = tr.transform(lon0, lat0)                      # ED50 geographic -> UTM31 ED50
    north, east, tvd = min_curvature(tj.MD.values, tj.Inclination.values, tj.Azimuth.values)
    tvd0 = float(tj.TVD.iloc[0]) if 'TVD' in tj.columns else float(tj.MD.iloc[0])
    return X0 + east, Y0 + north, tvd0 + tvd


def load_geom():
    g = json.load(open(GEOM))
    Xc = np.array(g['affine_ilxl_to_XY']['X']); Yc = np.array(g['affine_ilxl_to_XY']['Y'])
    # [a b; d e] [il;xl] = [X-c ; Y-g]
    M = np.array([[Xc[0], Xc[1]], [Yc[0], Yc[1]]])
    Minv = np.linalg.inv(M); off = np.array([Xc[2], Yc[2]])
    g['_Minv'] = Minv; g['_off'] = off
    return g


def xy_to_ilxl(g, X, Y):
    rhs = np.vstack([X - g['_off'][0], Y - g['_off'][1]])
    ilxl = g['_Minv'] @ rhs
    return ilxl[0], ilxl[1]      # il, xl (continuos)


def build_manifest():
    """Casa cada LAS-PHIF com sua trajetoria (por id NPD no header WELL)."""
    man = []
    for pat in PHIF_GLOBS:
        for f in sorted(glob.glob(str(WL / pat))):
            las = lasio.read(f, ignore_header_errors=True)
            if PORO_CURVE not in [c.mnemonic for c in las.curves]:
                continue
            npd = str(las.well.WELL.value).strip()
            npd = WELL_ALIAS.get(npd, npd)
            tf, tf_pdf = TRAJ / f'{npd}.csv', TRAJ_PDF / f'{npd}.csv'
            traj = str(tf_pdf) if tf_pdf.exists() else (str(tf) if tf.exists() else None)
            man.append(dict(las=f, npd=npd, name=os.path.basename(f),
                            traj=traj, has_traj=traj is not None,
                            fmt='pdf' if tf_pdf.exists() else 'osdu'))
    return man


def process_well(g, las_path, traj_path, npd, well_idx, tr):
    las = lasio.read(las_path, ignore_header_errors=True)
    md = np.asarray(las.index, dtype=float)                 # MD (m)
    phie = np.asarray(las[PORO_CURVE], dtype=float)
    tj = pd.read_csv(traj_path).sort_values('MD').reset_index(drop=True)
    X_st, Y_st, TVD_st = station_xyz(tj, tr)
    Xs = np.interp(md, tj.MD.values, X_st)
    Ys = np.interp(md, tj.MD.values, Y_st)
    TVDs = np.interp(md, tj.MD.values, TVD_st)
    # datum: survey/log medidos do piso de perfuracao; cubo referenciado ao MSL
    edf, fonte_edf = edf_do_poco(las, npd)
    TVDSS = TVDs - edf

    il, xl = xy_to_ilxl(g, Xs, Ys)
    IY = np.round((il - g['il0'])/g['il_step']).astype(int)
    IX = np.round((xl - g['xl0'])/g['xl_step']).astype(int)
    IZ = np.round((TVDSS - g['z0'])/g['dz']).astype(int)
    df = pd.DataFrame(dict(well=well_idx, npd=npd, MD=md, TVD=TVDs, TVDSS=TVDSS,
                           EDF=edf, X=Xs, Y=Ys,
                           IL=il, XL=xl, IX=IX, IY=IY, IZ=IZ, PHIE=phie))
    df.attrs['fonte_edf'] = fonte_edf
    inrange = (md >= tj.MD.min()) & (md <= tj.MD.max())     # so onde o survey cobre (sem extrapolar)
    inside = (IX >= 0) & (IX < g['n_xl']) & (IY >= 0) & (IY < g['n_il']) & \
             (IZ >= 0) & (IZ < g['nz']) & np.isfinite(phie) & inrange
    df['inside'] = inside
    return df


def upscale_voxel(df):
    """Upscale log->sismica: 1 PHIE medio por voxel (well, IX, IY, IZ) de 5 m.

    Corrige a inflacao artificial de amostras (~33 amostras de log 0,15 m por voxel de 5 m)
    e torna o LOOCV honesto. Mantem por-poco (well no key) p/ nao misturar pocos no mesmo voxel.
    """
    agg = (df.groupby(['well', 'npd', 'IX', 'IY', 'IZ'], as_index=False)
             .agg(PHIE=('PHIE', 'mean'), PHIE_std=('PHIE', 'std'), n_amostras=('PHIE', 'size'),
                  MD=('MD', 'mean'), TVD=('TVD', 'mean'), TVDSS=('TVDSS', 'mean'),
                  EDF=('EDF', 'first'), X=('X', 'mean'), Y=('Y', 'mean'),
                  IL=('IL', 'mean'), XL=('XL', 'mean')))
    agg['PHIE_std'] = agg['PHIE_std'].fillna(0.0)
    return agg


def main():
    g = load_geom()
    tr = Transformer.from_crs('EPSG:4230', 'EPSG:23031', always_xy=True)  # ED50geo->ED50/UTM31N
    man = build_manifest()
    print('Manifesto de pocos com PHIF:')
    for m in man:
        print(f"  {m['name']:<34} NPD={m['npd']:<10} trajetoria={'SIM' if m['has_traj'] else 'FALTA'}")
    proc = [m for m in man if m['has_traj']]
    print(f'\n{len(proc)}/{len(man)} pocos processaveis (com trajetoria).')

    frames = []
    for i, m in enumerate(proc):
        df = process_well(g, m['las'], m['traj'], m['npd'], i, tr)
        ins = df[df.inside]
        print(f"  {m['npd']}: {len(ins)}/{len(df)} amostras dentro do cubo | "
              f"IZ {ins.IZ.min()}-{ins.IZ.max()} IY {ins.IY.min()}-{ins.IY.max()} "
              f"IX {ins.IX.min()}-{ins.IX.max()} | PHIE mean={ins.PHIE.mean():.3f} | "
              f"EDF={ins.EDF.iloc[0]:.1f} m ({df.attrs['fonte_edf']})")
        frames.append(ins)

    if frames:
        samples = pd.concat(frames, ignore_index=True)
        voxel = upscale_voxel(samples)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        samples.to_csv(OUT_SAMPLES, index=False)
        voxel.to_csv(OUT, index=False)
        print(f'\nSamples (cru):  {len(samples)} amostras, {samples.well.nunique()} pocos -> {OUT_SAMPLES.name}')
        print(f'Voxel (treino): {len(voxel)} voxels,  {voxel.well.nunique()} pocos -> {OUT.name}')
        print(f'  reducao {len(samples)}->{len(voxel)} ({len(samples)/max(1,len(voxel)):.1f}x) | '
              f'PHIE_std medio intra-voxel = {voxel.PHIE_std.mean():.4f}')


if __name__ == '__main__':
    main()

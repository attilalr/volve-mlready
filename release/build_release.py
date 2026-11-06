#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assemble the flat, upload-ready dataset package (Zenodo stores files flat, max 100).

Reads the working tree produced by the pipeline ($VOLVE_DATA, default <repo>/release/data/volve)
and writes OUT (default ~/Desktop/volve-mlready-v<VERSION>/):

  README.md, DATA_LICENSE.md, Equinor_Open_Data_Licence_Volve.pdf, CITATION.cff, CHANGELOG.md
  grid_st0202_depth.json
  st0202_ps_amplitude_depth.npy            (901, 385, 605) float32   [hard link]
  vp_on_st0202_depth.npy                   (901, 385, 605) float32   [hard link]
  pp_amplitude_on_st0202_depth.npy         (901, 385, 605) float32   [hard link]
  vp_st10010_native_depth.npy / .json      (226, 436, 961) float32   [hard link]
  pp_poststack_st0202_time.npy / .json     (193, 303, 1126) float32  [hard link]
  wells.zip          wells_index.csv, wells_voxels.csv, wells_samples.csv, trajectories/*.csv
  source_files.zip   unmodified source files used (LAS, surveys, checkshots, markers, header)
  code.zip           snapshot of the GitHub repository: loader, notebooks, pipeline (MIT)
  SHA256SUMS.txt

Large arrays are hard-linked (no extra disk use) when OUT is on the same filesystem.
Usage: python release/build_release.py [--out DIR]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import lasio
import numpy as np
import pandas as pd
from pyproj import Transformer

HERE = Path(__file__).resolve().parent          # <repo>/release
REPO = HERE.parent
sys.path.insert(0, str(HERE / 'pipeline'))
from _paths import DATA, PREP  # noqa: E402
import amarre_volve as AM      # noqa: E402
from registry import WELL_NAMES, WELL_ORDER  # noqa: E402

VERSION = '1.0.0'

ARRAYS = {   # package name -> source (relative to PREP)
    'st0202_ps_amplitude_depth.npy': 'cubo_st0202_depth.npy',
    'vp_on_st0202_depth.npy': 'vel_coreg_st0202.npy',
    'pp_amplitude_on_st0202_depth.npy': 'pp_coreg_st0202.npy',
    'vp_st10010_native_depth.npy': 'vel_st10010_depth.npy',
    'pp_poststack_st0202_time.npy': 'pp_poststack_time.npy',
}
SIDE_JSON = {
    'vp_st10010_native_depth.json': 'vel_st10010_geom.json',
    'pp_poststack_st0202_time.json': 'pp_geom_time.json',
}
DOCS = {   # package name -> path relative to REPO
    'README.md': 'release/DATASET_README.md', 'DATA_LICENSE.md': 'DATA_LICENSE.md',
    'CITATION.cff': 'CITATION.cff', 'CHANGELOG.md': 'CHANGELOG.md',
    'Equinor_Open_Data_Licence_Volve.pdf': 'licenses/Equinor_Open_Data_Licence_Volve.pdf'}
# unmodified source files, kept in the layout the pipeline expects under $VOLVE_DATA
SOURCES = ['welllogs', 'trajectories', 'dbx_extract/surveys', 'dbx_extract/w19',
           'checkshots', 'markers', 'seismic/SeismicOrderSummary+Header.txt']
# snapshot of the GitHub repository (relative to REPO); ZENODO_pt.md is internal
CODE = ['src', 'notebooks', 'docs', 'release/pipeline', 'release/build_release.py',
        'release/make_worktree.sh', 'release/DATASET_README.md', 'pyproject.toml',
        'environment.yml', 'README.md', 'LICENSE', 'DATA_LICENSE.md', 'CITATION.cff',
        'CHANGELOG.md', 'licenses']


def sha256(path, chunk=8 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def link_or_copy(src, dst):
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def zip_tree(zpath, root, items, arc_prefix=''):
    """Deterministic zip (sorted entries, fixed timestamps)."""
    files = []
    for it in items:
        p = root / it
        if p.is_dir():
            files += sorted(q for q in p.rglob('*') if q.is_file() and not any(
                part == '__pycache__' or part.endswith(('.egg-info', '.ipynb_checkpoints'))
                for part in q.parts))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(p)
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(set(files)):
            zi = zipfile.ZipInfo(arc_prefix + f.relative_to(root).as_posix(), (2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, f.read_bytes())
    return len(files)


def build_wells(tmp):
    """wells_index.csv, wells_voxels.csv, wells_samples.csv, trajectories/*.csv."""
    vox = pd.read_csv(PREP / 'wells_volve.csv').rename(columns={'n_amostras': 'n_samples'})
    smp = pd.read_csv(PREP / 'wells_volve_samples.csv')
    assert smp['inside'].all(), 'samples CSV should only hold in-cube samples'
    smp = smp.drop(columns='inside')
    for df in (vox, smp):
        df.insert(2, 'wellbore', df['npd'].map(WELL_NAMES))
    vox.to_csv(tmp / 'wells_voxels.csv', index=False)
    smp.to_csv(tmp / 'wells_samples.csv', index=False)

    g = AM.load_geom()
    tr = Transformer.from_crs('EPSG:4230', 'EPSG:23031', always_xy=True)
    tdir = tmp / 'trajectories'
    tdir.mkdir()
    rows = []
    man = {m['npd']: m for m in AM.build_manifest()}
    for npd in WELL_ORDER:
        m = man[npd]
        las = lasio.read(m['las'], ignore_header_errors=True)
        edf, edf_src = AM.edf_do_poco(las, npd)
        tj = pd.read_csv(m['traj']).sort_values('MD').reset_index(drop=True)
        X, Y, TVD = AM.station_xyz(tj, tr)      # same function the well tie uses
        src = ('COMPASS survey export, full Volve release (Databricks)' if m['fmt'] == 'pdf'
               else 'OSDU Open Test Data trajectory (minimum curvature from wellhead)')
        t = pd.DataFrame(dict(MD=tj.MD.values, INC=tj.Inclination.values, AZI=tj.Azimuth.values,
                              TVD_DF=TVD, TVDSS=TVD - edf, X=X, Y=Y))
        t.round(4).to_csv(tdir / f'{npd}.csv', index=False)
        v = vox[vox.npd == npd]
        s = smp[smp.npd == npd]
        rows.append(dict(
            npd=npd, wellbore=WELL_NAMES[npd], las_file=Path(m['las']).name,
            survey_source=src, survey_file=Path(m['traj']).name, n_stations=len(t),
            EDF_m=edf, EDF_source=edf_src, wellhead_X=round(X[0], 2), wellhead_Y=round(Y[0], 2),
            max_inclination_deg=float(tj.Inclination.max()),
            n_samples=len(s), n_voxels=len(v),
            MD_min=s.MD.min(), MD_max=s.MD.max(),
            TVDSS_min=round(s.TVDSS.min(), 2), TVDSS_max=round(s.TVDSS.max(), 2),
            IZ_min=int(v.IZ.min()), IZ_max=int(v.IZ.max()),
            PHIE_mean=round(v.PHIE.mean(), 4)))
    pd.DataFrame(rows).to_csv(tmp / 'wells_index.csv', index=False)
    return len(vox), len(smp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path.home() / 'Desktop' / f'volve-mlready-v{VERSION}')
    a = ap.parse_args()
    out = a.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    print(f'source: {DATA}\nout:    {out}')

    for dst, src in ARRAYS.items():
        link_or_copy(PREP / src, out / dst)
        arr = np.load(out / dst, mmap_mode='r')
        print(f'  {dst:<36} {str(arr.shape):<18} {arr.dtype}')
    for dst, src in SIDE_JSON.items():
        shutil.copy2(PREP / src, out / dst)

    grid = json.load(open(PREP / 'cubo_st0202_geom.json'))
    grid['segy'] = 'seismic/st0202/stacks/ST0202R08_PSDM_FULL_OFFSET_DEPTH_POSTSTACK.segy'
    grid['z_reference'] = 'depth below mean sea level (TVDSS), metres: z = z0 + dz*iz'
    grid['wave_mode'] = 'PS (converted wave), PSDM full offset, post-stack'
    grid['arrays_on_this_grid'] = ['st0202_ps_amplitude_depth.npy', 'vp_on_st0202_depth.npy',
                                   'pp_amplitude_on_st0202_depth.npy']
    json.dump(grid, open(out / 'grid_st0202_depth.json', 'w'), indent=2)

    tmp = out / '_wells'
    tmp.mkdir()
    nv, ns = build_wells(tmp)
    zip_tree(out / 'wells.zip', tmp, ['wells_index.csv', 'wells_voxels.csv',
                                      'wells_samples.csv', 'trajectories'])
    shutil.rmtree(tmp)
    print(f'  wells.zip: {nv} voxels, {ns} samples')
    n = zip_tree(out / 'source_files.zip', DATA, SOURCES)
    print(f'  source_files.zip: {n} files')
    n = zip_tree(out / 'code.zip', REPO, CODE, arc_prefix=f'volve-mlready-{VERSION}/')
    print(f'  code.zip: {n} files')

    for dst, src in DOCS.items():
        shutil.copy2(REPO / src, out / dst)

    files = sorted(p for p in out.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt')
    with open(out / 'SHA256SUMS.txt', 'w') as f:
        for p in files:
            f.write(f'{sha256(p)}  {p.name}\n')
    tot = sum(p.stat().st_size for p in files)
    print(f'\n{len(files) + 1} files, {tot / 1e9:.2f} GB  ->  {out}')


if __name__ == '__main__':
    main()

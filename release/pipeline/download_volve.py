#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download the raw Volve seismic used by this dataset (reproducible, anonymous HTTP).

Source: OSDU Open Test Data public S3 bucket  s3://osdu-seismic-test-data/volve/
        (documented at https://community.opengroup.org/osdu/data/open-test-data).
        No account, token or AWS CLI is needed.
Licence of the data: Equinor Open Data Licence (see ../licenses/). The data are
redistributed by OSDU; they are not endorsed by Equinor or the Volve partners.

What is downloaded (into $VOLVE_DATA, default <repo>/data/volve):
  default            ST0202 PS PSDM full-offset post-stack, DEPTH          (895 MB)
  --with-velocity    ST10010 2011 TTI migration velocity, DEPTH            (479 MB)
  --with-gathers     ST0202 PZ PrSDM CIP gathers in PP TIME (pre-stack)    (20.3 GB)
  --no-cube          skip the 895 MB depth cube

Well logs, trajectories, COMPASS survey exports, checkshots and markers are NOT
downloaded here: they ship inside `source_files.zip` of the dataset record
(some of them only exist in the full Volve release on Databricks).

Idempotent: files already present with the expected size are skipped. Each file is
checked against the SHA-256 recorded when the dataset was built.

Usage:
    python pipeline/download_volve.py [--no-cube] [--with-velocity] [--with-gathers]
"""
import hashlib
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from _paths import DATA

BASE = 'https://osdu-seismic-test-data.s3.amazonaws.com'

# (flag, S3 key, local path relative to DATA, size in bytes, sha256 or None)
FILES = [
    ('cube',
     'volve/seismic/st0202/stacks/ST0202R08-PS_PSDM_FULL_OFFSET_DEPTH.MIG_FIN.POST_Stack.3D.JS-017534.segy',
     'seismic/st0202/stacks/ST0202R08_PSDM_FULL_OFFSET_DEPTH_POSTSTACK.segy',
     895367300, 'd2c76ac2c9a3db1ebbeb24beff0c774bf26aae3d39f9ce928a734c49412bc2e1'),
    ('header',
     'volve/seismic/st0202/stacks/SeismicOrderSummary+Header.txt',
     'seismic/SeismicOrderSummary+Header.txt', 446268, None),
    ('velocity',
     'volve/seismic/st0202/velocities/TTI_model_2011/ST10010ZC11_MIG_VEL.MIG_VEL.VELOCITY.3D.JS-017527.segy',
     'seismic/st0202/velocities/ST10010ZC11_MIG_VEL.segy', 479335024, None),
    ('gathers',
     'volve/seismic/st0202/prestacks/ST0202R08_PZ_PrSDM_CIP_gathers_in_PP_Time.segy',
     'seismic/st0202/prestacks/PP_PZ_gathers_PP_time.segy', 20311496528, None),
]


def sha256(path, chunk=8 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def fetch(key, dest, size, digest):
    dest = DATA / dest
    if dest.exists() and dest.stat().st_size == size:
        print(f'  skip {dest.name} (already present)')
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f'  get  {dest.name} ({size / 1e6:,.0f} MB) ...', flush=True)
        tmp = dest.with_suffix(dest.suffix + '.part')
        urllib.request.urlretrieve(BASE + '/' + urllib.parse.quote(key), tmp)
        if tmp.stat().st_size != size:
            raise RuntimeError(f'{dest.name}: size {tmp.stat().st_size} != expected {size}')
        tmp.rename(dest)
    if digest:
        got = sha256(dest)
        if got != digest:
            raise RuntimeError(f'{dest.name}: sha256 mismatch ({got})')
        print(f'       sha256 ok')


def main():
    args = set(sys.argv[1:])
    want = {'header'}
    if '--no-cube' not in args:
        want.add('cube')
    if '--with-velocity' in args:
        want.add('velocity')
    if '--with-gathers' in args:
        want.add('gathers')
    print(f'Destination: {DATA}')
    for flag, key, dest, size, digest in FILES:
        if flag in want:
            fetch(key, dest, size, digest)
    print('\nDone. Next: see pipeline/README.md for the processing order.')


if __name__ == '__main__':
    main()

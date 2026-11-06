"""Regenerate and execute the example notebooks (maintainer tool).

    VOLVE_MLREADY_DIR=/path/to/volve-mlready-v1.0.0 python notebooks/build_notebooks.py

Needs nbformat, nbclient and ipykernel. The notebooks are kept as plain code here so
they can be reviewed in diffs; the executed .ipynb files are committed for GitHub to render.
"""
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent


def md(s):
    return nbf.v4.new_markdown_cell(s.strip())


def code(s):
    return nbf.v4.new_code_cell(s.strip())


SETUP = '''
import os
import numpy as np
import pandas as pd
from volve_mlready import VolveMLReady

# folder holding the files downloaded from Zenodo
DATA = os.environ.get('VOLVE_MLREADY_DIR', '../data/volve-mlready-v1.0.0')
v = VolveMLReady(DATA)
'''

NB1 = [
    md('''
# 1 · Opening the dataset

This notebook shows how to load every part of the **Volve ML-ready** dataset and how its
indices and coordinates fit together. You only need `numpy` and `pandas`. The
`volve_mlready` helper is a thin convenience layer, and each step also shows the plain
`numpy`/`pandas` call.

**Before you start:** download the files from Zenodo (DOI `10.5281/zenodo.TODO`) into
`data/volve-mlready-v1.0.0/`, or set `VOLVE_MLREADY_DIR`. See the README for the
`volve_mlready.download()` helper.
'''),
    code(SETUP),
    md('## What is in the folder'),
    code('''
files = sorted(p for p in v.root.iterdir() if p.is_file())
pd.DataFrame({'file': [p.name for p in files],
              'MB': [round(p.stat().st_size / 1e6, 1) for p in files]})
'''),
    md('''
Optional integrity check against `SHA256SUMS.txt` (reads all 3.2 GB, takes a few seconds
to a minute):
'''),
    code('''
from volve_mlready import verify
status = verify(DATA)
print({k: n for k, n in pd.Series(status).value_counts().items()})
'''),
    md('''
## The common grid

The three main cubes share one grid, described in `grid_st0202_depth.json`. Arrays are
indexed `C[iz, iy, ix]`: depth below mean sea level, inline, crossline.
'''),
    code('''
g = v.grid
print('shape (z, inline, crossline):', g['shape_zyx'])
print(f"depth : z = {g['z0']} + {g['dz']}*iz   ->  {g['depths'][0]}-{g['depths'][-1]} m below MSL")
print(f"inline: IL = {g['il0']} + iy           ->  {g['ilines'][0]}-{g['ilines'][-1]}")
print(f"xline : XL = {g['xl0']} + ix           ->  {g['xlines'][0]}-{g['xlines'][-1]}")
print('CRS   :', g['crs'])
print('wave  :', g['wave_mode'])
'''),
    md('''
## The cubes

`np.load(..., mmap_mode='r')` maps the file without reading it, so slicing is cheap and the
840 MB arrays never have to fit in memory at once.
'''),
    code('''
cubes = {name: v.cube(name) for name in ['ps_amplitude', 'vp', 'pp_amplitude']}
# the same without the helper:
amp_plain = np.load(v.root / 'st0202_ps_amplitude_depth.npy', mmap_mode='r')

pd.DataFrame({name: {'shape': c.shape, 'dtype': str(c.dtype), 'GB': round(c.nbytes / 1e9, 2)}
              for name, c in cubes.items()}).T
'''),
    code('''
# summary statistics on a 1-in-5 subsample of the reservoir interval (2500-3400 m)
iz0, iz1 = int(2500 / g['dz']), int(3400 / g['dz'])
rows = {}
for name, c in cubes.items():
    s = np.asarray(c[iz0:iz1:5, ::5, ::5], dtype=np.float64)
    rows[name] = dict(min=s.min(), p1=np.percentile(s, 1), median=np.median(s),
                      p99=np.percentile(s, 99), max=s.max())
pd.DataFrame(rows).T.map(lambda x: float(f'{x:.4g}'))
'''),
    md('''
## Coordinates

`(inline, crossline) → (X, Y)` is an affine transform in ED50 / UTM 31N. The helper exposes
it both ways, and also between grid indices and world coordinates.
'''),
    code('''
X, Y, z = v.index_to_world(iz=590, iy=200, ix=300)
print(f'cell (590, 200, 300) centre: X={float(X):.1f} m  Y={float(Y):.1f} m  z={float(z):.0f} m TVDSS')
print('back to indices:', v.world_to_index(X, Y, z))
'''),
    md('''
## The wells

Three tables live inside `wells.zip`, plus one trajectory per well:

* `index`: one row per wellbore (sources, datum, counts);
* `voxels`: the **training table**, one row per (well, voxel), with the target `PHIE`;
* `samples`: the original log samples (0.1–0.15 m), before upscaling.
'''),
    code('''
idx = v.wells('index')
idx[['npd', 'wellbore', 'survey_file', 'EDF_m', 'max_inclination_deg',
     'n_samples', 'n_voxels', 'TVDSS_min', 'TVDSS_max', 'PHIE_mean']]
'''),
    code('''
vox = v.wells('voxels')
smp = v.wells('samples')
print(f'{len(vox):,} voxels and {len(smp):,} samples from {vox.npd.nunique()} wellbores')
vox.head()
'''),
    code('''
# the same without the helper
import zipfile
with zipfile.ZipFile(v.root / 'wells.zip') as z:
    print(z.namelist()[:5], '...')
    vox_plain = pd.read_csv(z.open('wells_voxels.csv'))
assert vox_plain.equals(vox)
'''),
    code('''
v.trajectory('NPD-7080').iloc[::40]       # 15/9-F-11 B, a horizontal producer
'''),
    md('''
## Cube values at the wells

`IZ, IY, IX` in the voxel table index straight into any of the three cubes, so building a
feature table is one line per cube.
'''),
    code('''
feat = pd.DataFrame({name: np.asarray(c[vox.IZ.values, vox.IY.values, vox.IX.values])
                     for name, c in cubes.items()})
feat['PHIE'] = vox.PHIE.values
feat['well'] = vox.wellbore.values
feat.head()
'''),
    md('''
For context-based models, cut a window around each voxel. Here is a vertical trace of
±10 samples (±50 m), with edge padding:
'''),
    code('''
def vertical_windows(cube, iz, iy, ix, half=10):
    nz = cube.shape[0]
    offs = np.arange(-half, half + 1)
    zz = np.clip(iz[:, None] + offs[None, :], 0, nz - 1)
    return np.asarray(cube[zz, iy[:, None], ix[:, None]])

W = vertical_windows(cubes['ps_amplitude'], vox.IZ.values, vox.IY.values, vox.IX.values)
print('windows:', W.shape, '(voxels, samples)')
'''),
    md('''
## Validation: group by well

Neighbouring voxels of the same well are strongly correlated, and some wells share a slot
(the F-1 and F-11 families). **Split by well, never by voxel.** For example, use
leave-one-well-out:
'''),
    code('''
groups = vox.npd.values
for test_well in np.unique(groups)[:3]:
    train, test = groups != test_well, groups == test_well
    print(f'{test_well}: train {train.sum():4d} voxels / test {test.sum():3d} voxels')
print('...')
'''),
    md('''
Next: [`02_exploration.ipynb`](02_exploration.ipynb) looks at the data.

*Contains data from the Volve field dataset, provided by Equinor ASA and the former Volve
licence partners ExxonMobil Exploration & Production Norway AS and Bayerngas Norge AS, under
the Equinor Open Data Licence.*
'''),
]

NB2 = [
    md('''
# 2 · A first look at the data

A quick exploration: where the wells are, what the three cubes look like around them, the
porosity logs, and how the cube values relate to porosity at the wells.

This is description, not modelling. The pooled correlations at the end are not a
performance estimate (see the validation note in notebook 1).
'''),
    code(SETUP + '''
import matplotlib.pyplot as plt
import viz_style as vs
vs.apply()

amp, vp, pp = v.cube('ps_amplitude'), v.cube('vp'), v.cube('pp_amplitude')
idx, vox, smp = v.wells('index'), v.wells('voxels'), v.wells('samples')
g = v.grid
FIG = '../docs/figures'
os.makedirs(FIG, exist_ok=True)

def short(name):              # '15/9-F-11B' -> 'F-11B', '15/9-19 A' -> '19 A'
    return name.replace('15/9-', '')
'''),
    md('''
## Where the wells are

A depth slice of the PS amplitude at 2950 m below MSL, close to the reservoir. Thin lines are
the full well paths from the surface. Thick lines are the sections with porosity data. The
right panel zooms in on the platform area, where most wells cluster.
'''),
    code('''
z_slice = 2950
iz = int(round((z_slice - g['z0']) / g['dz']))
IL, XL = np.meshgrid(g['ilines'], g['xlines'], indexing='ij')
GX, GY = v.ilxl_to_xy(IL, XL)
sl = np.asarray(amp[iz])
lo, hi = vs.sym_limits(sl)
ZOOM = (434.3, 437.0, 6477.95, 6479.75)          # km: x0, x1, y0, y1

# label placement for the crowded platform area: (anchor, dx, dy) in points
LABEL = {'F-1A': ('end', -30, 12), 'F-1': ('end', 0, 16), 'F-1C': ('end', 14, 10),
         'F-1B': ('end', 24, -2), 'F-11A': ('start', -44, 2), 'F-11T2': ('end', 10, 6),
         'F-15D': ('end', 10, 2), '19 A': ('start', -6, -16), 'F-11B': ('end', 10, -8),
         '19 SR': ('end', 4, -16), 'F-12': ('end', 10, -10)}

fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12.5, 5.6), width_ratios=[1, 1.1],
                               constrained_layout=True)
for ax in (ax0, ax1):
    m = ax.pcolormesh(GX / 1e3, GY / 1e3, sl, cmap='seismic_div', vmin=lo, vmax=hi,
                      shading='auto', rasterized=True)
    for r in idx.itertuples():
        t = v.trajectory(r.npd)
        ax.plot(t.X / 1e3, t.Y / 1e3, color=vs.INK, lw=0.8, alpha=0.6)
        s = smp[smp.npd == r.npd].sort_values('MD')
        ax.plot(s.X / 1e3, s.Y / 1e3, color='white', lw=4.2, solid_capstyle='round')
        ax.plot(s.X / 1e3, s.Y / 1e3, color=vs.INK, lw=2.4, solid_capstyle='round')
        if ax is ax1:
            name = short(r.wellbore)
            where, dx, dy = LABEL[name]
            k = -1 if where == 'end' else 0
            ax.annotate(name, (s.X.iloc[k] / 1e3, s.Y.iloc[k] / 1e3), xytext=(dx, dy),
                        textcoords='offset points', fontsize=8.5, color=vs.INK,
                        ha='left' if dx >= 0 else 'right', va='center',
                        arrowprops=dict(arrowstyle='-', color=vs.INK2, lw=0.6, shrinkA=0, shrinkB=2),
                        bbox=dict(boxstyle='round,pad=0.2', fc=vs.SURFACE, ec='none', alpha=0.9))
    ax.set_aspect('equal')
    ax.set_xlabel('X (km, ED50 / UTM 31N)')
x0, x1, y0, y1 = ZOOM
ax0.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=vs.INK, lw=1, ls='--'))
ax0.set_ylabel('Y (km)')
ax0.set_title(f'PS amplitude at {z_slice} m TVDSS')
ax1.set_xlim(x0, x1)
ax1.set_ylim(y0, y1)
ax1.set_title('Platform area: thick = section with porosity data')
cb = fig.colorbar(m, ax=ax1, shrink=0.8, pad=0.02)
cb.set_label('PS amplitude')
cb.outline.set_visible(False)
fig.savefig(f'{FIG}/map_wells.png')
plt.show()
'''),
    md('''
## The three cubes along one inline

Inline 10214 crosses the F-1 cluster and F-11 T2. The panels show the same section in each
cube, with the well voxels that lie within ±2 inlines.
'''),
    code('''
iy = 229
il_no = g['il0'] + iy
zr = slice(int(2000 / g['dz']), int(3500 / g['dz']) + 1)
depth = np.asarray(g['depths'])[zr]
xls = np.asarray(g['xlines'])
near = vox[(vox.IY - iy).abs() <= 2]

panels = [('PS amplitude', amp, 'seismic_div', True),
          ('Vp (m/s)', vp, 'blue_seq', False),
          ('PP amplitude (depth-converted with Vp)', pp, 'seismic_div', True)]
fig, axes = plt.subplots(3, 1, figsize=(9, 9.2), sharex=True, constrained_layout=True)
for ax, (title, cube, cmap, div) in zip(axes, panels):
    sec = np.asarray(cube[zr, iy, :])
    lim = vs.sym_limits(sec) if div else (np.percentile(sec, 1), np.percentile(sec, 99))
    m = ax.pcolormesh(xls, depth, sec, cmap=cmap, vmin=lim[0], vmax=lim[1],
                      shading='auto', rasterized=True)
    ax.scatter(g['xl0'] + near.IX, g['z0'] + near.IZ * g['dz'], s=7, color=vs.INK,
               edgecolor='white', linewidth=0.4, zorder=3)
    ax.invert_yaxis()
    ax.set_ylabel('TVDSS (m)')
    ax.set_title(title)
    cb = fig.colorbar(m, ax=ax, pad=0.01, aspect=25)
    cb.outline.set_visible(False)
tops = near.groupby('wellbore').agg(IX=('IX', 'median'), IZ=('IZ', 'min')).sort_values('IX')
for k, (name, d) in enumerate(tops.iterrows()):
    right = k % 2 == 1                     # alternate sides so neighbours do not collide
    axes[0].annotate(short(name), (g['xl0'] + d.IX, g['z0'] + d.IZ * g['dz']),
                     xytext=(8 if right else -8, 10), textcoords='offset points', fontsize=8,
                     ha='left' if right else 'right',
                     arrowprops=dict(arrowstyle='-', color=vs.INK2, lw=0.6, shrinkA=0, shrinkB=2),
                     bbox=dict(boxstyle='round,pad=0.15', fc=vs.SURFACE, ec='none', alpha=0.85))
axes[-1].set_xlabel(f'Crossline (inline {il_no})')
fig.savefig(f'{FIG}/section_three_cubes.png')
plt.show()
'''),
    md('''
## Porosity logs

`PHIE` against depth for each well. Light blue points are the original log samples
(0.1–0.15 m step) and black dots are the 5 m voxel means used for training. Horizontal
wells stack many samples at almost the same depth.
'''),
    code('''
ORDER = ['15/9-19 A', '15/9-19 SR', '15/9-F-1', '15/9-F-1A', '15/9-F-1B', '15/9-F-1C',
         '15/9-F-11A', '15/9-F-11B', '15/9-F-11T2', '15/9-F-12', '15/9-F-15D']
order = idx.set_index('wellbore').loc[ORDER, 'npd'].tolist()
fig, axes = plt.subplots(1, len(order), figsize=(13, 4.6), sharey=True, constrained_layout=True)
for ax, npd in zip(axes, order):
    s = smp[smp.npd == npd].sort_values('MD')
    d = vox[vox.npd == npd]
    ax.scatter(s.PHIE, s.TVDSS, s=1, color=vs.BLUE, alpha=0.35, linewidth=0, rasterized=True)
    ax.scatter(d.PHIE, d.TVDSS, s=7, color=vs.INK, zorder=3, linewidth=0)
    ax.set_title(short(d.wellbore.iloc[0]), fontsize=9)
    ax.set_xlim(0, 0.35)
    ax.set_xticks([0, 0.15, 0.3])
    ax.grid(axis='y')
axes[0].invert_yaxis()
axes[0].set_ylabel('TVDSS (m)')
fig.supxlabel('PHIE (fraction)', fontsize=9, color=vs.INK2)
fig.savefig(f'{FIG}/phie_logs.png')
plt.show()
'''),
    code('''
summary = (vox.groupby('wellbore')
              .agg(voxels=('PHIE', 'size'), PHIE_mean=('PHIE', 'mean'), PHIE_std=('PHIE', 'std'),
                   TVDSS_top=('TVDSS', 'min'), TVDSS_base=('TVDSS', 'max'))
              .round(3))
summary
'''),
    md('''
## Velocity with depth

The Vp model across the whole cube (median and 5–95 % range at each depth), compared with
the well voxels.
'''),
    code('''
sub = np.asarray(vp[:, ::4, ::4], dtype=np.float32).reshape(vp.shape[0], -1)
p5, p50, p95 = np.percentile(sub, [5, 50, 95], axis=1)
z = np.asarray(g['depths'])
vw = np.asarray(vp[vox.IZ.values, vox.IY.values, vox.IX.values])

fig, ax = plt.subplots(figsize=(5.2, 6))
ax.fill_betweenx(z, p5, p95, color=vs.BLUE, alpha=0.15, linewidth=0, label='cube, 5–95 %')
ax.plot(p50, z, color=vs.BLUE, label='cube, median')
ax.scatter(vw, vox.TVDSS, s=6, color=vs.INK, linewidth=0, label='well voxels', zorder=3)
ax.invert_yaxis()
ax.set_xlabel('Vp (m/s)')
ax.set_ylabel('TVDSS (m)')
ax.set_title('Migration velocity with depth')
ax.grid(True)
ax.legend(loc='lower left')
fig.savefig(f'{FIG}/vp_depth.png')
plt.show()
'''),
    md('''
## Cube values against porosity

Each dot is a well voxel and all wells are pooled. The pooled correlation mixes
differences between wells with variation inside each well, so the per-well values below
the figure tell more.
'''),
    code('''
feat = pd.DataFrame({'PS amplitude': np.asarray(amp[vox.IZ, vox.IY, vox.IX]),
                     'Vp (m/s)': vw,
                     'PP amplitude': np.asarray(pp[vox.IZ, vox.IY, vox.IX]),
                     'PHIE': vox.PHIE.values, 'well': vox.wellbore.map(short).values})

fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True, constrained_layout=True)
for ax, col in zip(axes, ['PS amplitude', 'Vp (m/s)', 'PP amplitude']):
    r = np.corrcoef(feat[col], feat.PHIE)[0, 1]
    ax.scatter(feat[col], feat.PHIE, s=7, color=vs.BLUE, alpha=0.55, linewidth=0)
    ax.set_xlabel(col)
    ax.set_title(f'{col}   r = {r:+.2f} (pooled)', fontsize=9)
    ax.grid(True)
axes[0].set_ylabel('PHIE (fraction)')
fig.savefig(f'{FIG}/crossplots.png')
plt.show()
'''),
    code('''
per_well = (feat.groupby('well')
                .apply(lambda d: pd.Series({c: np.corrcoef(d[c], d.PHIE)[0, 1]
                                            for c in ['PS amplitude', 'Vp (m/s)', 'PP amplitude']}),
                       include_groups=False)
                .round(2))
per_well['voxels'] = feat.groupby('well').size()
per_well
'''),
    md('''
The per-well correlations change sign from one well to the next. A single cube value at a
point is a weak and unstable predictor of porosity here. That fits the limitations listed in
the README: the PS image is converted-wave, the tie has no synthetic, and there are few
wells. Context windows, several cubes, and well-grouped validation are where to start.

*Contains data from the Volve field dataset, provided by Equinor ASA and the former Volve
licence partners ExxonMobil Exploration & Production Norway AS and Bayerngas Norge AS, under
the Equinor Open Data Licence.*
'''),
]


def build(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata['kernelspec'] = {'name': 'python3', 'display_name': 'Python 3', 'language': 'python'}
    NotebookClient(nb, timeout=600, kernel_name='python3',
                   resources={'metadata': {'path': str(HERE)}}).execute()
    nbf.write(nb, HERE / name)
    print('wrote', name)


if __name__ == '__main__':
    build('01_open_the_dataset.ipynb', NB1)
    build('02_exploration.ipynb', NB2)

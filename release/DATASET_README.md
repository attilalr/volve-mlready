# Volve ML-ready: co-registered seismic cubes and well-tied effective porosity

**Version 1.0.0** · DOI: `10.5281/zenodo.TODO` · Data licence: Equinor Open Data Licence ·
Code licence: MIT

This is an analysis-ready subset of the public **Volve field dataset** (Equinor, North Sea,
block 15/9). Three seismic-derived cubes sit on one common depth grid, and the
effective-porosity logs of 11 wellbores are tied to that grid, sample by sample and
voxel by voxel:

| Cube on the common grid | What it is |
|---|---|
| PS amplitude | ST0202 converted-wave (PS) PSDM full-offset post-stack, imaged in depth |
| Vp | ST10010 2011 TTI migration interval P-velocity, resampled onto the grid |
| PP amplitude | ST0202 PZ CIP gathers (PP, time), stacked and converted to depth with that Vp |

The cubes are **901 × 385 × 605** cells (depth × inline × crossline), 12.5 × 12.5 × 5 m.
They cover 0–4500 m below mean sea level and are referenced to ED50 / UTM zone 31N.

Assembling this from the raw release is the slow part. Logs are indexed by measured depth
only, and the deviation surveys of most production wells exist only in the full 5 TB release,
which today is distributed through Databricks. Each survey is in its own depth reference, and
the seismic comes in different grids and domains. This package removes those steps, and the
code to redo them from the raw files is included.

The data were prepared independently. They are not endorsed by Equinor, the Volve licence
partners, or OSDU. See [DATA_LICENSE.md](DATA_LICENSE.md).

---

## Contents

| File | Content | Size |
|---|---|---|
| `st0202_ps_amplitude_depth.npy` | PS amplitude, float32 (901, 385, 605) | 840 MB |
| `vp_on_st0202_depth.npy` | Interval Vp (m/s) on the same grid, float32 (901, 385, 605) | 840 MB |
| `pp_amplitude_on_st0202_depth.npy` | PP amplitude in depth on the same grid, float32 (901, 385, 605) | 840 MB |
| `grid_st0202_depth.json` | Grid of the three cubes above: inline/crossline/depth axes, affine (il, xl) → (X, Y) | 22 kB |
| `vp_st10010_native_depth.npy` / `.json` | Vp on its native grid (226, 436, 961), 20 m depth step | 379 MB |
| `pp_poststack_st0202_time.npy` / `.json` | PP post-stack on its native grid (193, 303, 1126), two-way time, 4 ms, 25 m bins | 263 MB |
| `wells.zip` | `wells_voxels.csv`, `wells_samples.csv`, `wells_index.csv`, `trajectories/*.csv` | 2.7 MB |
| `source_files.zip` | Unmodified source files used: LAS logs, COMPASS survey exports, OSDU trajectories, checkshots, formation tops, SEG-Y header dump | 14 MB |
| `code.zip` | Snapshot of the GitHub repository: loader, example notebooks, processing pipeline (MIT) | 4 MB |
| `DATA_LICENSE.md`, `Equinor_Open_Data_Licence_Volve.pdf` | Licence, attribution, no-endorsement notice | |
| `CITATION.cff`, `CHANGELOG.md`, `SHA256SUMS.txt` | Citation metadata, version history, checksums | |

Total: about 3.2 GB. Verify the download with `sha256sum -c SHA256SUMS.txt`.

---

## Quick start

Install the small loader (numpy + pandas only) from GitHub, or from `code.zip`:

```bash
pip install git+https://github.com/attilalr/TODO-REPO-NAME
```

```python
import numpy as np
from volve_mlready import VolveMLReady

v   = VolveMLReady('volve-mlready-v1.0.0/')    # folder holding the downloaded files
amp = v.cube('ps_amplitude')                   # memory-mapped, (901, 385, 605)
vp  = v.cube('vp')
pp  = v.cube('pp_amplitude')
vox = v.wells('voxels')                        # training table, one row per (well, voxel)

X_feat = np.stack([amp[vox.IZ, vox.IY, vox.IX],
                   vp [vox.IZ, vox.IY, vox.IX],
                   pp [vox.IZ, vox.IY, vox.IX]], axis=1)
y = vox.PHIE.values                            # effective porosity, fraction
groups = vox.npd.values                        # use for leave-one-well-out CV
```

Example notebooks (opening the data, a first exploration) are in the repository and in
`code.zip` → `notebooks/`. Without the helper you need only `np.load(..., mmap_mode='r')` and `pandas.read_csv`
(the CSVs are inside `wells.zip`).

---

## Grid and coordinate conventions

All three arrays on the common grid are indexed `C[iz, iy, ix]`:

| Index | Meaning | Value |
|---|---|---|
| `iz` | depth below MSL (TVDSS) | `z = 0 + 5·iz` m, 0–4500 m |
| `iy` | inline | `IL = 9985 + iy`, 9985–10369 |
| `ix` | crossline | `XL = 1932 + ix`, 1932–2536 |

- **CRS:** ED50 / UTM zone 31N (EPSG:23031). (il, xl) → (X, Y) is the affine
  `X = a·il + b·xl + c`, `Y = d·il + e·xl + f`. Its coefficients are in
  `grid_st0202_depth.json → affine_ilxl_to_XY`. It was fitted to the trace-header bin
  centres, with an RMS residual of about 0.05 m. Inline azimuth 284°, crossline azimuth 14°,
  bin 12.5 × 12.5 m.
- **Vertical datum:** depth is metres **below mean sea level**. Well depths were converted
  to the same datum (see *Depth datum* below).
- The native Vp grid uses the same inline/crossline numbering (affines agree within 0.3 m).
  The native PP grid is the same grid decimated by 2 (25 m bins).

---

## The cubes

### PS amplitude — `st0202_ps_amplitude_depth.npy`

- Source: `ST0202R08-PS_PSDM_FULL_OFFSET_DEPTH.MIG_FIN.POST_Stack.3D.JS-017534.segy`
  (895,367,300 bytes, SHA-256 `d2c76ac2…e1`). This is the 2002 ST0202 4C OBC survey,
  reprocessed by WesternGeco in 2008. The EBCDIC header reads
  *"FINAL PS PSDM STACK FULL OFFSET IN DEPTH"*.
- **This is converted-wave (P-to-S) data, not P-wave.** The OSDU mirror carries the PS
  depth stack but not the PZ depth stack. Use the PP cube below for P-wave reflectivity.
- Processing here: none. The SEG-Y was read with `segyio` (inline byte 189, crossline byte
  193) and transposed to (z, il, xl). Values are unchanged, with no NaNs. About 1 % of the
  values are exactly zero, mostly in the top 100 m and along the first and last crosslines.

### Vp — `vp_on_st0202_depth.npy`

- Source: `ST10010ZC11_MIG_VEL.MIG_VEL.VELOCITY.3D.JS-017527.segy` (OSDU path
  `st0202/velocities/TTI_model_2011/`). This is the 2011 TTI migration model of the
  2010 ST10010 survey: interval P-velocity in depth, 0–4500 m at 20 m.
- Co-registration: the inline/crossline window of the common grid is cropped out, and each
  column is linearly interpolated from 20 m to 5 m. Range about 1480–5340 m/s (water at 1480 m/s).
- It is a **smooth migration-velocity model**, not a well-calibrated property volume.

### PP amplitude — `pp_amplitude_on_st0202_depth.npy`

- Source: `ST0202R08_PZ_PrSDM_CIP_gathers_in_PP_Time.segy` (20.3 GB, pre-stack CIP gathers,
  PP two-way time, 4 ms, every 2nd inline and crossline). The header states
  "positive = increase in acoustic impedance".
- Step 1 (`pp_poststack_st0202_time.npy`): plain mean of all traces in each bin.
- Step 2: each depth column is converted with `TWT(z) = Σ 2·dz / Vp(z)` using the Vp cube
  above, and the nearest 25 m PP trace is interpolated at those times.
- The time-to-depth relation is the migration velocity, not a well calibration. Expect
  residual misties of the order of a wavelet.

---

## The wells

### Wellbores

| Wellbore | NPD id | Survey | EDF (m) | Max inc. (°) | Samples | Voxels | TVDSS range (m) | Mean PHIE |
|---|---|---|---|---|---|---|---|---|
| 15/9-19 A | NPD-3145 | OSDU | 25.0 | 61 | 1,967 | 68 | 2874–3143 | 0.140 |
| 15/9-F-1C | NPD-7405 | COMPASS | 54.9 | 84 | 8,422 | 136 | 2883–3116 | 0.177 |
| 15/9-F-11A | NPD-7079 | COMPASS | 54.9 | 75 | 1,533 | 36 | 2928–3052 | 0.160 |
| 15/9-F-11B | NPD-7080 | COMPASS | 54.9 | 90 | 13,933 | 207 | 2792–3182 | 0.155 |
| 15/9-F-12 | NPD-5599 | COMPASS | 54.9 | 55 | 2,647 | 77 | 2804–3045 | 0.174 |
| 15/9-19 SR | NPD-2105 | COMPASS | 25.0 | 61 | 6,886 | 217 | 2370–3091 | 0.108 |
| 15/9-F-1 | NPD-7223 | COMPASS | 54.9 | 50 | 2,872 | 65 | 2991–3252 | 0.082 |
| 15/9-F-1A | NPD-7224 | COMPASS | 54.9 | 63 | 2,281 | 46 | 3003–3167 | 0.090 |
| 15/9-F-1B | NPD-7264 | COMPASS | 54.9 | 30 | 2,105 | 47 | 2971–3180 | 0.117 |
| 15/9-F-15D | NPD-7289 | COMPASS | 54.9 | 82 | 11,936 | 160 | 2853–3153 | 0.166 |
| 15/9-F-11T2 | F-11T2 | COMPASS | 54.9 | 82 | 2,017 | 46 | 3125–3321 | 0.110 |
| **Total** | | | | | **56,599** | **1,105** | | |

These are all the Volve wellbores that have a PHIF log and a deviation survey in the
sources used.

### Tables in `wells.zip`

**`wells_voxels.csv`**: the training table, with one row per (well, voxel) and the mean of
the log samples falling in that 12.5 × 12.5 × 5 m cell. Wells are never merged into a voxel.

| Column | Meaning |
|---|---|
| `well` | integer well index (0–10), order as in `wells_index.csv` |
| `npd`, `wellbore` | NPD wellbore id and name |
| `IX`, `IY`, `IZ` | grid indices: crossline, inline, depth (`C[IZ, IY, IX]`) |
| `PHIE` | effective porosity (fraction), mean of the samples in the voxel |
| `PHIE_std`, `n_samples` | standard deviation and number of samples in the voxel (std = 0 if one sample) |
| `MD` | measured depth from the drill floor (m), mean |
| `TVD`, `TVDSS` | true vertical depth from the drill floor, and below MSL (m), mean |
| `EDF` | drill-floor elevation above MSL used for that well (m) |
| `X`, `Y` | ED50 / UTM 31N (m), mean |
| `IL`, `XL` | continuous inline / crossline numbers, mean |

**`wells_samples.csv`**: the same columns, one row per original log sample (0.1–0.15 m
step) inside the cube, without upscaling. Use it for QC or for your own upscaling.

**`wells_index.csv`**: one row per wellbore. It lists the source LAS file, the survey
source and file, the EDF and its evidence, the wellhead coordinates, the maximum
inclination, counts, and depth and index ranges.

**`trajectories/<npd>.csv`**: the deviation survey actually used, in one format: `MD, INC,
AZI, TVD_DF, TVDSS, X, Y` (m and degrees; X/Y in ED50 / UTM 31N).

### Target log

`PHIE` is the **PHIF** curve (effective porosity, v/v) from Equinor's petrophysical
interpretation: `WLC_PETRO_COMPUTED_OUTPUT_1*.LAS` (production wells) and `*_CPI.las`
(15/9-19 SR, 15/9-19 A). It was used as delivered. Samples with null or non-finite PHIF
are dropped. The raw input logs of the same wells (GR, density, neutron, sonic,
resistivity, …) are included in `source_files.zip` → `welllogs/`.

---

## How the wells were tied

1. **Survey per wellbore.** Ten wellbores use the **COMPASS** "SURVEY LIST" exports
   (Landmark) from the full Volve release (`Well_technical_data/…/*_ACTUAL`, and
   `*_Standard_Survey_NPD.txt` for 15/9-19 SR). These exports give absolute UTM
   coordinates and TVD per station. 15/9-19 A uses the **OSDU** trajectory (MD/inclination/
   azimuth plus wellhead latitude/longitude), integrated by minimum curvature. Its COMPASS
   export agrees within 1.4 m laterally and 0.15 m in TVD over the whole well, which
   makes it an independent check.
2. **Positioning.** X, Y and TVD are linearly interpolated at each log MD. Nothing is
   extrapolated beyond the first or last survey station.
3. **Depth datum.** `TVDSS = TVD − EDF`. EDF comes **only from metadata**: the LAS header
   where present, otherwise documented evidence (`wells_index.csv → EDF_source`). The values
   are 54.9 m for the Volve F platform and 25.0 m for the 15/9-19 wells, and they match the
   KB-MSL in the COMPASS headers. Depth was **never** shifted to maximise correlation with
   the target.
4. **Cell assignment.** (X, Y) → (il, xl) through the inverse affine, TVDSS → iz, then the
   nearest cell. Samples outside the cube are dropped.
5. **Upscaling.** The mean is taken per (well, voxel), which gives 56,599 samples → 1,105
   voxels (about 51 samples per voxel, mean within-voxel PHIE std 0.023).

---

## Known limitations

- **No synthetic well tie.** Depth alignment relies on the seismic depth imaging and the
  drill-floor datum. Misties of several voxels are possible, especially for the PS image
  and the velocity-converted PP cube. If your method is sensitive to that, do your own
  well tie: the checkshots are in `source_files.zip`.
- **Nearest-cell mapping.** The lateral error is at most half a bin diagonal (8.8 m) and the
  vertical error at most 2.5 m, on top of the survey uncertainty.
- **Clustered wells.** F-1, F-1A, F-1B and F-1C come from the same slot, and F-11A/B/T2
  share a slot. Several of their reservoir sections lie within a few bins of each other, so
  random or voxel-level splits leak information. **Use leave-one-well-out (grouped) validation**, and check how
  close the wells are to each other.
- **Few wells.** 11 wellbores and 1,105 voxels cover one reservoir interval (about
  2370–3320 m TVDSS). Results do not transfer to the whole cube.
- **Different vintages.** The PS/PP images come from the 2002 survey and Vp from the 2010
  survey.
- Petrophysical logs, surveys and seismic are delivered "as is" by the data owners, and may
  contain errors.

---

## Reproducing from the raw data

`code.zip` (folder `release/`) contains the pipeline that produced this release. Run it from
the repository root:

```bash
conda env create -f environment.yml && conda activate volve-mlready
export VOLVE_DATA=$PWD/release/data/volve
unzip source_files.zip -d $VOLVE_DATA                   # logs, surveys, checkshots, tops
python release/pipeline/download_volve.py --with-velocity --with-gathers   # seismic from OSDU (~21.7 GB)
python release/pipeline/preparar_cubo_volve.py                  # PS SEG-Y -> cube + grid
python release/pipeline/parse_compass_survey.py                 # COMPASS -> trajectories
python release/pipeline/amarre_volve.py                         # well tie + upscaling
python release/pipeline/preparar_velocidade.py                  # Vp native + co-registered
python release/pipeline/preparar_pp_volve.py                    # stack PP gathers (reads 20 GB)
python release/pipeline/preparar_pp_coreg.py                    # PP time -> depth grid
python release/build_release.py --out ./volve-mlready-v1.0.0   # assemble this package
```

The release pipeline was checked against the research outputs: the cubes, Vp and PP are
byte-identical. The well tables differ only in the 15/9-19 A fix listed in the CHANGELOG.

### Where the raw files come from

| Data | Source |
|---|---|
| Seismic SEG-Y, most LAS, OSDU trajectories, checkshots, formation tops | OSDU Open Test Data, public anonymous S3 `s3://osdu-seismic-test-data/volve/` (<https://community.opengroup.org/osdu/data/open-test-data>) |
| COMPASS survey exports; LAS of 15/9-F-11 T2 | Full Volve release, Databricks Marketplace listing by Equinor ASA (see <https://www.equinor.com/energy/volve-data-sharing>). Reading the shared volumes required a Databricks workspace with Unity Catalog (Databricks-to-Databricks sharing). The Free Edition could not read them. |

All of these files are included unmodified in `source_files.zip`, so the pipeline does not
need Databricks access.

---

## Licence and attribution

**Data:** Equinor Open Data Licence. Use is allowed, commercial use included, and so are
sharing and adaptation. **Selling the data is not allowed.** Attribution is required. Full
text, summary and the required attribution statement: [DATA_LICENSE.md](DATA_LICENSE.md).

> Contains data from the Volve field dataset, provided by Equinor ASA and the former Volve
> licence partners ExxonMobil Exploration & Production Norway AS and Bayerngas Norge AS,
> under the Equinor Open Data Licence (https://www.equinor.com/energy/volve-data-sharing).

**Code:** MIT (covers `code.zip` only).

## Citation

Please cite this dataset (see `CITATION.cff` or the Zenodo record) **and** acknowledge the
original Volve data as above.

> TODO-AUTHOR (2026). *Volve ML-ready: co-registered PS/PP seismic and Vp cubes with
> well-tied effective porosity for 11 wellbores* (v1.0.0) [Data set]. Zenodo.
> https://doi.org/10.5281/zenodo.TODO

## Contact

TODO-AUTHOR · TODO-EMAIL · issues: https://github.com/attilalr/TODO-REPO-NAME/issues

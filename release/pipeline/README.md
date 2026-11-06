# Pipeline

Scripts that build the dataset from the raw Volve files. All of them read and write under
`$VOLVE_DATA` (default `<repo>/release/data/volve`). Run them in this order:

| # | Script | Input | Output (under `$VOLVE_DATA`) |
|---|---|---|---|
| 0 | `download_volve.py [--with-velocity] [--with-gathers]` | OSDU public S3 | `seismic/…` SEG-Y (sha256-checked) |
| 1 | `preparar_cubo_volve.py` | PS depth SEG-Y | `prepared/cubo_st0202_depth.npy`, `cubo_st0202_geom.json` |
| 2 | `parse_compass_survey.py` | `dbx_extract/surveys`, `dbx_extract/w19` | `trajectories_pdf/*.csv` |
| 3 | `amarre_volve.py` | `welllogs/`, `trajectories*/`, grid | `prepared/wells_volve.csv`, `wells_volve_samples.csv` |
| 4 | `preparar_velocidade.py` | velocity SEG-Y | `prepared/vel_st10010_depth.npy`, `vel_coreg_st0202.npy` |
| 5 | `preparar_pp_volve.py` | PP gathers SEG-Y (20 GB) | `prepared/pp_poststack_time.npy`, `pp_geom_time.json` |
| 6 | `preparar_pp_coreg.py` | 4 + 5 | `prepared/pp_coreg_st0202.npy` |

Then `python release/build_release.py --out DIR` assembles the flat package. Paths above are
relative to `release/`; run from the repository root as `python release/pipeline/<script>.py`.

`dbx_extract/`, `welllogs/`, `trajectories/`, `checkshots/` and `markers/` come from
`source_files.zip`. Some of these files exist only in the full Volve release on Databricks.

Script names are in Portuguese (*amarre* = well tie, *preparar* = prepare, *velocidade* =
velocity), and so are some inline comments.

# Changelog

## 1.0.0 — first public release

- Three cubes on the ST0202 depth grid (901 × 385 × 605): PS amplitude, Vp, PP amplitude.
  Also Vp and PP post-stack on their native grids.
- 11 wellbores tied to the grid: 56,599 log samples, 1,105 upscaled voxels, target PHIE (PHIF).
- Unified deviation surveys, per-well index, unmodified source files, pipeline and loader.

### Differences from the authors' earlier internal version

- **15/9-19 A depth fix.** The OSDU trajectory was integrated by minimum curvature from 0 at
  the first survey station (MD = TVD = 109 m) instead of from 109 m. That placed the well
  109 m (22 voxels) too shallow. It is now positioned at the correct depth, which agrees
  with the independent COMPASS survey within 0.15 m in TVD. The other ten wellbores are
  unchanged.

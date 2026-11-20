# puglia-wind

Wind flow over the Monti Dauni, the Apennine ridge on the western edge of Puglia, with OpenFOAM. A 24 km square of real terrain, twelve wind directions, and ten years of ERA5 wind combined into a long-term map of mean wind 100 m above the ground, which is hub height for most of the turbines built there.

![Long-term mean wind 100 m above ground](report/figures/mean_wind.png)

The triangles are the 504 wind turbines mapped in OpenStreetMap inside the domain. They are only drawn on the map; the model doesn't use them.

## Results so far (200 m mesh, 576k cells)

| | |
|---|---|
| ERA5 mean at 100 m, 2015 to 2024 | 4.62 m/s (Weibull k 1.73, A 5.19) |
| Most frequent sectors | 240° (21 %), 330° (20 %), 0° (14 %), 210° (13 %) |
| Modelled mean at 100 m, domain | 2.7 to 6.7 m/s |
| Modelled mean at the turbines (264 outside the edge ring) | 5.47 m/s, against 4.55 m/s for the domain |
| Median turbine, percentile of modelled wind | 94 |
| Median turbine, percentile among cells of the same elevation (±25 m) | 80 |

Most of the placement is explained by height alone: the median turbine is also at percentile 93 of elevation. The last row is the part height doesn't explain. At the same elevation the turbines still sit on the windier cells, the exposed crests rather than sheltered ground of the same height.

![Speed-up for wind from 240°](report/figures/speedup_d240.png)

For the most frequent direction the flow speeds up by as much as 1.7 times over the crests and drops below half the inflow speed in the lee valleys.

## Method

- Terrain: Copernicus DEM GLO-30, projected to UTM 33N and cut around 41.38 N, 15.18 E (`scripts/terrain.py`).
- Mesh: one structured block from `blockMesh`, with each point column moved onto the terrain and graded towards the ground (first cell 5 to 7 m). A 3 km ring at the edges blends to flat ground, so the inflow sees level terrain (`scripts/mesh.py`).
- Solver: `simpleFoam`, k-epsilon, Richards and Hoxey inflow profiles (`atmBoundaryLayerInlet*`), rough wall with z0 = 0.1 m. All four sides carry the same inlet/outlet condition, so one mesh serves every direction and only `flowDir` changes (`case/template`).
- Climate: hourly 100 m wind from ERA5 through the Open-Meteo archive API, binned into twelve 30° sectors with a Weibull fit each (`scripts/wind_climate.py`). Each sector's speed-up scales its Weibull distribution; the sectors are then weighted by frequency (`scripts/wind_map.py`).

Two things that cost time:

- With the mesh aligned to UTM, the four directions parallel to a side (0, 90, 180, 270°) never converged. The flux through the parallel sides is close to zero, the inlet/outlet switch flips every iteration, and the cross-stream velocity residual stalls at about 1e-2. Rotating the mesh 15° against UTM fixes it: all twelve directions now converge in 225 to 275 iterations, except 240°, which levels off at about 1e-5 (just above the 1e-5 target for Uz and k) and runs to the 1500-iteration cap.
- The ABL inlet conditions inherit from `inletOutlet` and need an explicit `value` entry, or the case stops at time 0.

## Limits

- 200 m cells are too coarse for single turbine positions; the 50 m mesh (about 14M cells) is the target.
- Neutral stability only, no Coriolis, uniform roughness. Forest and land use (CORINE) would change z0 locally.
- ERA5 is used as the undisturbed inflow, but its 31 km grid already sees a smoothed version of these hills.
- OSM turbine coverage is volunteered and incomplete.

## Run it

```bash
docker build -t puglia-wind:dev docker              # OpenFOAM v2506 + GDAL
scripts/fetch_dem.sh
python3 scripts/terrain.py
python3 scripts/wind_climate.py
mkdir -p case/runs/mesh-200/constant && cp -r case/template/system case/runs/mesh-200/
python3 scripts/mesh.py case/runs/mesh-200 --dx 200 --nz 40
NP=4 scripts/run_sweep.sh case/runs/mesh-200
python3 scripts/wind_map.py case/runs/mesh-200
python3 scripts/turbines.py --mesh case/runs/mesh-200/mesh.json
python3 scripts/turbine_check.py case/runs/mesh-200-climate.npz
python3 report/plot_map.py case/runs/mesh-200-climate.npz --field mean -o report/figures/mean_wind.png
```

The Python and OpenFOAM steps run inside the container. For production runs, `spack/` builds OpenFOAM 2506 from source with GCC (`gnu.yaml`) or AOCC (`zenss.yaml`).

## To do

- [ ] 50 m mesh, full sweep, on an EPYC node
- [ ] Strong scaling of `simpleFoam` over cores, scotch against hierarchical decomposition
- [ ] OpenFOAM built with GCC against AOCC, same case
- [ ] Time and cost for a full twelve-direction sweep
- [ ] Roughness from CORINE land cover
- [ ] Check against a measured series

## Data

- Terrain: produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- Wind: contains modified Copernicus Climate Change Service information (ERA5), retrieved through Open-Meteo (CC BY 4.0).
- Turbines: © OpenStreetMap contributors, ODbL.

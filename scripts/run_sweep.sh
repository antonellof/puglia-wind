#!/usr/bin/env bash
# Solve every wind direction on one mesh and extract the hub-height fields.
#
# Usage: scripts/run_sweep.sh MESHCASE [DIRS]
#   MESHCASE  case directory with constant/polyMesh and mesh.json (scripts/mesh.py)
#   DIRS      directions in degrees (default: the 12 sector centres, 0 to 330)
# Settings: NP (MPI ranks, default 4), MPIRUN (default mpirun), UREF, Z0
# Each run goes to case/runs/<mesh name>-d<dir>, with log.simpleFoam and
# timing.json (wall seconds, iterations, ranks).
set -euo pipefail
cd "$(dirname "$0")/.."
MESH=${1:?usage: run_sweep.sh MESHCASE [DIRS]}
DIRS=${2:-"0 30 60 90 120 150 180 210 240 270 300 330"}
NP=${NP:-4}; MPIRUN=${MPIRUN:-mpirun}; UREF=${UREF:-10}; Z0=${Z0:-0.1}
name=$(basename "$MESH")
for d in $DIRS; do
  run=case/runs/$name-d$d
  python3 scripts/setup_case.py "$run" --mesh "$MESH" --dir "$d" --uref "$UREF" --z0 "$Z0" --procs "$NP" >/dev/null
  ( cd "$run"
    decomposePar > log.decomposePar 2>&1
    t0=$(date +%s.%N)
    $MPIRUN -np "$NP" simpleFoam -parallel > log.simpleFoam 2>&1
    t1=$(date +%s.%N)
    iters=$(grep -c "^Time = " log.simpleFoam)
    conv=$(grep -c "SIMPLE solution converged" log.simpleFoam || true)
    printf '{"wall_s": %.2f, "iterations": %d, "converged": %s, "ranks": %d}\n' \
      "$(python3 -c "print($t1 - $t0)")" "$iters" "$([[ $conv -gt 0 ]] && echo true || echo false)" "$NP" > timing.json
    reconstructPar -latestTime > log.reconstructPar 2>&1
    postProcess -func writeCellCentres -latestTime > log.cellCentres 2>&1
    rm -rf processor* )
  python3 scripts/hub_height.py "$run"
done

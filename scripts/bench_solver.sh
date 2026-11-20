#!/usr/bin/env bash
# Time simpleFoam on a fixed case with whichever OpenFOAM build is loaded, and
# check the answer against a reference run.
#
# Usage: scripts/bench_solver.sh MESHCASE LABEL
#   MESHCASE  mesh from scripts/mesh.py (e.g. case/runs/mesh-200)
#   LABEL     build label stored in the result, e.g. container-gcc, spack-gcc,
#             spack-aocc-znver4
# Settings: NP (ranks, default all cores), DIR (wind direction, default 240),
#   ITERS (fixed iterations, default 200), REF (reference hub_100m.npz to
#   compare with), MPIRUN, SPEC (build description, e.g. `spack find -lv openfoam`)
# Writes results/solver_<label>_<host>_<stamp>.json.
set -euo pipefail
cd "$(dirname "$0")/.."
MESH=${1:?usage: bench_solver.sh MESHCASE LABEL}; LABEL=${2:?label}
NP=${NP:-$(nproc --all)}; DIR=${DIR:-240}; ITERS=${ITERS:-200}; MPIRUN=${MPIRUN:-mpirun}
run=case/runs/bench-$LABEL
python3 scripts/setup_case.py "$run" --mesh "$MESH" --dir "$DIR" --procs "$NP" >/dev/null
# Fixed work: no early stop on residuals, write only at the end.
sed -i -e "s/^endTime .*/endTime         $ITERS;/" -e "s/^writeInterval .*/writeInterval   $ITERS;/" "$run/system/controlDict"
sed -i -e '/residualControl/d' "$run/system/fvSolution"

cd "$run"
decomposePar > log.decomposePar 2>&1
t0=$(date +%s.%N)
$MPIRUN -np "$NP" simpleFoam -parallel > log.simpleFoam 2>&1
t1=$(date +%s.%N)
reconstructPar -latestTime > log.reconstructPar 2>&1
postProcess -func writeCellCentres -latestTime > log.cellCentres 2>&1
rm -rf processor*
cd - >/dev/null
python3 scripts/hub_height.py "$run" >/dev/null

python3 - "$run" "$LABEL" "$NP" "$ITERS" "$t0" "$t1" "${REF:-}" "${SPEC:-}" <<'EOF'
import json, os, platform, re, subprocess, sys, time
import numpy as np
run, label, np_, iters, t0, t1, ref, spec = sys.argv[1:]
log = open(os.path.join(run, "log.simpleFoam")).read()
ex = [float(x) for x in re.findall(r"ExecutionTime = ([0-9.]+) s", log)]
sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
lscpu = dict(l.split(":", 1) for l in sh("lscpu").splitlines() if ":" in l)
res = dict(
    benchmark="simpleFoam", label=label, case=os.path.basename(run), ranks=int(np_), iterations=int(iters),
    wall_s=float(t1) - float(t0),
    s_per_iter_steady=(ex[-1] - ex[len(ex) // 4]) / (len(ex) - 1 - len(ex) // 4) if len(ex) > 8 else None,
    system=dict(cpu=lscpu.get("Model name", "").strip(), cores=os.cpu_count(), arch=platform.machine(),
                kernel=platform.release()),
    build=dict(spec=spec, foam=sh("foamVersion -full 2>/dev/null || echo $WM_PROJECT_VERSION"),
               compiler=os.environ.get("WM_COMPILER", ""), cxx=sh("mpicxx --version 2>/dev/null | head -1")),
    time=time.strftime("%Y%m%d-%H%M%S"))
if ref:
    a = np.load(os.path.join(run, "hub_100m.npz"))["speed"]
    b = np.load(ref)["speed"]
    res["check"] = dict(ref=ref, max_abs_diff_ms=float(np.abs(a - b).max()),
                        rms_diff_ms=float(np.sqrt(((a - b) ** 2).mean())))
os.makedirs("results", exist_ok=True)
out = f"results/solver_{label}_{platform.node()}_{res['time']}.json"
json.dump(res, open(out, "w"), indent=1)
print(f"{out}: {res['wall_s']:.1f} s for {iters} iterations on {np_} ranks"
      + (f", {res['s_per_iter_steady']:.3f} s/iter" if res["s_per_iter_steady"] else "")
      + (f", max |dU| vs ref {res['check']['max_abs_diff_ms']:.2e} m/s" if ref else ""))
EOF

#!/usr/bin/env bash
# Node baseline before the CFD runs: memory bandwidth (STREAM) and dense FP
# with the toolchain's BLAS (HPL), for one Spack environment.
#
# simpleFoam is limited by memory bandwidth, not FLOPs, so STREAM triad is the
# number that bounds how fast the wind sweep can go and where its scaling over
# cores flattens. HPL checks the compiler + BLAS + MPI stack end to end.
#
# Usage: scripts/node_baseline.sh ENV TOOLCHAIN
#   ENV        Spack environment (built from spack/gnu.yaml, zenss.yaml or oneapi.yaml)
#   TOOLCHAIN  label: gnu, zenss or oneapi
# Settings: HPL_N (default 20000), HPL_NB (default 256), NP (MPI ranks, default
#   all cores), STREAM_N (array length, default 80M), MPIRUN
# Writes results/baseline_<toolchain>_<host>_<stamp>.json.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV=${1:?usage: node_baseline.sh ENV TOOLCHAIN}; TC=${2:?toolchain}
NP=${NP:-$(nproc --all)}; HPL_N=${HPL_N:-20000}; HPL_NB=${HPL_NB:-256}; MPIRUN=${MPIRUN:-mpirun}
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

stream=$(spack -e "$ENV" location -i stream)/bin/stream_c.exe
hpl=$(spack -e "$ENV" location -i hpl)/bin/xhpl
eval "$(spack -e "$ENV" load --sh hpl)"

# STREAM: one thread per core, spread.
OMP_NUM_THREADS=$NP OMP_PROC_BIND=spread OMP_PLACES=cores "$stream" > "$work/stream.txt"

# HPL: P x Q close to square with P <= Q.
P=$(python3 -c "import math; n=$NP; print(max(p for p in range(1, int(math.isqrt(n))+1) if n % p == 0))")
Q=$((NP / P))
cat > "$work/HPL.dat" <<EOF
HPLinpack benchmark input file
puglia-wind node baseline
HPL.out      output file name (if any)
6            device out (6=stdout,7=stderr,file)
1            # of problems sizes (N)
$HPL_N       Ns
1            # of NBs
$HPL_NB      NBs
0            PMAP process mapping (0=Row-,1=Column-major)
1            # of process grids (P x Q)
$P           Ps
$Q           Qs
16.0         threshold
1            # of panel fact
2            PFACTs (0=left, 1=Crout, 2=Right)
1            # of recursive stopping criterium
4            NBMINs (>= 1)
1            # of panels in recursion
2            NDIVs
1            # of recursive panel fact.
1            RFACTs (0=left, 1=Crout, 2=Right)
1            # of broadcast
1            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)
1            # of lookahead depth
1            DEPTHs (>=0)
2            SWAP (0=bin-exch,1=long,2=mix)
64           swapping threshold
0            L1 in (0=transposed,1=no-transposed) form
0            U  in (0=transposed,1=no-transposed) form
1            Equilibration (0=no,1=yes)
8            memory alignment in double (> 0)
EOF
( cd "$work" && OMP_NUM_THREADS=1 $MPIRUN -np "$NP" "$hpl" > hpl.txt 2>&1 )

python3 - "$work" "$TC" "$ENV" "$NP" <<'PY'
import json, os, platform, re, subprocess, sys, time
work, tc, env, np_ = sys.argv[1:]
st = open(os.path.join(work, "stream.txt")).read()
hp = open(os.path.join(work, "hpl.txt")).read()
rate = lambda k: float(re.search(rf"^{k}:\s+([0-9.]+)", st, re.M).group(1))
wr = re.search(r"^W\S+\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+([0-9.eE+]+)", hp, re.M)
sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
lscpu = dict(l.split(":", 1) for l in sh("lscpu").splitlines() if ":" in l)
spec = sh(f"spack -e {env} find --format '{{name}}@{{version}} %{{compiler}}' stream hpl blas mpi 2>/dev/null")
res = dict(toolchain=tc, env=env, ranks=int(np_), time=time.strftime("%Y%m%d-%H%M%S"),
           stream_mb_s={k: rate(k) for k in ("Copy", "Scale", "Add", "Triad")},
           hpl=dict(n=int(wr.group(1)), nb=int(wr.group(2)), p=int(wr.group(3)), q=int(wr.group(4)),
                    seconds=float(wr.group(5)), gflops=float(wr.group(6)),
                    residual_passed="PASSED" in hp) if wr else None,
           system=dict(cpu=lscpu.get("Model name", "").strip(), arch=platform.machine(), cores=os.cpu_count()),
           build=spec.splitlines())
os.makedirs("results", exist_ok=True)
out = f"results/baseline_{tc}_{platform.node()}_{res['time']}.json"
json.dump(res, open(out, "w"), indent=1)
h = res["hpl"]
print(f"{out}: STREAM triad {res['stream_mb_s']['Triad'] / 1000:.1f} GB/s"
      + (f", HPL {h['gflops']:.1f} GFLOP/s, residual {'passed' if h['residual_passed'] else 'FAILED'}" if h else ", HPL output not parsed"))
PY

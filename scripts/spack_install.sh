#!/usr/bin/env bash
# Install one toolchain environment from spack/ and check that OpenFOAM
# really built.
#
# Usage: scripts/spack_install.sh gnu|zenss|oneapi [JOBS]
#
# Two traps this works around:
#  - Spack 1.x hands builds a make jobserver over a named pipe
#    (--jobserver-auth=fifo:...). GNU make older than 4.4 can't read it and
#    stops with "invalid --jobserver-auth string". The OpenFOAM package uses
#    whatever make is on PATH (it doesn't depend on gmake), so on a distro
#    with make 4.3 (Ubuntu 24.04) every wmake call fails.
#  - OpenFOAM's Allwmake then prints "ignoring possible compilation errors"
#    and exits 0, so Spack reports a successful install with no solvers in it.
# The script builds gmake 4.4 first, puts it on PATH, and fails if simpleFoam
# is missing afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."
TC=${1:?usage: spack_install.sh gnu|zenss|oneapi [JOBS]}; JOBS=${2:-$(nproc --all)}
ENV=pw-$TC

if ! make --version | head -1 | awk '{split($3, v, "."); exit !(v[1] > 4 || (v[1] == 4 && v[2] >= 4))}'; then
  spack -c packages:gmake:buildable:true install -j "$JOBS" gmake@4.4.1 >/dev/null
  PATH=$(spack -c packages:gmake:buildable:true location -i gmake@4.4.1)/bin:$PATH
  export PATH
fi
echo "make: $(make --version | head -1)"

spack env list | grep -qw "$ENV" || spack env create "$ENV" "spack/$TC.yaml" >/dev/null
spack -e "$ENV" concretize -f >/dev/null
spack -e "$ENV" install -j "$JOBS"

if spack -e "$ENV" find openfoam >/dev/null 2>&1; then
  prefix=$(spack -e "$ENV" location -i openfoam)
  solver=$(find "$prefix/platforms" -name simpleFoam -type f | head -1)
  [[ -n $solver ]] || { echo "OpenFOAM installed without simpleFoam; see $prefix/log.*-spack (gzip)" >&2; exit 1; }
  echo "simpleFoam: $solver"
fi

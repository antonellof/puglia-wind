#!/usr/bin/env bash
# Download Copernicus DEM GLO-30 tiles (public AWS open data, no account).
# Default tiles cover the Monti Dauni, the Tavoliere and the Gargano.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/dem
for t in ${TILES:-N41_00_E014_00 N41_00_E015_00 N41_00_E016_00 N42_00_E015_00 N42_00_E016_00}; do
  n=Copernicus_DSM_COG_10_${t}_DEM
  if [[ -f data/dem/$n.tif ]] || curl -sf -o data/dem/$n.tif "https://copernicus-dem-30m.s3.amazonaws.com/$n/$n.tif"; then
    echo "data/dem/$n.tif"
  else
    echo "$t: no tile (open sea), skipped"   # GLO-30 has no all-water tiles
  fi
done

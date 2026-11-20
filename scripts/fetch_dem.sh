#!/usr/bin/env bash
# Download Copernicus DEM GLO-30 tiles (public AWS open data, no account).
# Default tiles cover the Monti Dauni and the Tavoliere: N41 E014 and N41 E015.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/dem
for t in ${TILES:-N41_00_E014_00 N41_00_E015_00}; do
  n=Copernicus_DSM_COG_10_${t}_DEM
  [[ -f data/dem/$n.tif ]] || curl -sf -o data/dem/$n.tif "https://copernicus-dem-30m.s3.amazonaws.com/$n/$n.tif"
  echo "data/dem/$n.tif"
done

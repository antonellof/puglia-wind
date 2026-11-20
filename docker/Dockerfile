# Local development image: OpenFOAM v2506 plus GDAL and numpy for terrain work.
# Production runs on EPYC build OpenFOAM from source (see spack/).
FROM opencfd/openfoam-dev:2506
RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      gdal-bin python3-gdal python3-numpy python3-matplotlib python3-scipy python3-pandas \
    && rm -rf /var/lib/apt/lists/*

#!/bin/bash
# ============================================================
# LONI QB2 environment setup for PeleLMeX
# Usage: source setup_env_loni.sh
# ============================================================

module purge
module load gcc/13.2.0
module load mpich/4.1.2/intel-2021.5.0
module load cmake/3.27.7/intel-2021.5.0

# Override Intel MPI wrappers to use GCC
export MPICH_CXX=g++
export MPICH_CC=gcc
export MPICH_F90=gfortran

# Explicit compiler exports for build systems
export CC=gcc
export CXX=g++
export FC=gfortran

# Verify
echo "============================================"
echo " PeleLMeX environment loaded on LONI QB2"
echo "============================================"
echo "  GCC:    $(gcc --version | head -1)"
echo "  MPI:    $(mpicxx --version | head -1)"
echo "  CMake:  $(cmake --version | head -1)"
echo "  mpicxx wraps: $(mpicxx -show 2>&1 | awk '{print $1}')"
echo "============================================"

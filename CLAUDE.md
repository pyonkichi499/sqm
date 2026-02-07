# CLAUDE.md - SQM Project Instructions

## Project Overview

Complex Langevin simulation for the Bose-Hubbard model on a 3D lattice. Hybrid Fortran + Python architecture where Fortran handles the numerical simulation kernel and Python handles orchestration, analysis, and visualization.

The simulation computes spatial correlation functions $\langle a_0 a_i^* \rangle$ using the Complex Langevin method to circumvent the sign problem that arises at finite chemical potential.

## Key Architecture

- **Fortran**: Numerical simulation kernel (RK2 solver, Complex Langevin dynamics, Box-Muller noise generation, binary I/O)
- **Python**: Parameter sweep orchestration, Fortran binary data I/O, statistical analysis (Jackknife, autocorrelation), visualization, CLI interface, configuration management

### Data Flow

```
CLI (cli.py) / calc_bh.py
  -> wparams.py          (writes params.dat in Fortran NAMELIST format)
  -> ./a.out params.dat  (runs Fortran simulation, produces *.dat binary)
  -> read_dat_mod.py     (reads Fortran unformatted binary, computes correlations)
  -> autocorrelation.py  (statistical analysis: thermalization, effective samples)
  -> matplotlib plot     (saves figures/*.png)
```

### Fortran Binary Format

The Fortran simulation writes unformatted sequential files:
- **Header record**: `[reclen(4)] [Nx(i4)] [U(f8)] [mu(f8)] [Ntau(i4)] [reclen(4)]` = 32 bytes
- **Body records**: `[reclen(4)] [a(Nx*c16)] [a_ast(Nx*c16)] [reclen(4)]` per sample

Python reads these via `numpy.fromfile()` with structured dtypes that include the Fortran record markers (`head`/`tail` fields).

## Build & Test Commands

```bash
make                          # Compile Fortran code (optimized)
make a_debug.out              # Compile with debug flags (-g -fcheck=all -fbacktrace)
make test                     # Run all tests (Fortran + Python)
make test-fortran             # Run Fortran tests only
make test-python              # Run Python tests only (rye run pytest tests/ -v)
make lint                     # Lint Python code (rye run ruff check .)
make format                   # Format Python code (rye run ruff format .)
make type-check               # Type check Python code (rye run mypy .)
make clean                    # Remove build artifacts and caches
rye run pytest tests/ -v      # Run Python tests with verbose output
rye run pytest tests/ -v --cov=src/sqm  # Run with coverage
```

## Code Conventions

### Python
- 4 spaces for indentation
- Type hints required on all function signatures
- f-strings for string formatting
- Line length: 100 characters (configured in pyproject.toml `[tool.ruff]`)
- Use `from __future__ import annotations` for forward references
- Use `Path` from `pathlib` instead of string paths
- Logging via `logging.getLogger(__name__)`

### Fortran
- Fortran 2018 standard (`-std=f2018`)
- Use `iso_fortran_env` for portable types (`real64`, `int32`)
- Use `ieee_arithmetic` for NaN/Inf detection
- `implicit none` in all scopes
- NAMELIST for parameter file I/O

### Testing
- Test names in Japanese: `test_{descriptive scenario in Japanese}`
  - Example: `test_空のファイルは例外を送出する()`
  - Example: `test_ヘッダーのNxが正しく読み込まれる()`
- TDD: Red-Green-Refactor cycle
- All tests have a fixed random seed (`np.random.seed(42)` via conftest.py autouse fixture)
- Fortran tests use a custom assertion framework (`assert_eq_int`, `assert_near`, etc.)

## Key Files

### Python (src/sqm/)
- `cli.py` - Click CLI entry point with `sweep` and `config` command groups
- `config.py` - Configuration management with nested dataclasses (`Config`, `SimulationConfig`, `PathConfig`, `SweepConfig`, `SeedConfig`) and YAML/JSON serialization
- `read_dat_mod.py` - Fortran binary I/O (`read_dat`), Jackknife analysis (`jackknife`), correlation computation (`compute_correlation`), plotting (`plot_correlation`), and legacy wrapper (`readfile`)
- `autocorrelation.py` - Statistical analysis tools: FFT-based autocorrelation, integrated autocorrelation time (Sokal window), effective sample size, thermalization detection (Geweke-inspired), data thinning, corrected error estimation
- `calc_bh.py` - Simulation orchestration with `ProcessPoolExecutor` for parallel parameter sweeps
- `wparams.py` - Generates Fortran NAMELIST parameter files (`&params` and `&sampling_setting`)
- `experiment_log.py` - Structured experiment logging with Git info capture, environment metadata, JSON persistence, and warning generation

### Fortran (fortran/)
- `functions_module.f90` - Core physics module:
  - Lattice setup: `make_pos_arrays()`, `set_nn()` (nearest-neighbor table for 3D periodic lattice)
  - Drift terms: `da()`, `da_ast()` (derivatives of the Bose-Hubbard action)
  - RK2 solver: `do_langevin_loop_RK()` (Heun method with NaN/Inf detection)
  - Noise: `set_dw()` (Box-Muller complex Gaussian noise)
  - I/O: `write_header()`, `write_body()`
  - Lattice parameters: `Ntau=6`, `Nx=Ny=Nz=6`, `Dx=216`
- `complex_Langevin_BH.f90` - Main program: reads NAMELIST parameters, runs sampling loop, writes binary output
- `test_functions.f90` - Fortran unit tests (11 test subroutines)

### Configuration
- `pyproject.toml` - Rye project config, Ruff linting rules, mypy settings, pytest markers
- `Makefile` - Build and test automation

## Important Notes

- Fortran uses unformatted (binary) I/O with record markers. The Python reader must account for the 4-byte record length markers that gfortran writes before and after each record.
- The simulation parameters `dtau`, `ds`, `s_end` are passed as Fortran double-precision literal strings (e.g., `"0.3d0"`, `"0.3d-5"`) because they are written directly into NAMELIST files read by Fortran.
- Parallel execution via `ProcessPoolExecutor` in `calc_bh.py` means each worker process gets independent random seeds (system entropy via `call random_seed()`).
- The `SeedConfig` supports three modes: `"system"` (OS entropy), `"fixed"` (deterministic), and `"hybrid"` (base_seed + process_id).

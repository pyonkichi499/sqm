FC = gfortran
FFLAGS = -O2 -Wall -Wextra -std=f2018
FFLAGS_DEBUG = -g -fcheck=all -fbacktrace -Wall -Wextra -std=f2018
FFLAGS_LINT = -Wall -Wextra -Wpedantic -Wconversion -Wimplicit-interface -Wimplicit-procedure -std=f2018

MODULE_SRC = fortran/functions_module.f90
MAIN_SRC = fortran/complex_Langevin_BH.f90
TEST_SRC = fortran/test_functions.f90

.PHONY: all test test-fortran test-python lint lint-python lint-fortran type-check format format-check ci clean

all: a.out

a.out: $(MODULE_SRC) $(MAIN_SRC)
	$(FC) $(FFLAGS) -o $@ $(MODULE_SRC) $(MAIN_SRC)

a_debug.out: $(MODULE_SRC) $(MAIN_SRC)
	$(FC) $(FFLAGS_DEBUG) -o $@ $(MODULE_SRC) $(MAIN_SRC)

test_functions: $(MODULE_SRC) $(TEST_SRC)
	$(FC) $(FFLAGS) -o $@ $(MODULE_SRC) $(TEST_SRC)

test: test-fortran test-python

test-fortran: test_functions
	./test_functions

test-python:
	rye run pytest tests/ -v

lint: lint-python lint-fortran

lint-python:
	rye run ruff check .

lint-fortran:
	$(FC) $(FFLAGS_LINT) -fsyntax-only $(MODULE_SRC) $(MAIN_SRC)

format:
	rye run ruff format .

format-check:
	rye run ruff format --check .

type-check:
	rye run mypy src/sqm/

ci: test lint format-check type-check

clean:
	rm -f a.out a_debug.out test_functions *.o *.mod
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -f *.dat experiment_*.json
	rm -rf output/ figures/

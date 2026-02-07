FC = gfortran
FFLAGS = -O2 -Wall -Wextra -std=f2018
FFLAGS_DEBUG = -g -fcheck=all -fbacktrace -Wall -Wextra -std=f2018

MODULE_SRC = fortran/functions_module.f90
MAIN_SRC = fortran/complex_Langevin_BH.f90
TEST_SRC = fortran/test_functions.f90

.PHONY: all test test-fortran test-python lint type-check format clean

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

lint:
	rye run ruff check .

format:
	rye run ruff format .

type-check:
	rye run mypy .

clean:
	rm -f a.out a_debug.out test_functions *.o *.mod
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache

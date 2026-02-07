FC = gfortran
FFLAGS =
MODULE = functions_module.f90
MAIN = complex_Langevin_BH.f90
TEST = test_functions.f90

.PHONY: build test run clean

build: a.out

a.out: $(MODULE) $(MAIN)
	$(FC) $(FFLAGS) $^ -o $@

test: run_tests
	./run_tests

run_tests: $(MODULE) $(TEST)
	$(FC) $(FFLAGS) $^ -o $@

run: a.out
	python calc_bh.py

clean:
	rm -f a.out run_tests *.mod *.dat

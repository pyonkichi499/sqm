FC = gfortran
FFLAGS = -O2
MODULE = functions_module.f90
MAIN = complex_Langevin_BH.f90
TEST = test_functions.f90
OUTDIR = output

.PHONY: build test run clean cleanall

build: a.out

a.out: $(MODULE) $(MAIN)
	$(FC) $(FFLAGS) $^ -o $@

test: run_tests
	./run_tests

run_tests: $(MODULE) $(TEST)
	$(FC) $(FFLAGS) $^ -o $@

run: a.out | $(OUTDIR)
	python calc_bh.py

$(OUTDIR):
	mkdir -p $(OUTDIR)

clean:
	rm -f a.out run_tests *.mod

cleanall: clean
	rm -rf $(OUTDIR)

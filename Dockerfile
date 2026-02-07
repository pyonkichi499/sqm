# ---- Stage 1: test ----
FROM python:3.12-slim AS test

RUN apt-get update && \
    apt-get install -y --no-install-recommends gfortran make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir numpy matplotlib seaborn pytest

COPY functions_module.f90 complex_Langevin_BH.f90 Makefile ./
RUN make build

COPY wparams.py read_dat_mod.py simulate.py sweep.py collect.py ./
COPY tests/ tests/

RUN python -m pytest tests/ -v

# ---- Stage 2: production ----
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gfortran make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir numpy matplotlib seaborn

COPY --from=test /app/a.out ./
COPY wparams.py read_dat_mod.py simulate.py sweep.py collect.py ./

VOLUME /app/output

CMD ["python", "simulate.py"]

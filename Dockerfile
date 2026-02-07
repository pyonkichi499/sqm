FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gfortran make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir numpy matplotlib seaborn

COPY functions_module.f90 complex_Langevin_BH.f90 Makefile ./
RUN make build

COPY simulate.py sweep.py collect.py wparams.py read_dat_mod.py ./

VOLUME /app/output

CMD ["python", "simulate.py"]

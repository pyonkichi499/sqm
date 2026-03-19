# ---- Stage 1: build & test ----
FROM python:3.12-slim AS test

RUN apt-get update && \
    apt-get install -y --no-install-recommends gfortran make && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (production + dev) using lock file
COPY pyproject.toml requirements-dev.lock ./
RUN sed '/-e file:\./d' requirements-dev.lock > /tmp/requirements-dev.txt && \
    pip install --no-cache-dir -r /tmp/requirements-dev.txt && \
    rm /tmp/requirements-dev.txt

# Compile Fortran sources
COPY fortran/ fortran/
COPY Makefile ./
RUN make all && make test_functions

# Install the sqm package in editable mode
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Copy tests
COPY tests/ tests/

# Run all tests (Fortran unit tests + Python pytest)
RUN make test-fortran && python -m pytest tests/ -v

# ---- Stage 2: production ----
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gfortran && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install production-only dependencies using lock file
COPY pyproject.toml requirements.lock ./
RUN sed '/-e file:\./d' requirements.lock > /tmp/requirements.txt && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy compiled Fortran binary from test stage
COPY --from=test /app/a.out ./

# Install the sqm package
COPY src/ src/
RUN pip install --no-cache-dir .

VOLUME /app/output

ENTRYPOINT ["sqm"]

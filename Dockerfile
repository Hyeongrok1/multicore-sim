# Build/run on Linux x86-64 (use --platform linux/amd64 on Apple Silicon).
FROM ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0
USER root
ARG BUILD_JOBS=4
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git g++-multilib python3-venv \
    && rm -rf /var/lib/apt/lists/*
ARG MCPAT_REF=74d4759f3ba2dff8f5a69e07a68efdb46b42fb8c
ARG HOTSPOT_REF=f18831e48cef5d62580585cca0d7fab6c71bc3cc
RUN git clone https://github.com/HewlettPackard/mcpat.git /opt/mcpat \
    && git -C /opt/mcpat checkout "$MCPAT_REF" \
    && make -C /opt/mcpat -j"$BUILD_JOBS"
RUN git clone https://github.com/uvahotspot/HotSpot.git /opt/HotSpot \
    && git -C /opt/HotSpot checkout "$HOTSPOT_REF" \
    && make -C /opt/HotSpot -j"$BUILD_JOBS" hotspot
RUN git clone --depth 1 --branch v26.0.0.0 https://github.com/gem5/gem5.git /opt/gem5
WORKDIR /opt/gem5
RUN scons build/X86/gem5.opt -j"$BUILD_JOBS"
COPY requirements.txt /opt/problem1/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /opt/problem1/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/opt/problem1"
COPY problem1 /opt/problem1/problem1
COPY tests /opt/problem1/tests
COPY smoke.py gem5_smoke.py smoke.S /opt/problem1/
WORKDIR /opt/problem1
RUN python3 -m unittest discover -v
WORKDIR /output
# Building or starting this image does not start the 20 benchmark experiments.
CMD ["python3", "-m", "problem1.run", "plan"]

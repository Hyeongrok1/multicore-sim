FROM ghcr.io/gem5/ubuntu-24.04_all-dependencies:v26-0

USER root
ARG BUILD_JOBS=4
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git g++-multilib \
    && rm -rf /var/lib/apt/lists/*

ARG MCPAT_REF=master
ARG HOTSPOT_REF=master
RUN git clone https://github.com/HewlettPackard/mcpat.git /opt/mcpat \
    && git -C /opt/mcpat checkout "$MCPAT_REF" \
    && make -C /opt/mcpat -j"$BUILD_JOBS"
RUN git clone https://github.com/uvahotspot/HotSpot.git /opt/HotSpot \
    && git -C /opt/HotSpot checkout "$HOTSPOT_REF" \
    && make -C /opt/HotSpot -j"$BUILD_JOBS" hotspot

RUN git clone --depth 1 --branch v26.0.0.0 https://github.com/gem5/gem5.git /opt/gem5
WORKDIR /opt/gem5
RUN scons build/X86/gem5.opt -j"$BUILD_JOBS"

COPY smoke.py gem5_smoke.py smoke.S /opt/problem1/
WORKDIR /output
CMD ["python3", "/opt/problem1/smoke.py"]

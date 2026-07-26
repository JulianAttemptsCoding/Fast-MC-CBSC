ARG PYTORCH_IMAGE=pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime
FROM ${PYTORCH_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/cbsc-zdc
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-build-isolation '.[root,eval,cloud]'

ENTRYPOINT ["python", "-m", "cbsc_zdc.cloud.vertex_stage"]

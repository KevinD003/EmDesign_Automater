# STITCHIQ backend — FastAPI + the digitizing engine (CTO B1).
#
# python:3.11-slim, NOT a newer tag: the stream-lock hashes and SSIM visual
# baselines are float-sensitive instruments captured on 3.11 (see
# .github/workflows/ci.yml, which pins the same). Changing this line changes
# stitch output.
FROM python:3.11-slim AS base

# rlPyCairo (the Part 25 SVG rasterizer) builds pycairo from source and needs
# the cairo headers; libGL/libglib are OpenCV's runtime deps. Build-only
# packages are dropped in the same layer so they never reach the image.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt requirements-features.txt ./
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libcairo2-dev pkg-config \
      libgl1 libglib2.0-0 \
 && pip install --no-cache-dir -r requirements.txt -r requirements-features.txt \
 && apt-get purge -y build-essential libcairo2-dev pkg-config \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# Application code last: dependency layers stay cached across code changes.
COPY app ./app
COPY scripts ./scripts
COPY fonts ./fonts

# rembg downloads its ~170MB U2-Net weights on first use. Baking them in keeps
# the first digitize of a fresh container from paying that (and from needing
# egress at request time). Best-effort: a build behind a strict egress policy
# still produces a working image, it just warms the cache at runtime instead.
ENV U2NET_HOME=/opt/u2net
RUN mkdir -p $U2NET_HOME && \
    python -c "import rembg, numpy as np; rembg.remove(np.zeros((8,8,3), 'uint8'))" \
    || echo "u2net warm-up skipped (no egress at build time) — will fetch on first use"

# Non-root: the container writes only to the designs dir, which is a volume.
RUN useradd --system --uid 10001 stitchiq \
 && mkdir -p /data/designs && chown -R stitchiq /data /opt/u2net
USER stitchiq
ENV STITCHIQ_DESIGNS_DIR=/data/designs \
    STITCHIQ_USER_STORE=/data/local_users.json

EXPOSE 8000

# /health is a real check (see app/main.py): it reports uptime and the python
# version, and answering it at all proves the event loop is not wedged — which
# is exactly what B1 is about.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# uvicorn workers under gunicorn: PROCESSES, not threads. The measured X1
# stall (1,198ms of frozen loop during one digitize) is GIL contention, so
# more threads cannot fix it — only more interpreters can. WEB_CONCURRENCY is
# read by gunicorn; set it to (2 x cores) + 1 on the host.
ENV WEB_CONCURRENCY=4
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "180", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]

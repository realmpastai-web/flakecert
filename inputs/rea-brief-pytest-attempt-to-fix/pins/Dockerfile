# python:3.11-slim-bookworm index digest, resolved from registry-1.docker.io on 2026-10-18
FROM python@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-deps --require-hashes -r /tmp/requirements.lock
WORKDIR /work

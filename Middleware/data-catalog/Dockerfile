FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
# Non-root: a catalog service has no reason to run as root.
RUN useradd --create-home --uid 10001 akg
USER akg
EXPOSE 9001
CMD ["uvicorn", "data_catalog.app:app", "--host", "0.0.0.0", "--port", "9001"]

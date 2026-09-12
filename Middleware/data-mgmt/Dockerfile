FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY Libraries/python/akg-service-core /libs/akg-service-core
COPY Middleware/data-mgmt/pyproject.toml ./
COPY Middleware/data-mgmt/src ./src
RUN pip install --no-cache-dir /libs/akg-service-core && pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 akg
USER akg
EXPOSE 8002
CMD ["uvicorn", "data_mgmt.app:app", "--host", "0.0.0.0", "--port", "8002"]

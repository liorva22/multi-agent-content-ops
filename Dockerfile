FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY contentops ./contentops
RUN pip install --no-cache-dir .
COPY config.yaml ./
COPY examples ./examples
ENV CONTENTOPS_CONFIG=/app/config.yaml
EXPOSE 8000
CMD ["uvicorn", "contentops.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

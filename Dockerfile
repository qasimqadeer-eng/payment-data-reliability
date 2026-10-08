FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY dbt ./dbt
RUN pip install --no-cache-dir -e '.[warehouse]' && useradd --create-home appuser && mkdir -p /app/reports && chown -R appuser:appuser /app
USER appuser
CMD ["python", "-m", "payment_reliability.cli", "--help"]

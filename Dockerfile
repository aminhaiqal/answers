FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev && useradd --create-home axelyn
ENV PATH="/app/.venv/bin:$PATH"
USER axelyn
EXPOSE 8000
CMD ["uvicorn", "axelyn.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

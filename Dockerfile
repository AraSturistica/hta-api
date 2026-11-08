FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -r appuser
USER appuser
CMD ["uvicorn", "--factory", "app.main:_factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

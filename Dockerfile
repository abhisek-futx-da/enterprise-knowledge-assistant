FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/models
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image so containers start offline and fast.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY app ./app
RUN useradd --create-home --uid 10001 appuser && mkdir -p /srv/data && chown -R appuser /srv /opt/models
USER appuser

EXPOSE 8000 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]


FROM python:3.12-slim AS ui
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
RUN pip install streamlit==1.67.0 httpx==0.28.1
COPY ui ./ui
RUN useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.maxUploadSize=10"]

FROM python:3.12-alpine3.23

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && adduser -D -u 1000 playlist \
    && mkdir /data \
    && chown playlist:playlist /data

COPY main.py spotify_auth.py ./
WORKDIR /data
USER playlist

ENTRYPOINT ["python", "/app/main.py"]
CMD []

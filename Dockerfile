FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY agria ./agria
RUN pip install --no-cache-dir .
COPY config ./config
ENV AGRIA_CONFIG=/app/config/sites.yaml AGRIA_DATA_DIR=/data
VOLUME /data
EXPOSE 8080
CMD ["agria"]

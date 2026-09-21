FROM python:3.12

RUN apt-get update && apt-get install -y --no-install-recommends \
        supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app
COPY . .

# Python deps
RUN uv sync

# Node deps — build native modules from source
RUN npm ci --build-from-source

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /app/start-auth.sh

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

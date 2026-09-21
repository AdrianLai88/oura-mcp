FROM python:3.12

RUN apt-get update && apt-get install -y --no-install-recommends \
        supervisor \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app
COPY . .

# Python deps
RUN uv sync

# Node deps
RUN npm ci

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /app/start-auth.sh

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

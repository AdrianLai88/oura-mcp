FROM python:3.12-slim

# build-essential + python3 needed for better-sqlite3 native addon (node-gyp)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        supervisor \
        build-essential \
        python3 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app
COPY . .

# Python deps (no uv.lock committed; resolves fresh)
RUN uv sync

# Node deps (builds better-sqlite3 native addon)
RUN npm ci

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Railway injects PORT; auth-server.js reads process.env.PORT automatically
EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

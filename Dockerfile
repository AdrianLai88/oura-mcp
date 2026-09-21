FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        supervisor \
        build-essential \
        python3 \
    && rm -rf /var/lib/apt/lists/*

# uv manages Python 3.12 and project dependencies
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY . .

# Install Python 3.12 via uv then project deps
RUN uv python install 3.12 && uv sync

# Node deps — build native modules from source for this exact environment
RUN npm ci --build-from-source

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

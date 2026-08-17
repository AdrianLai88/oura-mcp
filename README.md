# Oura MCP server

Read your Oura ring data from Claude.ai and Claude Code. Wraps
[@daveremy/oura-mcp](https://www.npmjs.com/package/@daveremy/oura-mcp), which
speaks stdio, in an OAuth 2.1 login so it can be added to Claude.ai as a custom
connector. Claude Code can use a plain token instead.

## Tools

`oura_daily_summary`, `oura_sleep`, `oura_readiness`, `oura_activity`,
`oura_workouts`, `oura_heart_rate`, `oura_stress`, `oura_spo2`, `oura_sessions`,
`oura_trends`.

## How it fits together

```
Claude.ai / Claude Code
        |  HTTPS
   Cloudflare Tunnel, or any proxy that gives you HTTPS
        |
   nginx  127.0.0.1:8441
        |
   auth-server.js  :8442    handles the login and the tokens
        |
   supergateway    :8440    puts the stdio server on HTTP, local only
        |
   oura-mcp  ->  api.ouraring.com
```

Ports are 8440-8442 so they sit clear of the other MCPs on this host.

## Setup

```bash
npm install --omit=dev

mkdir -p ~/.config/oura-mcp && chmod 700 ~/.config/oura-mcp
echo "OURA_TOKEN=your-personal-access-token" > ~/.config/oura-mcp/env
chmod 600 ~/.config/oura-mcp/env

CONFIG_DIR=~/.config/oura-mcp node set-password.js 'your-password-here'
openssl rand -hex 32 > ~/.config/oura-mcp/token
chmod 600 ~/.config/oura-mcp/token
```

Get the Oura token from [cloud.ouraring.com](https://cloud.ouraring.com/personal-access-tokens).

Then fill in `YOUR_USER` and the hostname in `systemd/*.service` and
`nginx/oura-mcp.conf`, and:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now oura-mcp oura-mcp-auth
sudo cp nginx/oura-mcp.conf /etc/nginx/sites-enabled/oura-mcp
sudo nginx -t && sudo systemctl reload nginx
```

Point a tunnel or an HTTPS proxy at `127.0.0.1:8441`. OAuth needs HTTPS.

Check it from outside: discovery should return metadata, and `/mcp` without a
token must return `401`.

```bash
curl https://your-host/.well-known/oauth-authorization-server
curl -o /dev/null -w '%{http_code}\n' -X POST https://your-host/mcp
```

## Connecting

Claude.ai: Settings, Connectors, Add custom connector, `https://your-host/mcp`,
client ID and secret blank.

Claude Code:

```bash
claude mcp add --transport http oura https://your-host/mcp \
  --header "Authorization: Bearer $(cat ~/.config/oura-mcp/token)" --scope user
```

## Credits

The Oura client is [@daveremy/oura-mcp](https://www.npmjs.com/package/@daveremy/oura-mcp).
The login layer comes from [rollecode/obsidian-remote-mcp](https://github.com/rollecode/obsidian-remote-mcp).

### 1.1.0: 2026-08-22

* Replace @daveremy/oura-mcp with our own client: it silently returned no
  sleep periods, no activity and no workouts on every single-day query
* Add resilience, cardiovascular age, VO2 max, sleep timing, tags, rest
  mode, ring hardware/battery and personal_info -- the rest of the Oura v2
  API the old package never covered
* Drop supergateway; the new server speaks streamable HTTP natively

### 1.0.0: 2026-08-17

* Serve the Oura MCP over HTTP behind an OAuth 2.1 login
* Accept a fixed token for Claude Code
* Add service files and nginx site

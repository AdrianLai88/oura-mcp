<center align="center" style="text-align: center;justify-content:center;">
<div align="center" style="text-align: center;justify-content:center;">
<h1 align="center" style="text-align: center;justify-content:center;">

Oura MCP server

<img style="justify-content:center;text-align: center;width: 95px; height: auto;" width="793" height="411" alt="image" src="https://github.com/user-attachments/assets/abed1a04-d69b-4ab4-a490-d606064df72d" />
<img style="justify-content:center;text-align: center;width: 145px; height: auto;" alt="image" src="public/oura-wordmark-white.png" />

</h1>


![Version](https://img.shields.io/badge/version-1.1.0-blue.svg?style=for-the-badge) ![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![Node](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=node.js&logoColor=white) ![OAuth](https://img.shields.io/badge/OAuth_2.1-EB5424?style=for-the-badge&logo=auth0&logoColor=white)

</div>
</center>

<hr>

Read your Oura ring from Claude.ai and Claude Code: sleep with the full periods behind the score, readiness, activity, workouts, heart rate, stress, SpO2, resilience, cardiovascular age, VO2 max, bedtime recommendations, tags and rest mode. It talks to the documented Oura API v2 and puts an OAuth 2.1 login in front so you can add it to Claude.ai as a custom connector. Claude Code can use a plain token instead.

<hr>

## Why not the npm package

This started as a wrapper around [@daveremy/oura-mcp](https://www.npmjs.com/package/@daveremy/oura-mcp) and replaced it, because that package returns nothing for most of what you would ask it. It queries single-day ranges as `start_date == end_date`, and the Oura API does not answer those the way the naming suggests:

* `sleep` filters on `bedtime_start` in UTC, so a night that begins at 00:31 local (UTC+3) lands on the previous UTC day and falls outside its own day's window
* `daily_activity` and `workout` treat `end_date` as exclusive, making a same-day range zero-width

The result is silent: `oura_sleep` returns a score with an empty `periods` array, `oura_activity` returns `null`, and `oura_workouts` returns `[]`, on every single-day call. Nothing errors, so it reads as "no data recorded" rather than "the query was wrong". This server pads the range on both sides and filters back by each record's own `day` field, which is timezone-correct, and follows `next_token` to exhaustion instead of silently returning one page.

## Tools

| Tool | What you get |
| --- | --- |
| `oura_daily_summary` | Sleep score, readiness score, sleep periods and activity for a day, in one call |
| `oura_sleep` | The daily score with its contributors, plus the raw periods: duration, stages, heart rate, HRV |
| `oura_sleep_time` | Oura's recommended bedtime window, and how the actual bedtime compared |
| `oura_readiness` | Readiness score and its contributors |
| `oura_resilience` | Long-term resilience level, with sleep and daytime recovery contributors |
| `oura_cardiovascular_age` | Estimated vascular age and pulse wave velocity |
| `oura_vo2_max` | Estimated VO2 max |
| `oura_activity` | Score, steps, calories, distance and the activity time breakdown |
| `oura_workouts` | Workouts with heart rate, calories, duration and intensity |
| `oura_heart_rate` | Continuous heart rate samples for a time window |
| `oura_stress` | Daily stress and recovery time |
| `oura_spo2` | Average nightly blood oxygen |
| `oura_sessions` | Meditation, breathing and relaxation sessions |
| `oura_tags` | Tags logged for a day, both the legacy and the enhanced kind |
| `oura_rest_mode` | Rest mode periods covering a day |
| `oura_ring` | Every ring ever paired, plus battery readings |
| `oura_personal_info` | Age, weight, height, biological sex, email |
| `oura_trends` | Sleep, readiness, activity and stress scores over a range of days |

Every date-scoped tool takes an optional `date` as `YYYY-MM-DD` and defaults to today. Oura files a night under the day you woke up.

`oura_vo2_max`, `oura_sleep_time` and `oura_cardiovascular_age` are sparse by design: Oura computes them periodically rather than daily, so an empty result is normal and not a sync failure.

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
   oura-mcp  :8440          streamable HTTP, local only
        |
   api.ouraring.com
```

Ports are 8440-8442 so they sit clear of the other MCPs on this host. The server on :8440 has no login of its own and refuses to bind anywhere but loopback, so it is only ever reached through the login layer.

## Setup

Needs Python 3.12 or newer, and Node for the login layer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
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

Running it over stdio instead, without any of the login layer:

```bash
OURA_TOKEN=your-token .venv/bin/oura-mcp
```

## Credits

The login layer comes from [rollecode/obsidian-remote-mcp](https://github.com/rollecode/obsidian-remote-mcp).

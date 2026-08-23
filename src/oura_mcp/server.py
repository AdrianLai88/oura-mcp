"""MCP server for the Oura API v2, covering every usercollection resource."""

import importlib.metadata
import json
import logging
import os
from datetime import date, datetime, timedelta

from mcp.server.fastmcp import FastMCP
from mcp.types import Icon

from .client import OuraClient, OuraError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    __version__ = importlib.metadata.version("oura-mcp")
except importlib.metadata.PackageNotFoundError:  # running from a source tree
    __version__ = "0.0.0"

_ICON_BASE = os.getenv("MCP_PUBLIC_URL", "").rstrip("/")
_ICON_SIZES = (48, 96, 256)

mcp = FastMCP(
    "oura",
    icons=(
        [
            Icon(
                src=f"{_ICON_BASE}/icon.png"
                if size == 256
                else f"{_ICON_BASE}/icon-{size}.png",
                mimeType="image/png",
                sizes=[f"{size}x{size}"],
            )
            for size in _ICON_SIZES
        ]
        if _ICON_BASE
        else None
    ),
    website_url=_ICON_BASE or None,
    instructions=(
        "Read Oura ring data: sleep (score and raw periods with stages/HR/HRV), "
        "readiness, activity, workouts, heart rate, stress, SpO2, sessions, "
        "resilience, cardiovascular age, VO2 max, sleep timing recommendations, "
        "tags, rest mode periods, ring hardware and battery, and the account "
        "profile. Every date-scoped tool defaults to today when no date is given."
    ),
)
mcp._mcp_server.version = __version__

_client: OuraClient | None = None


def _get_client() -> OuraClient:
    global _client
    if _client is None:
        _client = OuraClient()
    return _client


def _today() -> date:
    return date.today()


def _parse_date(d: str | None) -> date:
    return date.fromisoformat(d) if d else _today()


def _ok(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _err(e: Exception) -> str:
    if isinstance(e, OuraError):
        msg = str(e)
    else:
        msg = f"{type(e).__name__}: {e}"
    return json.dumps({"status": "error", "message": msg})


_READ = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

def _first(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


# ------------------------------------------------------------------
# Sleep
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_sleep(date: str | None = None) -> str:
    """Get detailed sleep data for a date: the daily sleep score with its
    contributors, and the raw sleep periods (duration, stages, heart rate,
    HRV) that score is built from.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        daily = _first(client.get_daily_sleep(d, d))
        periods = client.get_sleep_periods(d, d)
        return _ok({"date": str(d), "daily": daily, "periods": periods})
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_sleep_time(date: str | None = None) -> str:
    """Get Oura's recommended bedtime window and how last night's actual
    bedtime compared to it. Sparse: only populated on days Oura had enough
    history to compute a recommendation.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        rows = client.get_sleep_time(d, d)
        return _ok({"date": str(d), "sleep_time": _first(rows)})
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Readiness / resilience / cardiovascular
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_readiness(date: str | None = None) -> str:
    """Get the readiness score and its contributors for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(_first(client.get_daily_readiness(d, d)))
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_resilience(date: str | None = None) -> str:
    """Get the long-term resilience level (limited/adequate/solid/strong/
    exceptional) and its contributors (sleep recovery, daytime recovery,
    stress) for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok({"date": str(d), "resilience": _first(client.get_daily_resilience(d, d))})
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_cardiovascular_age(date: str | None = None) -> str:
    """Get estimated vascular age and pulse wave velocity for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok({"date": str(d), "cardiovascular_age": _first(client.get_daily_cardiovascular_age(d, d))})
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_vo2_max(date: str | None = None) -> str:
    """Get the estimated VO2 max for a date. Sparse: Oura only computes this
    periodically, not every day.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok({"date": str(d), "vo2_max": _first(client.get_vo2_max(d, d))})
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Activity / workouts
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_activity(date: str | None = None) -> str:
    """Get daily activity data (score, steps, calories, distance, activity
    time breakdown) for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(_first(client.get_daily_activity(d, d)))
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_workouts(date: str | None = None) -> str:
    """Get workouts (auto-detected and manually logged) with heart rate,
    calories, duration and intensity for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(client.get_workouts(d, d))
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_heart_rate(start_datetime: str, end_datetime: str) -> str:
    """Get continuous heart rate samples for a time window. Useful for
    correlating with untracked activity or workouts.

    Args:
        start_datetime: Start in ISO 8601 (e.g. 2024-01-01T00:00:00+00:00).
        end_datetime: End in ISO 8601 (e.g. 2024-01-01T23:59:59+00:00).
    """
    try:
        client = _get_client()
        return _ok(client.get_heart_rate(start_datetime, end_datetime))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Stress / SpO2 / sessions
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_stress(date: str | None = None) -> str:
    """Get daily stress and recovery time for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(_first(client.get_daily_stress(d, d)))
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_spo2(date: str | None = None) -> str:
    """Get average nightly blood oxygen (SpO2) percentage for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(_first(client.get_daily_spo2(d, d)))
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_sessions(date: str | None = None) -> str:
    """Get guided or unguided meditation, breathing and relaxation sessions
    for a date.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok(client.get_sessions(d, d))
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Tags / rest mode
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_tags(date: str | None = None) -> str:
    """Get tags logged for a date: built-in and custom tags (e.g. illness,
    alcohol, travel, a named event), covering both the legacy tag endpoint
    and the newer enhanced tags with time spans.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok({"date": str(d), "tags": client.get_tags(d, d)})
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_rest_mode(date: str | None = None) -> str:
    """Get rest mode periods active on a date (Oura's illness/injury/
    recovery mode, which relaxes activity goals and readiness contributors).

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        return _ok({"date": str(d), "rest_mode_periods": client.get_rest_mode_periods(d, d)})
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Device / account
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_ring(start_datetime: str | None = None, end_datetime: str | None = None) -> str:
    """Get every ring ever paired to the account (model, color, size,
    firmware) plus battery level readings for a time window (defaults to the
    last 24 hours).

    Args:
        start_datetime: ISO 8601, defaults to 24 hours ago.
        end_datetime: ISO 8601, defaults to now.
    """
    try:
        client = _get_client()
        end_dt = datetime.fromisoformat(end_datetime) if end_datetime else datetime.now().astimezone()
        start_dt = (
            datetime.fromisoformat(start_datetime)
            if start_datetime
            else end_dt - timedelta(hours=24)
        )
        return _ok(
            {
                "rings": client.get_ring_configuration(),
                "battery": client.get_ring_battery(start_dt.isoformat(), end_dt.isoformat()),
            }
        )
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_personal_info() -> str:
    """Get the account profile: age, weight, height, biological sex, email."""
    try:
        return _ok(_get_client().get_personal_info())
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Combined views
# ------------------------------------------------------------------


@mcp.tool(annotations=_READ)
def oura_daily_summary(date: str | None = None) -> str:
    """Get a one-call overview for a date: sleep score, raw sleep periods,
    readiness score, and daily activity. Use the more specific tools
    (oura_sleep, oura_readiness, oura_activity, oura_resilience, etc.) for
    fields not covered here.

    Args:
        date: YYYY-MM-DD, defaults to today.
    """
    try:
        client = _get_client()
        d = _parse_date(date)
        sleep = _first(client.get_daily_sleep(d, d))
        readiness = _first(client.get_daily_readiness(d, d))
        periods = client.get_sleep_periods(d, d)
        activity = _first(client.get_daily_activity(d, d))
        return _ok(
            {
                "date": str(d),
                "sleep": sleep,
                "readiness": readiness,
                "sleepPeriods": periods,
                "activity": activity,
            }
        )
    except Exception as e:
        return _err(e)


@mcp.tool(annotations=_READ)
def oura_trends(days: int = 7) -> str:
    """Get daily sleep, readiness, activity and stress scores over a range of
    days, most recent last.

    Args:
        days: Number of days to look back, including today (default 7).
    """
    try:
        client = _get_client()
        n = max(1, days)
        end = _today()
        start = end - timedelta(days=n - 1)
        sleep_by_day = {r["day"]: r for r in client.get_daily_sleep(start, end)}
        readiness_by_day = {r["day"]: r for r in client.get_daily_readiness(start, end)}
        activity_by_day = {r["day"]: r for r in client.get_daily_activity(start, end)}
        stress_by_day = {r["day"]: r for r in client.get_daily_stress(start, end)}

        results = []
        for i in range(n - 1, -1, -1):
            d = end - timedelta(days=i)
            ds = str(d)
            results.append(
                {
                    "date": ds,
                    "sleep_score": (sleep_by_day.get(ds) or {}).get("score"),
                    "readiness_score": (readiness_by_day.get(ds) or {}).get("score"),
                    "activity_score": (activity_by_day.get(ds) or {}).get("score"),
                    "stress_summary": (stress_by_day.get(ds) or {}).get("day_summary"),
                }
            )
        return _ok(results)
    except Exception as e:
        return _err(e)


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------


def main():
    """Run the server on stdin/stdout, or over HTTP.

    Over HTTP it has no login of its own, so it only listens on the local
    machine and is only ever reached through auth-server.js.
    """
    import argparse

    from dotenv import find_dotenv, load_dotenv

    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path and load_dotenv(dotenv_path, override=False):
        logger.info("Loaded .env from %s", dotenv_path)

    parser = argparse.ArgumentParser(prog="oura-mcp")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8440")))
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    if args.host not in ("127.0.0.1", "::1", "localhost"):
        raise SystemExit(
            f"refusing to listen on {args.host}: this server has no login of "
            "its own. Keep it on the local machine and put auth-server.js in "
            "front of it."
        )

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    logger.info("Listening on http://%s:%d/mcp", args.host, args.port)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()

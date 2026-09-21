"""Client for the Oura API v2 (https://api.ouraring.com/v2/usercollection/*).

Talks directly to Oura's documented REST API with a personal access token.
Two things the OpenAPI spec (https://cloud.ouraring.com/v2/docs) does not
document, both confirmed empirically against the live API:

1. `end_date`/`end_datetime` is exclusive on some usercollection endpoints
   (sleep, daily_activity, workout confirmed; likely others) but inclusive on
   others (daily_sleep, daily_readiness, daily_stress, daily_spo2, session).
   A single-day query with start_date == end_date silently returns zero rows
   on the exclusive ones. Fixed here by always widening the end date sent to
   the API by one day and filtering the response back down client-side --
   this is correct regardless of which behavior a given endpoint has.
2. Pagination via `next_token` is real and unbounded: a wide date range can
   need more than one page. Every list fetch here follows next_token to
   exhaustion rather than silently truncating.
"""

import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import httpx

BASE_URL = "https://api.ouraring.com"
_OURA_TOKEN_URL = "https://api.ouraring.com/oauth/token"


class OuraError(Exception):
    """Raised when the Oura API call fails."""


def _iso(d: date) -> str:
    return d.isoformat()


class OuraClient:
    """Client for the Oura v2 API. Accepts a static PAT via OURA_TOKEN or
    OAuth2 refresh-token rotation via OURA_CLIENT_ID + OURA_CLIENT_SECRET +
    OURA_REFRESH_TOKEN (refreshed automatically; new refresh token persisted
    to CONFIG_DIR/oura-tokens.json so container restarts stay authenticated)."""

    def __init__(self, *, token: str | None = None) -> None:
        self._client_id = os.getenv("OURA_CLIENT_ID", "").strip()
        self._client_secret = os.getenv("OURA_CLIENT_SECRET", "").strip()
        self._token_file = os.path.join(
            os.getenv("CONFIG_DIR", os.path.expanduser("~/.config/oura-mcp")),
            "oura-tokens.json",
        )
        self._expires_at: float = 0.0
        self._refresh_token: str | None = None

        static = token or os.getenv("OURA_TOKEN", "").strip()
        if static:
            self._token = static
        elif self._client_id and self._client_secret:
            self._refresh_token = (
                self._load_stored_refresh_token()
                or os.getenv("OURA_REFRESH_TOKEN", "").strip()
            )
            if not self._refresh_token:
                raise OuraError(
                    "OAuth2 mode requires OURA_REFRESH_TOKEN. "
                    "Run get_refresh_token.py once to obtain one."
                )
            self._token = ""
            self._do_token_refresh()
        else:
            raise OuraError(
                "Set OURA_TOKEN (personal access token) or "
                "OURA_CLIENT_ID + OURA_CLIENT_SECRET + OURA_REFRESH_TOKEN."
            )

        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=30.0,
        )

    def _load_stored_refresh_token(self) -> str:
        try:
            with open(self._token_file) as f:
                return json.load(f).get("refresh_token", "")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return ""

    def _save_tokens(self) -> None:
        os.makedirs(os.path.dirname(self._token_file), exist_ok=True)
        with open(self._token_file, "w") as f:
            json.dump({"refresh_token": self._refresh_token, "expires_at": self._expires_at}, f)

    def _do_token_refresh(self) -> None:
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }).encode()
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            _OURA_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, context=ctx) as resp:
            tokens = json.loads(resp.read())
        self._token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token", self._refresh_token)
        self._expires_at = time.time() + tokens.get("expires_in", 86400) - 60
        self._save_tokens()

    def _ensure_token(self) -> None:
        if self._refresh_token and time.time() >= self._expires_at:
            self._do_token_refresh()
            self._http.headers["Authorization"] = f"Bearer {self._token}"

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # Low-level request helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._ensure_token()
        params = {k: v for k, v in (params or {}).items() if v is not None}
        resp = self._http.get(path, params=params)
        if not resp.is_success:
            raise OuraError(f"Oura API {resp.status_code} on {path}: {resp.text}")
        return resp.json()

    def _list_all_pages(self, path: str, params: dict) -> list[dict]:
        """Follow next_token to exhaustion. A single page is capped by Oura's API."""
        out: list[dict] = []
        next_token: str | None = None
        while True:
            page_params = dict(params)
            if next_token:
                page_params["next_token"] = next_token
            page = self._get(path, page_params)
            out.extend(page.get("data", []))
            next_token = page.get("next_token")
            if not next_token:
                return out

    def _list_by_day(
        self,
        resource: str,
        start_date: date,
        end_date: date,
        *,
        day_field: str = "day",
    ) -> list[dict]:
        """Fetch a date-scoped resource, correcting for two undocumented
        quirks confirmed against the live API: end_date is exclusive on some
        endpoints (sleep, daily_activity, workout confirmed), and at least
        `sleep` filters by bedtime_start in UTC rather than by its own `day`
        field, so a period starting after 21:00 local (UTC+3) on day D can
        fall outside a [D, D] or even [D, D+1] UTC window. Widened by one day
        on both sides and filtered back to [start_date, end_date] by
        day_field, which is itself timezone-correct. Safe against endpoints
        that never needed the padding.
        """
        wide_start = start_date - timedelta(days=1)
        wide_end = end_date + timedelta(days=1)
        rows = self._list_all_pages(
            f"/v2/usercollection/{resource}",
            {"start_date": _iso(wide_start), "end_date": _iso(wide_end)},
        )
        lo, hi = _iso(start_date), _iso(end_date)
        return [r for r in rows if lo <= (r.get(day_field) or "") <= hi]

    # ------------------------------------------------------------------
    # Daily score/summary resources (day is inclusive on these, but the
    # widen+filter approach is harmless and keeps every resource consistent)
    # ------------------------------------------------------------------

    def get_daily_sleep(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_sleep", start, end)

    def get_daily_readiness(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_readiness", start, end)

    def get_daily_activity(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_activity", start, end)

    def get_daily_stress(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_stress", start, end)

    def get_daily_spo2(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_spo2", start, end)

    def get_daily_resilience(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_resilience", start, end)

    def get_daily_cardiovascular_age(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("daily_cardiovascular_age", start, end)

    def get_vo2_max(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("vO2_max", start, end)

    def get_sleep_time(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("sleep_time", start, end)

    # ------------------------------------------------------------------
    # Detailed/event resources
    # ------------------------------------------------------------------

    def get_sleep_periods(self, start: date, end: date) -> list[dict]:
        """Raw sleep periods: duration, stages, HR, HRV. This is the endpoint
        the old @daveremy/oura-mcp package silently broke for single-day
        queries (empty `periods` on every call)."""
        return self._list_by_day("sleep", start, end)

    def get_workouts(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("workout", start, end)

    def get_sessions(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("session", start, end)

    def get_rest_mode_periods(self, start: date, end: date) -> list[dict]:
        return self._list_by_day("rest_mode_period", start, end, day_field="start_day")

    def get_tags(self, start: date, end: date) -> list[dict]:
        """Both tag families: the legacy `tag` endpoint and the newer,
        richer `enhanced_tag` (custom names, start/end time spans)."""
        legacy = self._list_by_day("tag", start, end)
        enhanced = self._list_by_day(
            "enhanced_tag", start, end, day_field="start_day"
        )
        return legacy + enhanced

    # ------------------------------------------------------------------
    # Timestamp-scoped resources (caller supplies a real range; no
    # single-day ambiguity, so no widening needed)
    # ------------------------------------------------------------------

    def get_heart_rate(self, start_datetime: str, end_datetime: str) -> list[dict]:
        return self._list_all_pages(
            "/v2/usercollection/heartrate",
            {"start_datetime": start_datetime, "end_datetime": end_datetime},
        )

    def get_ring_battery(self, start_datetime: str, end_datetime: str) -> list[dict]:
        return self._list_all_pages(
            "/v2/usercollection/ring_battery_level",
            {"start_datetime": start_datetime, "end_datetime": end_datetime},
        )

    # ------------------------------------------------------------------
    # Unscoped/single-document resources
    # ------------------------------------------------------------------

    def get_personal_info(self) -> dict:
        return self._get("/v2/usercollection/personal_info")

    def get_ring_configuration(self) -> list[dict]:
        """Every ring the account has ever paired, not just the active one."""
        return self._list_all_pages("/v2/usercollection/ring_configuration", {})

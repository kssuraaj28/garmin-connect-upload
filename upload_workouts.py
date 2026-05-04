"""
Upload a Garmin Connect structured-workout JSON file using zendriver.

Usage:
    python upload_workouts.py path/to/workout.json

Opens a real Chrome window via zendriver, waits for you to finish logging in
to Garmin Connect, then POSTs the workout to the workout-service endpoint
from *inside* the authenticated page context. The request mirrors what the
"share-your-garmin-workout" Chrome extension does:

    POST /gc-api/workout-service/workout
    connect-csrf-token: <from meta[name="csrf-token"]>

Because the request runs in the page itself, it inherits cookies and session
state automatically.
"""

import asyncio
import json
import sys
from pathlib import Path

import zendriver as zd

CONNECT_URL = "https://connect.garmin.com"
WORKOUTS_PAGE = f"{CONNECT_URL}/modern/workouts"
WORKOUT_ENDPOINT = "/gc-api/workout-service/workout"

# Persistent Chrome profile sits next to this script so Garmin cookies
# survive between runs. First run creates it empty; after you log in once,
# subsequent runs reuse the session.
PROFILE_DIR = Path(__file__).resolve().parent / ".profile"

# Garmin sets one of these on connect.garmin.com once SSO completes.
AUTH_COOKIES = {"SESSIONID", "GARMIN-SSO-GUID"}

# JS runs inside the authenticated page. Reads the CSRF token from the meta
# tag (same way the extension does) and POSTs the payload. Returns
# {ok, status, body} so Python can log success/failure.
POST_WORKOUT_JS = """
(async () => {
    const payload = %s;
    const meta = document.querySelector('meta[name="csrf-token"]');
    const csrf = meta ? meta.getAttribute('content') : null;
    if (!csrf) {
        return { ok: false, status: 0, body: 'missing csrf-token meta tag' };
    }
    const res = await fetch(%r, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'cache-control': 'no-cache',
            'connect-csrf-token': csrf,
            'x-requested-with': 'XMLHttpRequest',
        },
        credentials: 'include',
        body: JSON.stringify(payload),
    });
    let body = null;
    try { body = await res.json(); } catch (e) { body = await res.text(); }
    return { ok: res.ok, status: res.status, body };
})()
"""


async def is_authenticated(browser) -> bool:
    cookies = await browser.cookies.get_all()
    names = {c.name for c in cookies if "garmin.com" in (c.domain or "")}
    return bool(AUTH_COOKIES & names)


async def wait_for_csrf_token(page, timeout: float = 10.0) -> None:
    """Poll until the csrf-token meta tag is present in the document."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        found = await page.evaluate(
            "!!document.querySelector('meta[name=\"csrf-token\"]')"
        )
        if found:
            return
        await asyncio.sleep(0.2)
    raise RuntimeError("csrf-token meta tag did not appear within timeout")


async def wait_for_login(browser, grace_period: float = 5.0) -> None:
    """Block until Garmin auth cookies are present.

    On a warm profile, Chrome re-establishes the session cookies during the
    initial page load, so we poll silently for a few seconds before deciding
    the user actually needs to log in."""
    deadline = asyncio.get_event_loop().time() + grace_period
    while asyncio.get_event_loop().time() < deadline:
        if await is_authenticated(browser):
            return
        await asyncio.sleep(0.5)

    print(">> Log in to Garmin Connect in the opened browser window.")
    print(">> Waiting for authenticated session...")
    while not await is_authenticated(browser):
        await asyncio.sleep(1)


async def main(workout_file: Path) -> int:
    payload = json.loads(workout_file.read_text())

    PROFILE_DIR.mkdir(exist_ok=True)
    browser = await zd.start(headless=False, user_data_dir=str(PROFILE_DIR))
    page = None
    try:
        print("navigating to workouts page")
        page = await browser.get(WORKOUTS_PAGE)

        print("waiting for login")
        await wait_for_login(browser)

        # After login we may have been redirected through SSO; land back on
        # /modern/workouts so the csrf-token meta tag is guaranteed present.
        print("navigating back to workouts page")
        await page.get(WORKOUTS_PAGE)
        await wait_for_csrf_token(page)

        print("POSTing workout")
        js = POST_WORKOUT_JS % (json.dumps(payload), WORKOUT_ENDPOINT)
        result = await page.evaluate(js, await_promise=True, return_by_value=True)

        if isinstance(result, dict) and result.get("ok"):
            body = result.get("body") or {}
            wid = body.get("workoutId") if isinstance(body, dict) else None
            print(f"[ OK ] status={result.get('status')} workoutId={wid}")
            return 0

        print(f"[FAIL] {workout_file.name}")
        print(f"  result: {result}")
        return 1
    finally:
        print("stopping browser")
        if page is not None:
            await page.close()
        await browser.stop()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(main(path)))

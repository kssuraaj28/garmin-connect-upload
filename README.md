# garmin-connect-upload

A command-line tool for uploading structured-workout JSON files to
[Garmin Connect](https://connect.garmin.com). Mirrors the behaviour of the
[share-your-garmin-workout](https://github.com/fulippo/share-your-garmin-workout)
Chrome extension's import feature, but from the terminal.

It drives a real Chrome window via [zendriver](https://zendriver.dev/) so it
inherits your normal Garmin login (SSO, CAPTCHA, MFA — all of it) without
reimplementing any of Garmin's auth flow. The upload `fetch` runs from
*inside* the authenticated page, so cookies and the CSRF token are picked up
automatically.

## Setup

Requires Python 3.10+ and a working Chrome/Chromium install.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Usage

```sh
.venv/bin/python upload_workouts.py path/to/workout.json [more.json ...]
.venv/bin/python upload_workouts.py path/to/dir_of_json/
```

You can pass any mix of individual `.json` files and directories. Directories
are scanned non-recursively for `*.json` files.

On the **first** run, a Chrome window opens to `connect.garmin.com` and waits
for you to log in. Once the session cookies are set, the script POSTs each
workout to `/gc-api/workout-service/workout` and prints the resulting workout
ID.

On subsequent runs, the login step is skipped — see the next section.

## Persistent browser profile

The Chrome profile is stored at `./.profile/` next to the script. This is
where Garmin cookies live between runs, so you only need to log in once per
session (or whenever Garmin's session expires, usually after a few days).

If you ever want a clean state, just delete the `.profile/` directory.

## How it works (briefly)

1. Launch Chrome via zendriver with `user_data_dir=./.profile`.
2. Navigate to `https://connect.garmin.com/modern/workouts` and wait for the
   auth cookies (`SESSIONID` / `GARMIN-SSO-GUID`) to appear.
3. Wait for the `<meta name="csrf-token">` tag to be present on the page.
4. For each workout file:
   - Strip server-generated fields (`workoutId`, `ownerId`, `createdDate`,
     `updatedDate`, `author`, `estimatedDurationInSecs`,
     `estimatedDistanceInMeters`).
   - Recursively null every `stepId` inside `workoutSegments`.
   - `page.evaluate()` a `fetch()` POST to
     `/gc-api/workout-service/workout` with the `connect-csrf-token` header
     read from the meta tag.
5. Log the resulting workout ID (or the error body) and move on to the next
   file.

## AI-generated code notice

This project — including the script, this README, and the approach used —
was written by Claude (Anthropic's Claude Code CLI) in collaboration with a
human operator. The workout-upload logic is a direct port of the
`GarminImport` class from the open-source
[share-your-garmin-workout](https://github.com/fulippo/share-your-garmin-workout)
Chrome extension by @fulippo. Review the code before running it against
your own Garmin account.

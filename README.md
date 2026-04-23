# django_uv_web_app

A small Django task-tracker web app that is managed exclusively by [uv](https://docs.astral.sh/uv/).
It exists as a **felix test fixture** — the project is intentionally pinned to
vulnerable, older dependency versions and uses a handful of legacy Django APIs
so that running a major upgrade through felix exercises the smart-update
pipeline across multiple files.

## Project layout

```
django_uv_web_app/
├── .python-version          # uv picks this Python automatically
├── pyproject.toml           # [project] dependencies — no requirements.txt
├── uv.lock                  # resolved by `uv lock`
├── manage.py
├── tasks/                   # Django app: models, views, middleware, services…
└── tasktracker/             # project package: settings, urls, wsgi
```

## Running the app

```bash
uv sync                      # installs deps into ./.venv, respects uv.lock
uv run python manage.py migrate
uv run python manage.py runserver
```

## Vulnerable baseline — what Felix should detect

| Package                | Pinned    | Known advisory surface                         |
| ---------------------- | --------- | ---------------------------------------------- |
| `django`               | 3.2.18    | CVE-2023-31047, CVE-2023-24580, CVE-2023-36053 |
| `djangorestframework`  | 3.12.4    | XSS fix in 3.14                                |
| `requests`             | 2.25.1    | CVE-2023-32681 (Proxy-Authorization leak)      |
| `gunicorn`             | 19.10.0   | CVE-2024-1135 (HTTP Request Smuggling)         |
| `python-dotenv`        | 0.19.0    | older — benign                                 |
| `urllib3` (transitive) | ≤ 1.26.x  | CVE-2023-43804, CVE-2023-45803                 |
| `certifi` (transitive) | ≤ 2022.x  | CVE-2022-23491                                 |
| `idna` (transitive)    | ≤ 3.6     | CVE-2024-3651                                  |

## Legacy Django APIs intentionally used

A major upgrade to Django 5.x forces patches across **five** files:

| File                            | Legacy API                                            | Removed in |
| ------------------------------- | ----------------------------------------------------- | ---------- |
| `tasktracker/urls.py`           | `django.conf.urls.url()`                              | 4.2        |
| `tasks/urls.py`                 | `django.conf.urls.url()` + regex routes               | 4.2        |
| `tasks/services.py`             | `django.utils.encoding.force_text`                    | 4.0        |
| `tasks/middleware.py`           | `django.utils.timezone.utc`                           | 5.0        |
| `tasktracker/settings.py`       | `STATICFILES_STORAGE` / `DEFAULT_FILE_STORAGE` + `USE_L10N` | 5.0 (replaced by `STORAGES`) |

## Felix test flows this fixture covers

| Flow                                  | Command                                                |
| ------------------------------------- | ------------------------------------------------------ |
| Scan + tree view (uv.lock detection)  | `felix scan`                                           |
| Advisory rollup for direct + trans.   | `felix scan` output                                    |
| Normal single-dep bump (no breakage)  | `felix deps:update python-dotenv==1.0.0`               |
| Minor bump (no breakage)              | `felix deps:update djangorestframework==3.14.0`        |
| **Major upgrade w/ multi-file code patches** | `felix deps:update django==5.2.8`               |
| Transitive Tier 1 (parent-first)      | `felix deps:update urllib3==1.26.18`                   |
| Transitive Tier 2 (direct pin fallback) | `felix deps:update certifi==2024.7.4`                |
| Full remediate sweep                  | `felix remediate`                                      |
| Lockfile re-sync                      | verify `uv.lock` regenerates after each update         |

## Resetting the fixture

After Felix mutates the project, reset it with:

```bash
git reset --hard HEAD && rm -rf .venv db.sqlite3 && uv sync && uv run python manage.py migrate
```

# Utility scripts

Developer tools that live outside the app runtime. Each script has a full docstring at the top — this file is the directory index.

Run from the project root with the venv active. On Windows: `.venv\Scripts\python.exe scripts\<name>.py`. On Unix: `.venv/bin/python scripts/<name>.py`.

| Script | One-line purpose | When to reach for it |
| --- | --- | --- |
| [`garmin_diagnose.py`](./garmin_diagnose.py) | Garmin login / API / grant_type diagnostic toolkit (subcommands: `login`, `api`, `grants`, `all`) | After a `garminconnect` library upgrade, Garmin-side auth change, or a regional sync breakage. See `docs/dev/gotchas.md` "Garmin CN" section. |
| [`garmin_profile_probe.py`](./garmin_profile_probe.py) | Dump Garmin profile, HR, sleep, and running-CP payloads for the connected user | When deciding which key names `parse_user_profile` / `parse_garmin_recovery` should read after Garmin changes a response shape. Requires a successful sync first. |
| [`cleanup_garmin_token_bug.py`](./cleanup_garmin_token_bug.py) | One-shot cleanup for the historical shared-tokenstore cross-user leak | Only if migrating a pre-fix deployment. Deletes Garmin-sourced rows for non-admin users — **read the docstring carefully before running.** |
| [`migrate_csv_to_db.py`](./migrate_csv_to_db.py) | Migrate legacy CSV data + `config.json` into SQLite | Historical one-shot for the CSV → DB architecture change. Safe to ignore on fresh installs. |
| [`generate_sample_data.py`](./generate_sample_data.py) | Regenerate synthetic fixtures in `data/sample/` | After a schema change that affects test CSVs. |
| [`seed_sample_data.py`](./seed_sample_data.py) | Copy `data/sample/` → `data/` for a quick-start empty-install demo | **Never run when real user data exists in the DB** — overwrites. |
| [`translate_missing.py`](./translate_missing.py) | Translate new copy and review existing Lingui `.po` entries with page context via Azure AI | `po` fills new strings; `review-po` runs a bounded native-language pass over a stable catalog shard. Requires `AZURE_AI_ENDPOINT` and Azure credentials. |
| [`check_i18n_quality.py`](./check_i18n_quality.py) | Enforce catalog coverage, placeholders, canonical terms, voice rules, and Chinese typography | Before committing catalog changes; it also runs in the i18n PR workflow and after every automated translation/review pass. |
| [`export_brand_icons.py`](./export_brand_icons.py) | Render the Praxys flag mark SVG → PNG at several sizes | When the brand SVG changes and raster assets (mini-program icons, favicons) need re-exporting. |
| `i18n_glossary.yaml` | Chinese voice guide and canonical terminology consumed by both i18n scripts | Not a script — edit when product tone or a domain term intentionally changes, then sweep the catalog in the same PR. |

## Quick-start tips

- Most scripts expect the project venv (`.venv/`). Activate it or call the venv's python directly.
- Scripts that need credentials read them from `.env`, env vars, or the DB (see each docstring). Never commit credentials.
- Scripts that touch the DB use the same `db/session.py` as the app — `PRAXYS_LOCAL_ENCRYPTION_KEY` must be set.
- Diagnostic scripts (`garmin_diagnose.py`, `garmin_profile_probe.py`) are read-only against Garmin's servers and safe to run repeatedly.
- `cleanup_garmin_token_bug.py` and `seed_sample_data.py` are **destructive** on the DB or on `data/`. Back up before running.

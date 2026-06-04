# Security Audit Results

Date: 2026-06-03

This document contains the results of the repository security audit using:

- `bandit` static code analysis
- `pip-audit` dependency vulnerability audit
- Django `manage.py check --deploy` deployment security inspector

## 1. Audit commands executed

The following commands were executed from the repository root:

```bash
python -m pip install --upgrade pip
pip install -r requirements/dev.txt
bandit -r . -x ./tests,./.venv,./staticfiles -f json -o bandit-report.json --exit-zero
bandit -r . -x ./tests,./.venv,./staticfiles --exit-zero
pip-audit -r requirements/base.txt
python manage.py migrate --noinput
DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
```

## 2. Bandit results

### Summary

- `bandit` scanned the repository recursively
- Excluded paths: `./tests`, `./.venv`, `./staticfiles`
- Generated JSON report: `bandit-report.json`
- Scan result: no issues identified
- Total lines of code scanned: 7,324
- Total issues by severity:
  - Undefined: 0
  - Low: 0
  - Medium: 0
  - High: 0

### Notes

The scan output included one non-failing warning about a `# nosec` comment in `core/templatetags/mhtms_tags.py:43`.
This warning did not produce a failed result because Bandit was invoked with `--exit-zero`.

### Bandit raw output

```text
[main]  INFO    profile include tests: None
[main]  INFO    profile exclude tests: None
[main]  INFO    cli include tests: None
[main]  INFO    cli exclude tests: None
Working... ━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━━━━  52% 0:00:01[tester]       WARNING  nosec encountered (B703), but no failed test on file .\core\templatetags\mhtms_tags.py:43
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:01
[json]  INFO    JSON output written to file: bandit-report.json
[main]  INFO    profile include tests: None
[main]  INFO    profile exclude tests: None
[main]  INFO    cli include tests: None
[main]  INFO    cli exclude tests: None
[main]  INFO    running on Python 3.13.13
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━╺━━━━━━━━━━━━━━  64% 0:00:01[tester]       WARNING  nosec encountered (B703), but no failed test on file .\core\templatetags\mhtms_tags.py:43
Working... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:01
Run started:2026-06-03 14:41:06.073145+00:00

Test results:
        No issues identified.

Code scanned:
        Total lines of code: 7324
        Total lines skipped (#nosec): 0

Run metrics:
        Total issues (by severity):
                Undefined: 0
                Low: 0
                Medium: 0
                High: 0
        Total issues (by confidence):
                Undefined: 0
                Low: 0
                Medium: 0
                High: 0
Files skipped (0):
``` 

## 3. pip-audit results

### Summary

- `pip-audit` audited the dependency set defined in `requirements/base.txt`
- Result: no known vulnerabilities found

### pip-audit raw output

```text
WARNING:venv:Actual environment location may have moved due to redirects, links or junctions.
  Requested location: "C:\\Users\\WINDOW~1\\AppData\\Local\\Temp\\tmpqc4g902h\\Scripts\\python.exe"
  Actual location:    "C:\\Users\\Windows 11\\AppData\\Local\\Temp\\tmpqc4g902h\\Scripts\\python.exe"
No known vulnerabilities found
```

## 4. Django `check --deploy` results

### Summary

- Migrations were applied successfully with `python manage.py migrate --noinput`
- `DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy` completed with warnings
- Django reported 3 deploy/security warnings

### Warnings found

1. `axes.W006` — `AXES_LOCKOUT_PARAMETERS` does not contain `ip_address`
   - Impact: an attacker may bypass rate limits by rotating User-Agent headers or cookies
   - Recommendation: add `ip_address` to `AXES_LOCKOUT_PARAMETERS`

2. `security.W008` — `SECURE_SSL_REDIRECT` is not set to `True`
   - Impact: the site may be available over both SSL and non-SSL connections
   - Recommendation: set `SECURE_SSL_REDIRECT = True` or enforce HTTPS with a load balancer/reverse proxy

3. `security.W009` — `SECRET_KEY` is weak
   - Impact: a short or predictable key weakens security-critical Django features
   - Recommendation: generate a long, random secret key and do not use a Django-generated default

### Django raw output

```text
System check identified some issues:

WARNINGS:
?: (axes.W006) AXES_LOCKOUT_PARAMETERS does not contain 'ip_address'. This configuration allows attackers to bypass rate limits by rotating User-Agents or Cookies.
        HINT: Add 'ip_address' to AXES_LOCKOUT_PARAMETERS.
Operations to perform:
  Apply all migrations: accounts, admin, auditlogs, auth, axes, consultations, contenttypes, django_celery_beat, patients, sessions, token_blacklist, triage
Running migrations:
  No migrations to apply.
System check identified some issues:

WARNINGS:
?: (axes.W006) AXES_LOCKOUT_PARAMETERS does not contain 'ip_address'. This configuration allows attackers to bypass rate limits by rotating User-Agents or Cookies.
        HINT: Add 'ip_address' to AXES_LOCKOUT_PARAMETERS.
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True. Unless your site should be available over both SSL and non-SSL connections, you may want to either set this setting True or configure a load balancer or reverse-proxy server to redirect all connections to HTTPS.
?: (security.W009) Your SECRET_KEY has less than 50 characters, less than 5 unique characters, or it's prefixed with 'django-insecure-' indicating that it was generated automatically by Django. Please generate a long and random value, otherwise many of Django's security-critical features will be vulnerable to attack.

System check identified 3 issues (0 silenced).
```

## 5. Conclusions and actions

- Bandit scan: no issues found in the codebase
- pip-audit: no known dependency vulnerabilities
- Django deploy check: 3 warnings require attention before production rollout

### Recommended follow-up actions

- Update `AXES_LOCKOUT_PARAMETERS` to include `ip_address`
- Set `SECURE_SSL_REDIRECT = True` for production deployments
- Replace the current `SECRET_KEY` with a strong random secret from a secure generator

### Notes for PDF conversion

This file is formatted with explicit headings, command output blocks, and a clear conclusion section for direct PDF rendering.

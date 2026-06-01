# Deploy MHTMS on Render.com

This guide walks you through deploying the **Municipal Health & Triage Management System** on [Render](https://render.com) using the included `render.yaml` Blueprint.

**What gets created:**

| Resource | Name | Purpose |
|----------|------|---------|
| Web service | `mhtms-web` | Django + Gunicorn |
| PostgreSQL | `mhtms-db` | Primary database |
| Key Value (Redis) | `mhtms-redis` | Cache, sessions, Celery broker |

---

## Before you start

### 1. Accounts and keys

- [ ] Render account (you have this)
- [ ] [GitHub](https://github.com) account (to host the code)
- [ ] [Cloudinary](https://cloudinary.com) account — profile photos & patient documents
- [ ] (Optional) [OpenAI](https://platform.openai.com) API key — **Consult AI** feature only

### 2. Push code to GitHub

Render deploys from Git. If the project is not on GitHub yet:

```powershell
cd "C:\Users\Windows 11\Desktop\municipal-health-and-triage-management-system"
git init
git add .
git commit -m "Prepare for Render deployment"
```

Create an empty repository on GitHub (e.g. `municipal-health-and-triage-management-system`), then:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

> Never commit `.env` — it is listed in `.gitignore`. Secrets are set in the Render dashboard.

### 3. Confirm local project runs

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/prod.txt
python manage.py check --deploy --settings=config.settings.production
```

Fix any errors before deploying.

---

## Part A — Deploy with Blueprint (recommended)

### Step 1: Open Blueprint deploy

1. Log in to [https://dashboard.render.com](https://dashboard.render.com)
2. Click **New +** → **Blueprint**
3. Connect your **GitHub** account if prompted
4. Select the repository containing this project
5. Render detects `render.yaml` — review the three resources (web, Postgres, Redis)
6. Click **Apply**

Blueprint creation can take **5–15 minutes**.

### Step 2: Set required environment variables

After the blueprint is created, open the **`mhtms-web`** service → **Environment**.

Set these **before** the first successful deploy (or immediately after if the deploy failed):

| Variable | Example | Notes |
|----------|---------|--------|
| `ALLOWED_HOSTS` | `mhtms-web.onrender.com,.onrender.com` | Replace `mhtms-web` with your **actual** service name from Render |
| `CSRF_TRUSTED_ORIGINS` | `https://mhtms-web.onrender.com` | Must be `https://` — no trailing slash |
| `CORS_ALLOWED_ORIGINS` | `https://mhtms-web.onrender.com` | Same URL if you use the API from a browser |
| `CLOUDINARY_CLOUD_NAME` | from Cloudinary dashboard | **Dashboard → Account Details** |
| `CLOUDINARY_API_KEY` | from Cloudinary | |
| `CLOUDINARY_API_SECRET` | from Cloudinary | |

**Find your Render URL:** `mhtms-web` service → top of page shows  
`https://mhtms-web-xxxx.onrender.com` or similar. Use that exact host in the variables above.

**Auto-set by Blueprint (do not change unless you know why):**

- `SECRET_KEY` — generated
- `DATABASE_URL` — linked from `mhtms-db`
- `REDIS_URL` / `CELERY_BROKER_URL` — linked from `mhtms-redis`
- `DJANGO_SETTINGS_MODULE` — `config.settings.production`
- `DEBUG` — `False`

**Optional (Consult AI):**

| Variable | Value |
|----------|--------|
| `OPENAI_API_KEY` | `sk-...` |
| `OPENAI_MODEL` | `gpt-4o-mini` (default in blueprint) |

### Step 3: Trigger deploy

1. **mhtms-web** → **Manual Deploy** → **Deploy latest commit** (if not already deploying)
2. Open **Logs** and watch the build:
   - `pip install -r requirements/prod.txt`
   - `migrate`
   - `seed_demo --reset` (demo users and sample patients)
   - `collectstatic`
   - Gunicorn starts

### Step 4: Verify the site

1. Open `https://YOUR-SERVICE.onrender.com/health/`  
   Expected: `{"status": "ok"}`
2. Open `https://YOUR-SERVICE.onrender.com/accounts/login/`
3. Log in with demo credentials (Part C)

### Step 5: Custom domain (optional)

1. **mhtms-web** → **Settings** → **Custom Domains**
2. Add your domain and follow DNS instructions
3. Update environment variables:
   - `ALLOWED_HOSTS` → add `yourdomain.gov.ph,.onrender.com`
   - `CSRF_TRUSTED_ORIGINS` → `https://yourdomain.gov.ph`
   - `CORS_ALLOWED_ORIGINS` → `https://yourdomain.gov.ph`

---

## Part B — Manual deploy (without Blueprint)

Use this if you prefer creating services one by one.

### B1. PostgreSQL

1. **New +** → **PostgreSQL**
2. Name: `mhtms-db`, Database: `mhtms`, User: `mhtms`
3. Region: **Singapore** (or closest to users)
4. Plan: **Free** or **Starter** (free DB may not be available in all accounts — use Starter if needed)
5. Create → copy **Internal Database URL**

### B2. Redis

1. **New +** → **Redis**
2. Name: `mhtms-redis`, Plan: **Free**
3. Create → note **Internal Redis URL**

### B3. Web service

1. **New +** → **Web Service**
2. Connect your GitHub repo
3. Settings:

| Field | Value |
|-------|--------|
| Name | `mhtms-web` |
| Region | Singapore |
| Branch | `main` |
| Runtime | **Python 3** |
| Build Command | `./build.sh` (installs deps, migrate, `seed_demo --reset`, collectstatic) |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |

> **Free tier:** `preDeployCommand` is not supported. Migrations run inside `build.sh` instead.
| Health Check Path | `/health/` |

4. **Environment** — add all variables from Part A Step 2, plus:

| Key | Value |
|-----|--------|
| `DATABASE_URL` | Paste **Internal** Postgres URL |
| `REDIS_URL` | Paste **Internal** Redis URL |
| `CELERY_BROKER_URL` | Same Redis URL |
| `SECRET_KEY` | Generate: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `DEBUG` | `False` |
| `PYTHON_VERSION` | `3.13.0` |

5. **Create Web Service**

---

## Part C — Demo data and login

**Every deploy** runs `python manage.py seed_demo --reset` inside `build.sh` (free tier has no Shell).

- Creates or updates demo users (`admin@mhtms.gov.ph`, etc.) and resets their password to `DemoPass123!`
- `--reset` removes sample patients (`PAT-SAMPLE-*`, `PAT-DEMO-001`) and related triage/consultations before re-seeding, so redeploys do not duplicate queue rows

Check build logs for `=== Sample data ready ===` and `Created user admin@mhtms.gov.ph`.

### Manual re-seed (optional)

If you need to refresh data without a full deploy:

- **Paid plans (Shell):** `python manage.py seed_demo --reset` on **mhtms-web**
- **From your PC** (External `DATABASE_URL`, one-time only):

```powershell
$env:DATABASE_URL="postgresql://..."
$env:DJANGO_SETTINGS_MODULE="config.settings.production"
python manage.py seed_demo --reset
```

> **Production go-live:** Remove or comment out the `seed_demo` line in `build.sh` before real patient data is stored, or demo passwords and sample patients will be reset on every deploy.

### Demo logins

| Email | Password | Role |
|-------|----------|------|
| admin@mhtms.gov.ph | DemoPass123! | Super Admin |
| doctor@mhtms.gov.ph | DemoPass123! | Doctor (Carigara) |
| nurse@mhtms.gov.ph | DemoPass123! | Nurse (Carigara) |

Change passwords in production for real use.

---

## Part D — Cloudinary setup

1. [Cloudinary Console](https://console.cloudinary.com/) → **Account Details**
2. Copy **Cloud name**, **API Key**, **API Secret**
3. Paste into Render **Environment** for `mhtms-web`
4. **Save** → Render redeploys
5. Test: log in → **My profile** (header avatar) → upload a photo

Uploads are stored under folder `mhtms/profiles/{user_id}/` on Cloudinary.

---

## Part E — Production checklist

- [ ] `DEBUG=False` (set by blueprint)
- [ ] `ALLOWED_HOSTS` includes your `.onrender.com` host and custom domain
- [ ] `CSRF_TRUSTED_ORIGINS` uses `https://` URLs
- [ ] Cloudinary credentials are real (not `demo`)
- [ ] `python manage.py check --deploy` passes locally with production settings
- [ ] `/health/` returns `{"status":"ok"}`
- [ ] Login, triage, and profile photo upload work
- [ ] Create a new superuser or change demo passwords before go-live

### Create production superuser (Shell)

```bash
python manage.py createsuperuser
```

---

## Troubleshooting

### Deploy fails at `collectstatic`

- Check build logs for missing static files
- Run locally: `python manage.py collectstatic --noinput --settings=config.settings.production`

### Deploy fails at `migrate`

- Confirm `DATABASE_URL` is set and Postgres is **available** (same region)
- Check **build logs** for SQL errors (migrations run in `build.sh` on free tier)

### Blank login button, missing admin charts, or stuck modal on doctor dashboard

Production **Content-Security-Policy** must allow the same CDNs as `templates/base.html` and `admin.html` (`unpkg.com`, `cdn.jsdelivr.net` for Chart.js, `cdn.tailwindcss.com`). If Chart.js is blocked, admin charts stay empty; if Alpine components fail to register, confirmation modals can appear stuck.

After pulling the latest `main`, redeploy **mhtms-web** and hard-refresh the browser (Ctrl+Shift+R).

### Login always fails ("Invalid email or password")

1. Open the latest **build** logs and confirm `seed_demo --reset` finished without errors
2. Redeploy **mhtms-web** → **Manual Deploy** → **Deploy latest commit**
3. If build seeding is disabled, run `python manage.py seed_demo --reset` via Shell or locally (Part C)
4. Too many failed attempts: run `python manage.py unlock_login --all` (Shell or local with `DATABASE_URL`)

### `DisallowedHost` in browser

- Add your exact host to `ALLOWED_HOSTS`, e.g. `mhtms-web.onrender.com,.onrender.com`

### CSRF verification failed on login

- Set `CSRF_TRUSTED_ORIGINS=https://your-exact-host.onrender.com` (HTTPS, no trailing slash)

### 502 / service unavailable

- Free web tier **spins down** after ~15 minutes idle — first request may take 30–60 seconds
- Check **Logs** for Gunicorn crashes (often missing env vars)

### Profile photo / Cloudinary errors

- Verify all three `CLOUDINARY_*` variables
- See build logs; ensure `common/cloudinary_utils.py` runs (included in project)

### Consult AI fails on Render

- Set `OPENAI_API_KEY` in environment
- Linux servers usually do not need the Windows SSL workaround; if errors persist, check OpenAI billing and logs

### Blueprint: `pre-deploy command is not supported for free tier`

Remove `preDeployCommand` from `render.yaml`. This project runs migrations in `build.sh` instead (already configured on `main`).

### Blueprint: `services[1] must specify IP allow list`

Render requires `ipAllowList` on the Redis / Key Value service. Use the latest `render.yaml` from this repo, which includes:

```yaml
  - type: keyvalue
    name: mhtms-redis
    ipAllowList: []   # internal-only (recommended)
```

Push to GitHub, then run Blueprint again. If validation still fails, change to:

```yaml
    ipAllowList:
      - source: 0.0.0.0/0
        description: everywhere
```

### Redis connection errors

- Use **Internal** Redis URL from the Render Key Value service (not external) for `REDIS_URL`
- Ensure `mhtms-redis` is in the same region and **Available**

---

## Costs and limits (typical Render free tier)

- **Web**: Free with spin-down; cold starts after idle
- **Redis**: Free tier has memory limits (~25 MB)
- **PostgreSQL**: Availability/plan varies by account — Starter plan ~$7/month if free DB is not offered

Upgrade plans when you need always-on uptime, more RAM, or production SLAs.

---

## Updating the live site

1. Push commits to `main` on GitHub
2. Render **auto-deploys** if enabled (**Settings** → **Auto-Deploy**)
3. Each deploy runs `build.sh` (`migrate`, `seed_demo --reset`, `collectstatic`), then restarts Gunicorn

---

## Files reference

| File | Purpose |
|------|---------|
| `render.yaml` | Blueprint: web + Postgres + Redis |
| `build.sh` | Install deps + `migrate` + `seed_demo --reset` + `collectstatic` |
| `Procfile` | Gunicorn/Celery commands (reference) |
| `runtime.txt` | Python 3.13.0 |
| `requirements/prod.txt` | Production dependencies |
| `config/settings/production.py` | Production Django settings |

For Consult AI setup, see [CONSULT_AI_SETUP.md](CONSULT_AI_SETUP.md).

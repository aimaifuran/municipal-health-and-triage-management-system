# Municipal Health & Triage Management System (MHTMS)

Enterprise-grade municipal health and triage platform for local government clinics. Built with Django, DRF, PostgreSQL, Redis, Celery, HTMX, Alpine.js, and Tailwind CSS.

## Features

- **RBAC**: Super Admin, Doctor, Nurse, Receptionist, Public API Consumer
- **Anti-IDOR**: UUID-only URLs, clinic scoping, doctor-patient assignments
- **Security**: JWT with rotation/blacklist, django-axes, honeypot, CSP/HSTS, audit logging
- **Triage**: Smart priority scoring from vitals and symptoms
- **Bulk discharge**: Transaction-safe multi-patient discharge for doctors
- **Public API**: HIPAA-masked regional statistics only
- **Dashboards**: Role-based HTMX dashboards with live queue polling

## Architecture

```
config/          # Settings, URLs, Celery, WSGI
accounts/        # User, Clinic, assignments
patients/        # Patient demographics, documents
triage/          # Triage records, priority engine
consultations/   # Consultations, admit/discharge
analytics/       # Aggregated statistics
dashboard/       # Web UI views
auditlogs/       # Audit & login attempts
security/        # Permissions, middleware, honeypot
api/             # DRF v1 endpoints
common/          # Base models, mixins, validators
core/            # Template tags, error handlers
```

## Unlock login (django-axes lockout)

If you see *"Account locked: too many login attempts"*:

```bash
# Unlock everyone (local dev)
python manage.py unlock_login --all

# Unlock one email
python manage.py unlock_login --email=doctor@mhtms.gov.ph
```

Built-in axes commands also work: `python manage.py axes_reset`

## Quick Start (Development)

### Prerequisites

- Python 3.13+
- PostgreSQL 16+
- Redis 7+

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements/dev.txt
cp .env.example .env     # Edit values
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

### Sample test data

```bash
# Load / refresh all sample records (11 patients, triage, consultations)
python manage.py seed_demo

# Clear sample patients first, then re-seed
python manage.py seed_demo --reset
```

Includes **3 clinics** (Carigara, Barugo, Capoocan — Region VIII), **7 staff accounts**, **11 patients**, active **triage queues** (critical/moderate/stable), and **consultations** (some admitted for bulk-discharge testing).

### Demo Accounts

| Email | Role | Password |
|-------|------|----------|
| admin@mhtms.gov.ph | Super Admin | DemoPass123! |
| doctor@mhtms.gov.ph | Doctor (Carigara) | DemoPass123! |
| doctor2@mhtms.gov.ph | Doctor (Barugo) | DemoPass123! |
| nurse@mhtms.gov.ph | Nurse (Carigara) | DemoPass123! |
| nurse2@mhtms.gov.ph | Nurse (Barugo) | DemoPass123! |
| reception@mhtms.gov.ph | Receptionist | DemoPass123! |
| reception2@mhtms.gov.ph | Receptionist (Barugo) | DemoPass123! |

## Environment Variables

See [`.env.example`](.env.example) for all variables. **Never commit `.env` to version control.**

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL URL (production) |
| `REDIS_URL` | Redis cache/broker |
| `CLOUDINARY_*` | Media storage |
| `DEBUG` | Must be `False` in production |
| `OPENAI_API_KEY` | Consult AI on doctor queue ([setup guide](docs/CONSULT_AI_SETUP.md)) |

## API Documentation

- Swagger UI: `/api/docs/`
- OpenAPI schema: `/api/schema/`
- Postman collection: [`docs/postman/MHTMS_API.postman_collection.json`](docs/postman/MHTMS_API.postman_collection.json)

### Authentication

```http
POST /api/v1/auth/login/
Content-Type: application/json

{"email": "doctor@mhtms.gov.ph", "password": "DemoPass123!"}
```

Use `Authorization: Bearer <access_token>` for protected endpoints.

### Public Masked Endpoint

```http
GET /api/v1/public/health-stats/?region=Region+VII
```

Returns aggregated data only; PHI fields are `"HIPAA Restricted"`.

## Deployment (Render)

Full step-by-step guide: **[docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md)**

Quick overview:

1. Push this repository to GitHub
2. Render Dashboard → **New** → **Blueprint** → select the repo (`render.yaml`)
3. Set `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and Cloudinary credentials on `mhtms-web`
4. After deploy: `python manage.py seed_demo` in Render Shell (optional demo data)

`DEBUG` is **always False** in production settings.

## Security

- UUID primary keys (no integer IDs in URLs)
- Object-level permissions and clinic filtering
- Argon2 password hashing
- Brute-force lockout via django-axes
- Separate audit and security log streams
- CI runs Bandit, pip-audit, and `manage.py check --deploy`

## Testing

```bash
pytest
black .
isort .
flake8 .
bandit -r . -x ./tests
```

## License

Proprietary — Municipal Government Use

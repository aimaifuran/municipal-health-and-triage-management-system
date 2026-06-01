# Consult AI (OpenAI / ChatGPT) setup

The **Consult AI** button on the Doctor Dashboard consultation modal sends de-identified clinical context from the active patient and triage record to OpenAI and returns draft **Diagnosis**, **Treatment**, **Prescription**, and **Consultation notes**. The attending physician must review and edit every field before saving.

## Prerequisites

- An [OpenAI](https://platform.openai.com/) account with billing enabled (API usage is paid per token).
- This project already uses `httpx` to call the OpenAI Chat Completions API.

## Step 1: Create an OpenAI API key

1. Sign in at [https://platform.openai.com/](https://platform.openai.com/).
2. Open **API keys** (profile menu → **API keys**, or [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)).
3. Click **Create new secret key**.
4. Name it (e.g. `mhtms-dev`) and copy the key immediately (`sk-...`). You will not see it again.

Keep the key secret. Never commit it to git or paste it in chat logs.

## Step 2: Add environment variables

In your project root, edit `.env` (create from `.env.example` if needed):

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=60
```

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Secret key from OpenAI |
| `OPENAI_MODEL` | No | Model id (default: `gpt-4o-mini`). Alternatives: `gpt-4o`, `gpt-4.1-mini`, etc. |
| `OPENAI_TIMEOUT_SECONDS` | No | HTTP timeout in seconds (default: `60`) |

Restart the Django development server after changing `.env`.

## Step 3: Verify locally

1. Log in as a doctor (e.g. `doctor@mhtms.gov.ph` after `python manage.py seed_demo`).
2. Open **Active Patient Queue** → **Consult** on a patient with triage vitals.
3. Click **Consult AI** (top right of the consultation section).
4. After a few seconds, the four fields should populate with a draft and a yellow disclaimer banner.

If the key is missing, you will see: *OpenAI API key is not configured.*

## Step 4: Production deployment

1. Set `OPENAI_API_KEY` in your host’s secret store (Render, Railway, Azure, etc.) — not in the repository.
2. Restrict API key permissions in OpenAI if your org supports scoped keys.
3. Set usage limits and alerts under OpenAI **Settings → Limits** to control cost.
4. Ensure outbound HTTPS to `api.openai.com` is allowed from the app server.

## Cost and privacy notes

- Each click sends patient clinical data (name, demographics, vitals, symptoms) to OpenAI. Ensure this aligns with your clinic’s privacy policy and any applicable regulations (e.g. Data Privacy Act of 2012 in the Philippines).
- Consider using OpenAI’s [data usage policies](https://openai.com/policies) and, for production, enterprise agreements if required.
- Drafts are **not** auto-saved; only **Save consultation** / **Move to awaiting discharge** writes to the database.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| API key not configured | Set `OPENAI_API_KEY` in `.env` and restart the server |
| Invalid API key | Regenerate key in OpenAI dashboard; update `.env` |
| Rate limit | Wait and retry; upgrade OpenAI tier or reduce usage |
| Timeout | Increase `OPENAI_TIMEOUT_SECONDS` or use a faster model |
| Empty or invalid JSON | Retry; if persistent, switch model to `gpt-4o` |
| Could not reach OpenAI / SSL certificate | See [SSL on Windows](#ssl-certificate-errors-on-windows) below |

### SSL certificate errors on Windows

If you see **Could not reach OpenAI** or **SSL certificate verify failed**, Python on Windows often cannot find trusted CA certificates.

1. Install/update dependencies (includes `truststore` so Python uses Windows trusted certificates):

   ```powershell
   pip install -r requirements/dev.txt
   ```

2. Restart `python manage.py runserver`.

3. Test from the project folder (replace with your key or omit the header — any non-SSL error means TLS works):

   ```powershell
   python -c "import truststore; truststore.inject_into_ssl(); import httpx; r=httpx.get('https://api.openai.com/v1/models', timeout=15); print(r.status_code)"
   ```

   Status `401` or `200` means HTTPS works. If SSL still fails, try another network or check antivirus HTTPS scanning.

4. **Do not** disable SSL verification in production (`verify=False`).

## Optional: disable Consult AI

Remove or leave `OPENAI_API_KEY` empty. The button remains visible but requests will fail with a clear configuration message.

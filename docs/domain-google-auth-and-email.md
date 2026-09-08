# Domain, Google Sign-In & Transactional Email — Setup Runbook

How to take Kio from `localhost` to a real domain with working Google sign-in and
delivered verification / password-reset emails.

The application code for all three is already written. Everything below is
**account setup, DNS, and environment variables** — no code changes required.

---

## 0. Why this order

| Step | Blocks | Reason |
|------|--------|--------|
| 1. Buy domain | 2, 3 | Email deliverability requires DNS records on a domain you own |
| 2. Resend + DNS | Real email delivery | Resend refuses to send from an unverified domain |
| 3. Google Console | Google sign-in in prod | Authorized origins must name your real domain |

Google sign-in also works on `http://localhost:5173` with no domain at all, so you
can test it today. Email works locally too — with `EMAIL_PROVIDER=noop` the link
is written to the backend log instead of being sent.

---

## 1. Buy the domain

Any registrar works (Cloudflare, Namecheap, Porkbun, Google Domains → Squarespace).
Cloudflare is the easiest to live with because DNS management is free and fast to
propagate.

**Before you buy, check the name is clear of an existing trademark** — Kio is a
short, common-looking word and you'll be putting it on school contracts.

### Suggested subdomain layout

| Host | Points at | Used for |
|------|-----------|----------|
| `app.yourdomain.com` | Frontend (Vercel/Netlify/S3+CDN) | What users open |
| `api.yourdomain.com` | Backend (FastAPI/uvicorn) | `VITE_API_BASE_URL` |
| `send.yourdomain.com` | Resend (MX/TXT only) | Bounce handling for outbound mail |
| `yourdomain.com` | Marketing site or redirect to `app.` | — |

Keeping the app on `app.` rather than the apex means you can move hosting later by
changing one CNAME.

---

## 2. Transactional email (Resend)

### 2a. Create the account and add your domain

1. Sign up at <https://resend.com>.
2. **Domains → Add Domain** → enter `yourdomain.com` (Resend will suggest the
   `send.` subdomain for the return path).
3. Resend shows you a set of DNS records to add. Typically:

   | Type | Purpose |
   |------|---------|
   | `TXT` on `send.yourdomain.com` | **SPF** — authorizes Resend's servers to send as you |
   | `TXT` on `resend._domainkey.yourdomain.com` | **DKIM** — cryptographically signs your mail |
   | `MX` on `send.yourdomain.com` | Bounce/complaint handling |

   > Copy the exact values from the Resend dashboard — don't retype them from
   > this doc or anywhere else. DKIM keys are per-account.

4. Add a **DMARC** record too. Resend doesn't require it, but Gmail and Yahoo now
   expect one from bulk senders, and without it your mail is far more likely to be
   filtered:

   ```
   Type: TXT
   Name: _dmarc
   Value: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
   ```

   Start at `p=none` (monitor only). Move to `p=quarantine` once the reports show
   your legitimate mail is passing.

5. Click **Verify** in Resend. DNS usually propagates in minutes; allow up to a
   few hours.

### 2b. Get an API key

**API Keys → Create API Key** with *Sending access*. Copy it once — it isn't shown
again. It goes in `RESEND_API_KEY`.

### 2c. Point the backend at it

```env
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=Kio <noreply@yourdomain.com>
EMAIL_REPLY_TO=support@yourdomain.com
FRONTEND_URL=https://app.yourdomain.com
```

`EMAIL_FROM` **must** be on the verified domain. `FRONTEND_URL` is what gets baked
into every link in every email — if it's wrong, users click through to nothing.

### Safety net

If `EMAIL_PROVIDER=resend` but `RESEND_API_KEY` is blank, the service logs a
warning and falls back to `noop` rather than crashing. A send that fails is logged
and swallowed — a bounced email can never turn a successful signup into a 500.

### Before your domain verifies

Resend's shared sender `onboarding@resend.dev` works immediately but **only
delivers to the email address that owns the Resend account**. Useful for one
end-to-end smoke test, useless for real users.

---

## 3. Google Sign-In

Kio uses the Google Identity Services **ID-token** flow. That means you configure
**Authorized JavaScript origins** — there are no redirect URIs to set.

### 3a. Create the OAuth client

1. Open <https://console.cloud.google.com> → create a project (e.g. "Kio").
2. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - App name: `Kio`, support email, logo, and your homepage/privacy/terms URLs
   - Scopes: `openid`, `email`, `profile` only. These are **non-sensitive**, so
     you do not need to go through Google's app-verification review.
   - **Publish the app.** While it's in *Testing* mode only explicitly listed test
     users can sign in, capped at 100.
3. **Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized JavaScript origins:
     ```
     http://localhost:5173
     https://app.yourdomain.com
     ```
   - Leave *Authorized redirect URIs* empty.
4. Copy the **Client ID** (ends in `.apps.googleusercontent.com`).

### 3b. Configure both sides

The same client ID goes in two places — they must match, or every sign-in fails
with an audience error:

```env
# backend/.env
GOOGLE_CLIENT_ID=1234567890-abcdef.apps.googleusercontent.com

# frontend .env.local / .env.production
VITE_GOOGLE_CLIENT_ID=1234567890-abcdef.apps.googleusercontent.com
```

`GOOGLE_CLIENT_SECRET` is not needed for this flow — the setting exists only for a
future server-side auth-code flow.

### Notes

- Leaving both blank is a supported state: the "Continue with Google" button is
  hidden and `/auth/google` returns 503. Nothing breaks.
- Google origins must be **https** in production. `localhost` is the only
  exception Google makes.
- Google accounts arrive with `is_verified=true` — Google already proved the
  address, so those users never see the verification banner.

---

## 4. Environment matrix

### Backend (`backend/.env`)

| Variable | Local | Production |
|----------|-------|------------|
| `ENVIRONMENT` | `development` | `production` |
| `JWT_SECRET_KEY` | dev default | **random 64-char secret** — the app refuses to boot in production with the dev default |
| `DATABASE_URL` | local Postgres | managed Postgres URL |
| `FRONTEND_URL` | `http://localhost:5173` | `https://app.yourdomain.com` |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | `["https://app.yourdomain.com"]` |
| `EMAIL_PROVIDER` | `noop` | `resend` |
| `RESEND_API_KEY` | *(blank)* | `re_…` |
| `EMAIL_FROM` | default | `Kio <noreply@yourdomain.com>` |
| `GOOGLE_CLIENT_ID` | client ID | same client ID |
| `GEMINI_API_KEY` | your key | your key |

### Frontend (`.env.local` / host env)

| Variable | Local | Production |
|----------|-------|------------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | `https://api.yourdomain.com` |
| `VITE_GOOGLE_CLIENT_ID` | client ID | same client ID |

> `VITE_*` variables are inlined **at build time**, not read at runtime. Changing
> one means rebuilding and redeploying the frontend — restarting it is not enough.

---

## 5. Smoke test

Run through this once against production before letting real users in.

**Email verification**
1. Sign up with a real address you can read.
2. The email arrives from `noreply@yourdomain.com` — check it lands in **Inbox**,
   not Spam.
3. The signed-in app shows the amber "Please verify your email" banner.
4. Click the link → `/verify-email` shows success → banner disappears.
5. Click the same link again → still succeeds (verification is idempotent).

**Password reset**
1. `/forgot-password` with a real account → email arrives.
2. Submit a new password at `/reset-password` → redirected to sign in.
3. Old password is rejected; new password works.
4. Re-open the **same** reset link → rejected. Links are single-use.
5. `/forgot-password` with an address that has no account → same generic success
   message, no email sent. (This is deliberate: the endpoint must not reveal which
   addresses are registered.)

**Google**
1. "Continue with Google" appears on `/login`.
2. New Google user → asked only for mobile + institution code.
3. Returning Google user → straight to their dashboard, no verification banner.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No email, log says `[email:noop] would send` | `EMAIL_PROVIDER` isn't `resend`, or `RESEND_API_KEY` is blank | Set both; restart the backend |
| `Resend rejected the message (HTTP 403)` | `EMAIL_FROM` domain isn't verified in Resend | Finish DNS verification, or send to your own address via `onboarding@resend.dev` |
| Emails land in Spam | Missing DKIM/SPF/DMARC, or a brand-new domain with no sending reputation | Verify all DNS records; warm up gradually; keep `p=none` at first |
| Email links point at `localhost` | `FRONTEND_URL` not set in production | Set it and restart |
| Google button missing | `VITE_GOOGLE_CLIENT_ID` empty in the **build** | Set it and rebuild — it's inlined at build time |
| `Invalid Google credential` (401) | Frontend and backend client IDs differ | Make them identical |
| Google popup: "origin not allowed" | Origin missing from Authorized JavaScript origins | Add the exact scheme+host+port |
| Only some Google users can sign in | Consent screen still in *Testing* | Publish to Production |
| Backend won't start in production | `JWT_SECRET_KEY` is still the dev default | Set a strong secret (this guard is intentional) |

---

## Related

- `docs/safety-sla-and-escalation.md` — risk response SLAs
- `backend/.env.example`, `.env.example` — the full variable lists
- `backend/tests/test_auth_email.py` — verification & reset behaviour, including
  the no-enumeration and single-use guarantees

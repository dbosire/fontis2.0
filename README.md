Fontis Springs: Moving to Production
This is Phase 9–10 of the migration: cutting the Django app over from the fontis_springs_staging database to the real fontis_springs production database, and retiring the PHP app. Follow it in order — each section depends on the one before it.

0. Before you start
 All modules validated side-by-side against the live PHP app (Phase 8 — already done)
 Pick a cutover window (low-traffic time) — writes to fontis_springs must pause briefly during the switch
 Full backup of fontis_springs (the real DB, not staging)
mysqldump -u root fontis_springs > fontis_springs_pre_cutover_backup.sql
Keep this backup untouched until you're confident the cutover succeeded — it's your rollback path.

1. Server prerequisites
The app currently runs on Windows (XAMPP box). Confirm the production host has:

Python 3.13 + the project's venv (or rebuild it: python -m venv venv && venv\Scripts\pip install -r requirements.txt)
MySQL reachable at whatever DB_HOST/DB_PORT production will use
Node.js (for the one-time Tailwind production build — NPM_BIN_PATH in .env)
The legacy PHP app's uploads/ directory present at the path MEDIA_ROOT expects (fontis/settings/base.py:118: BASE_DIR.parent / "fontis") — Django serves the same upload files the PHP app wrote, it doesn't duplicate them
The ML microservice(s) already running and reachable — ML_SERVICE_V1_URL / ML_SERVICE_V2_URL in .env point at 127.0.0.1:8000 / :8010 by default. If those FastAPI services aren't already running as their own process on the production box, the ML Predictor pages will fail. Standing them up is outside this codebase.
2. Production .env
Copy .env to the production host and change these values — do not reuse the staging .env as-is:

Variable	Change to
DJANGO_SECRET_KEY	A new, unique key — generate with python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())". Never reuse the dev key.
DJANGO_DEBUG	False (only matters if anything still imports base.py directly — production.py already hardcodes DEBUG = False)
DJANGO_ALLOWED_HOSTS	The real domain(s), e.g. app.fontissprings.co.ke — not localhost,127.0.0.1
DB_NAME	fontis_springs (the real DB — not _staging)
DB_USER / DB_PASSWORD	Production DB credentials, ideally a dedicated app user rather than root
EMAIL_BACKEND	Switch off the console backend to django.core.mail.backends.smtp.EmailBackend, and fill in EMAIL_HOST / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD — CRM email is currently just printing to console
MPESA_ENV	production once you have live Daraja credentials (currently sandbox)
MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET / MPESA_SHORTCODE / MPESA_TILL_NUMBER / MPESA_PASSKEY	Live values from the Daraja production app. MPESA_SHORTCODE identifies the org to Daraja (BusinessShortCode); MPESA_TILL_NUMBER is the actual Buy Goods till customers pay (PartyB, shown as the Till Number) — both currently blank, must be set
MPESA_CALLBACK_BASE_URL	The real public HTTPS URL Daraja will call back to, e.g. https://app.fontissprings.co.ke — must be HTTPS, Daraja rejects plain HTTP callbacks in production
SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE	True, once a reverse proxy terminating TLS is in front of the app (see §4)
SECURE_HSTS_SECONDS	e.g. 31536000 once HTTPS is confirmed working end-to-end — don't set this before TLS is live, it can lock out plain-HTTP access
CSRF_TRUSTED_ORIGINS	https://app.fontissprings.co.ke (comma-separated if there's more than one host)
Also rotate SMS_API_TOKEN before production use — the current value was printed in a recent debugging session and should be treated as compromised.

Run manage.py check --deploy once the .env is in place, from a shell with DJANGO_SETTINGS_MODULE=fontis.settings.production:

set DJANGO_SETTINGS_MODULE=fontis.settings.production
venv\Scripts\python.exe manage.py check --deploy
This flags any remaining insecure defaults (missing HSTS, cookies not secure, etc.) against the real production settings.

3. Database
fontis/settings/production.py points at fontis_springs (not _staging) once DB_NAME=fontis_springs is set. Apply every migration this migration itself has produced during the Django rewrite — including the two from the Commission Module just built:

venv\Scripts\python.exe manage.py migrate
Run this against fontis_springs directly (not a copy) — at this point in the cutover there should be no live PHP writes happening (see §6), so it's safe. Confirm with:

venv\Scripts\python.exe manage.py showmigrations
Every app should show all migrations checked off, including commissions and employees.0005_payroll_commission_earned_and_more.

4. Static files, WSGI server, and reverse proxy
Build Tailwind for production (minified, not the dev watcher):

venv\Scripts\python.exe manage.py tailwind build
Collect static files — whitenoise serves them with CompressedManifestStaticFilesStorage (fontis/settings/base.py:109), so this step is required, not optional:

venv\Scripts\python.exe manage.py collectstatic --noinput
Run the app under Waitress (already in requirements.txt, matches the HTTPS-header comment in production.py) instead of manage.py runserver:

venv\Scripts\waitress-serve.exe --host=127.0.0.1 --port=8001 --call fontis.wsgi:application
Wrap this as a Windows service (e.g. with NSSM) so it restarts on reboot/crash, rather than running it in a console window.

Put a reverse proxy in front of Waitress (IIS with URL Rewrite, or nginx) to terminate TLS. This is required, not optional, for two reasons specific to this app:

Daraja mechanically rejects non-HTTPS M-Pesa callback URLs
The public M-Pesa payment page (/pay/<token>/) carries phone numbers over the wire and needs a secure origin for SESSION_COOKIE_SECURE/CSRF_COOKIE_SECURE to make sense
The proxy should forward X-Forwarded-Proto: https — production.py already has SECURE_PROXY_SSL_HEADER set to read it. Once the proxy is live, flip the SECURE_SSL_REDIRECT / SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE env vars from §2.

5. Application-level setup (one-time, on the production DB)
 Create a real superuser: venv\Scripts\python.exe manage.py createsuperuser
 Log in and configure System → Settings (system_info) — company name, logo, any site-wide config the PHP app had
 Configure Finance → Finance Settings (AccountMapping) — chart-of-accounts wiring. This is currently unset even in staging (confirmed while testing the Commission Module's GL posting), so payroll/sales/expense postings will silently no-op until it's filled in
 Set up Employee Management → Roles & Permissions for real staff accounts — don't run production with everyone as superuser
 Verify Mobile Money → Reconciliation picks up real Daraja traffic once MPESA_ENV=production is live (test with a small real transaction before wide rollout)
6. Cutover sequence
Announce the maintenance window; put the PHP app in read-only or maintenance mode so no new writes land in fontis_springs mid-cutover.
Take the backup from §0 if you haven't already (a fresh one, right before cutover).
Run manage.py migrate against fontis_springs (§3).
Start the Django app under Waitress behind the reverse proxy (§4), pointed at fontis_springs.
Smoke-test critical paths directly against production data: log in, view Sales list, generate one Payroll (don't mark it Paid yet), view Finance → Trial Balance, submit one M-Pesa STK push on a test amount.
Switch DNS / load balancer / IIS site binding from the PHP app to the Django app.
Keep the PHP app installed but stopped (not deleted) for a rollback window — a few days to a week, per your risk tolerance.
7. Rollback plan
If something's wrong post-cutover: switch DNS/routing back to the PHP app, restore fontis_springs from the §0/§6 backup if the Django app wrote bad data, and investigate offline against fontis_springs_staging (never against production) before retrying.

8. Post-cutover cleanup (Phase 10)
 Monitor error logs for the first few days (Waitress + Django logging — none is currently configured beyond console output; consider adding a LOGGING config with file rotation before cutover, not after)
 Confirm fontis_springs_staging is still being used for all future dev/test work (per the existing team discipline) — never test against fontis_springs again
 Once confident, decommission the PHP app and its web server config
 Set up regular fontis_springs backups (this migration didn't add automated backups — whatever cron/scheduled task backed up the PHP-era DB should keep running, just double check it's still pointed at the right DB name)
 Revisit SMS_API_TOKEN rotation (flagged in §2) if not already done

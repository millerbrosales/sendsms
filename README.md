# Miller Bros SMS MVP

A small FastAPI app for:

- importing MBX sales data from CSV
- normalizing US phone numbers
- preventing obvious duplicate imports
- scheduling a welcome SMS, pre-install reminder, and post-install follow-up
- sending through a Twilio Messaging Service
- receiving inbound SMS into the dashboard
- storing Twilio delivery-status updates
- hosting on Railway + PostgreSQL

## Important before production

1. Use only customers whose consent matches your approved A2P campaign.
2. Edit the message templates in `app/messaging.py` so they exactly match your intended/approved use case.
3. Register the 573 number under the correct A2P 10DLC campaign / Messaging Service.
4. Set a strong `APP_PASSWORD` and `SESSION_SECRET`.
5. This MVP stores customer data. Treat the app and Railway account as sensitive.

## Expected CSV columns

The importer auto-detects several common names.

Required:
- customer name
- phone number

Recommended:
- install date
- rep name
- order/account ID

Examples it recognizes:
- `Customer Name`, `Name`, `Subscriber Name`
- `Phone`, `Phone Number`, `Mobile`
- `Rep`, `Sales Rep`, `Salesperson`
- `Install Date`, `Scheduled Install Date`
- `Order ID`, `Account Number`, `Sale ID`

If MBX uses different headers, edit `ALIASES` in `app/csv_import.py`.

## Run locally

```bash
cp .env.example .env
pip install -r requirements.txt
set -a; source .env; set +a
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

To process due messages manually:

```bash
python -m app.worker
```

## Railway deployment

### 1. Put this project in GitHub

Create a new private GitHub repo and upload these files.

### 2. Create Railway project

- New Project
- Deploy from GitHub Repo
- choose the repo
- Railway will detect the Dockerfile

### 3. Add PostgreSQL

Inside the same Railway project:
- click `+ New`
- add PostgreSQL

Railway exposes a `DATABASE_URL`. Reference/add that variable to the web service.

### 4. Add variables to the web service

Copy the names from `.env.example` into Railway Variables:

- `DATABASE_URL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_MESSAGING_SERVICE_SID`
- `APP_PASSWORD`
- `SESSION_SECRET`
- `DEFAULT_COUNTRY=US`
- `APP_TIMEZONE=America/Chicago`
- `WELCOME_DELAY_MINUTES=1`
- `REMINDER_DAYS_BEFORE=2`
- `FOLLOWUP_DAYS_AFTER=1`
- `MESSAGE_HOUR_LOCAL=10`

Do not commit real secrets to GitHub.

### 5. Generate a Railway public domain

Generate a public domain for the web service.

You should then have something similar to:

`https://your-app.up.railway.app`

Test:

`https://your-app.up.railway.app/health`

### 6. Create a Railway cron service

Create another service from the SAME GitHub repo.

Override its start command with:

```bash
python -m app.worker
```

Give it the same database and Twilio variables.

Configure its cron schedule:

```cron
*/5 * * * *
```

Railway cron schedules use UTC. This worker itself only checks timestamps already stored in UTC, so that is fine.

### 7. Twilio inbound webhook

In the Messaging Service / 573 sender configuration, point inbound messages to:

`https://YOUR-RAILWAY-DOMAIN/twilio/inbound`

Use HTTP POST.

### 8. Twilio delivery status callback

Set your Messaging Service Delivery Status Callback to:

`https://YOUR-RAILWAY-DOMAIN/twilio/status`

The app sends via `messaging_service_sid`, so service-level callbacks can be used.

## First safe test

Do NOT start with a live MBX export.

Create a CSV with only your own phone number:

```csv
Order ID,Customer Name,Phone,Rep,Install Date
TEST-001,Noah,+15735551234,Noah,08/30/2026
```

Upload it. Confirm:
- customer appears
- messages are scheduled
- worker sends the welcome
- Twilio status updates arrive
- replying to the 573 number appears under Recent replies

Only then test a small consented customer batch.

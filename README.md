# SAP Outreach — GitHub Repo Structure

## How it works

1. Open the SAP Outreach Agent (browser)
2. Paste contacts, generate emails, review and approve
3. Export CSV — drop it into `outreach/queue/`
4. GitHub Action runs automatically at 9am ET Mon-Fri
5. Sends 1 email every 2 minutes up to the daily cap
6. Moves processed files to `outreach/sent/` with results
7. Logs every send to `outreach/logs/`

## Folder structure

```
outreach/
  queue/       ← Drop export CSVs here before 9am
  sent/        ← Processed files land here with results
  logs/        ← Daily send logs
send_emails.py ← Send script
.github/
  workflows/
    send_outreach.yml ← GitHub Action (runs 9am ET Mon-Fri)
```

## GitHub Secrets required

Go to repo Settings → Secrets and variables → Actions → New repository secret

| Secret     | Value                          |
|------------|-------------------------------|
| SMTP_USER  | mhandy@sponsorapurpose.org    |
| SMTP_PASS  | Morgan's Office 365 password  |

## Daily cap schedule (increase weekly)

| Week | Cap |
|------|-----|
| 1    | 50  |
| 2    | 75  |
| 3    | 100 |
| 4    | 150 |
| 5+   | 200 |

To increase the cap: edit `DAILY_CAP = 50` in `send_emails.py`

## US Holidays (auto-skipped)

Memorial Day, Independence Day, Labor Day, Thanksgiving,
Christmas, New Year's Day, MLK Day, Presidents Day,
Columbus Day, Veterans Day

Update the `US_HOLIDAYS` set in `send_emails.py` each January.

## CSV format (export from SAP Outreach Agent)

```
from, to, to_name, org, sequence, processor, subject, body
```

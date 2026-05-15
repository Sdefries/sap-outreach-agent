"""
SAP Outreach — Email Send Script
Reads queue CSV, checks holidays, sends via Office 365 SMTP
1 email every 2 minutes, 50/day cap (increase DAILY_CAP weekly)
"""

import csv
import smtplib
import logging
import os
import time
from datetime import date, datetime
from email.mime.text import MIMEText
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────
SMTP_HOST   = "smtp.office365.com"
SMTP_PORT   = 587
SMTP_USER   = os.environ.get("SMTP_USER", "mhandy@sponsorapurpose.org")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")
FROM_NAME   = "Morgan Handy"

DAILY_CAP   = 50          # Increase weekly: 50 → 75 → 100 → 150 → 200
STAGGER_SEC = 120         # 2 minutes between sends

QUEUE_DIR   = Path("outreach/queue")
SENT_DIR    = Path("outreach/sent")
LOG_DIR     = Path("outreach/logs")

# ── US Federal Holidays (update annually) ───────────────────────
US_HOLIDAYS = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents Day
    date(2026, 5, 25),  # Memorial Day
    date(2026, 7, 4),   # Independence Day
    date(2026, 9, 7),   # Labor Day
    date(2026, 10, 12), # Columbus Day
    date(2026, 11, 11), # Veterans Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
    date(2027, 1, 1),   # New Year's Day 2027
}

# ── Logging ──────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
SENT_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / f"send_{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def is_holiday(d: date) -> bool:
    return d in US_HOLIDAYS


def is_weekday(d: date) -> bool:
    return d.weekday() < 5  # Mon=0 ... Fri=4


def send_one(to_email: str, to_name: str, subject: str, body: str) -> bool:
    """Send a single plain-text email via Office 365 SMTP."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = to_email
    msg["Reply-To"] = SMTP_USER

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())
        return True
    except smtplib.SMTPRecipientsRefused:
        log.error(f"Recipient refused: {to_email}")
        return False
    except smtplib.SMTPAuthenticationError:
        log.critical("SMTP authentication failed — check SMTP_USER and SMTP_PASS secrets")
        raise
    except Exception as e:
        log.error(f"Send failed to {to_email}: {e}")
        return False


def process_queue_file(queue_file: Path, sent_count: int) -> tuple[int, list]:
    """Process one queue CSV file. Returns (emails_sent, results_rows)."""
    results = []

    with open(queue_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    for row in rows:
        if sent_count >= DAILY_CAP:
            log.info(f"Daily cap of {DAILY_CAP} reached. Stopping.")
            results.append({**row, "send_status": "cap_reached", "sent_at": ""})
            continue

        to_email = row.get("to", "").strip()
        to_name  = f"{row.get('to_name', '').strip()}"
        subject  = row.get("subject", "").strip()
        body     = row.get("body", "").replace("\\n", "\n").strip()

        if not to_email or not subject or not body:
            log.warning(f"Skipping incomplete row: {row}")
            results.append({**row, "send_status": "skipped_incomplete", "sent_at": ""})
            continue

        log.info(f"Sending {sent_count + 1}/{DAILY_CAP} → {to_email} ({to_name})")
        success = send_one(to_email, to_name, subject, body)

        if success:
            sent_count += 1
            sent_at = datetime.now().isoformat()
            results.append({**row, "send_status": "sent", "sent_at": sent_at})
            log.info(f"✓ Sent to {to_email}")

            # Stagger — wait 2 minutes between sends (skip after last)
            if sent_count < DAILY_CAP:
                log.info(f"Waiting {STAGGER_SEC}s before next send...")
                time.sleep(STAGGER_SEC)
        else:
            results.append({**row, "send_status": "failed", "sent_at": ""})

    return sent_count, results


def archive_queue_file(queue_file: Path, results: list):
    """Move processed queue file to sent folder with results appended."""
    timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M")
    sent_file  = SENT_DIR / f"{queue_file.stem}_{timestamp}_results.csv"

    if not results:
        return

    fieldnames = list(results[0].keys())
    with open(sent_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    queue_file.unlink()
    log.info(f"Archived to {sent_file}")


def main():
    today = date.today()
    log.info(f"SAP Outreach Send Script — {today}")

    # Check weekday
    if not is_weekday(today):
        log.info("Weekend — skipping send.")
        return

    # Check holiday
    if is_holiday(today):
        log.info(f"US Holiday — skipping send for {today}.")
        return

    # Check credentials
    if not SMTP_PASS:
        log.critical("SMTP_PASS not set. Add it to GitHub Secrets as SMTP_PASS.")
        return

    # Find queue files
    queue_files = sorted(QUEUE_DIR.glob("*.csv"))
    if not queue_files:
        log.info("No files in outreach/queue/ — nothing to send today.")
        return

    log.info(f"Found {len(queue_files)} queue file(s). Daily cap: {DAILY_CAP}")
    total_sent = 0

    for queue_file in queue_files:
        if total_sent >= DAILY_CAP:
            log.info("Cap reached — skipping remaining files.")
            break

        log.info(f"Processing: {queue_file.name}")
        total_sent, results = process_queue_file(queue_file, total_sent)
        archive_queue_file(queue_file, results)

    log.info(f"Done. Total sent today: {total_sent}/{DAILY_CAP}")


if __name__ == "__main__":
    main()

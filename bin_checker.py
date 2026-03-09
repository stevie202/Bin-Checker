#!/usr/bin/env python3
import os, re, smtplib, schedule, time, logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ADDRESS_SEARCH = os.getenv("BIN_ADDRESS",    "79 Redhill Road")
EMAIL_FROM     = os.getenv("EMAIL_FROM",     "your_email@gmail.com")
EMAIL_TO       = os.getenv("EMAIL_TO",       "your_email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
SMTP_HOST      = os.getenv("SMTP_HOST",      "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT",  "587"))
RUN_NOW        = os.getenv("RUN_NOW",        "false").lower() == "true"
COUNCIL_URL    = "https://www.lisburncastlereagh.gov.uk/w/collection-days-and-holiday-information"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BIN_EMOJI = {"brown": "🟤", "recycle": "♻️", "residual": "🗑️"}

def get_bin_emoji(name):
    for k, e in BIN_EMOJI.items():
        if k in name.lower(): return e
    return "🗂️"

def fetch_bin_info():
    log.info("Launching browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(COUNCIL_URL, wait_until="networkidle", timeout=30_000)
        log.info("Page loaded.")

        # Log ALL inputs found on page
        inputs = page.locator("input").all()
        log.info(f"Total inputs found: {len(inputs)}")
        for i, inp in enumerate(inputs):
            log.info(f"  [{i}] type={inp.get_attribute('type')} id={inp.get_attribute('id')} name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')}")

        # Log full page HTML
        html = page.content()
        log.info("=== PAGE HTML (first 3000 chars) ===")
        log.info(html[:3000])
        log.info("=====================================")

        # Save debug files
        page.screenshot(path="debug_initial.png", full_page=True)
        with open("debug_initial.html", "w", encoding="utf-8") as f:
            f.write(html)
        log.info("Saved debug_initial.png and debug_initial.html")

        browser.close()

    return {"address": ADDRESS_SEARCH, "date": "DEBUG RUN - check logs", "bins": []}

def send_email(info):
    today = datetime.now().strftime("%A %d %B %Y")
    bins_html = "".join(
        f"<li>{get_bin_emoji(b)} <strong>{b}</strong></li>" for b in info["bins"]
    ) or "<li>Could not determine bin type -- check website manually.</li>"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
      <h2>Bin Collection Reminder</h2>
      <p>Checked: <strong>{today}</strong></p>
      <p><strong>Address:</strong> {info["address"]}</p>
      <p><strong>Next collection:</strong> {info["date"]}</p>
      <p><strong>Put out tonight:</strong></p>
      <ul>{bins_html}</ul>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    recipients = [r.strip() for r in EMAIL_TO.split(",")]
    msg["Subject"] = f"Bin Day Tomorrow -- {info['date']}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        log.info(f"Email sent to {EMAIL_TO}")
    except Exception as e:
        log.error(f"Failed to send email: {e}")

def run_job():
    log.info("=" * 50)
    try:
        info = fetch_bin_info()
        send_email(info)
    except Exception as e:
        log.error(f"Job failed: {e}", exc_info=True)
        send_email({"address": ADDRESS_SEARCH, "date": "Could not retrieve", "bins": []})

if __name__ == "__main__":
    log.info(f"Started. Address: {ADDRESS_SEARCH}")
    if RUN_NOW:
        run_job()
    else:
        schedule.every().tuesday.at("18:30").do(run_job)
        while True:
            schedule.run_pending()
            time.sleep(30)

#!/usr/bin/env python3
"""
Bin Collection Day Checker
Scrapes lisburncastlereagh.gov.uk every Tuesday at 18:30 GMT
for 79 Redhill Road and sends an email notification.

Requirements:
    pip install playwright schedule
    playwright install chromium

Configuration:
    Set environment variables or edit the CONFIG section below.
"""

import os
import re
import smtplib
import schedule
import time
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────
# CONFIG — edit these or set as env variables
# ─────────────────────────────────────────────
ADDRESS_SEARCH  = os.getenv("BIN_ADDRESS",    "79 Redhill Road")
EMAIL_FROM      = os.getenv("EMAIL_FROM",     "your_email@gmail.com")
EMAIL_TO        = os.getenv("EMAIL_TO",       "your_email@gmail.com")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "your_app_password")   # Gmail App Password
SMTP_HOST       = os.getenv("SMTP_HOST",      "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT",  "587"))
RUN_NOW         = os.getenv("RUN_NOW",        "false").lower() == "true"  # set True to test immediately
COUNCIL_URL     = "https://www.lisburncastlereagh.gov.uk/w/collection-days-and-holiday-information"
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)


# ── Bin emojis ──────────────────────────────
BIN_EMOJI = {
    "brown":    "🟤",
    "recycle":  "♻️",
    "residual": "🗑️",
    "green":    "🟢",
    "blue":     "🔵",
}

def get_bin_emoji(bin_name: str) -> str:
    name_lower = bin_name.lower()
    for key, emoji in BIN_EMOJI.items():
        if key in name_lower:
            return emoji
    return "🗂️"


# ── Scraper ──────────────────────────────────
def fetch_bin_info() -> dict:
    """
    Opens the council page, searches for the address, selects the first
    result, and returns a dict with keys: address, date, bins (list of str).
    """
    log.info("Launching browser to scrape bin collection info...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ── Load page ──
        page.goto(COUNCIL_URL, wait_until="domcontentloaded", timeout=30_000)
        log.info("Page loaded.")

        # ── Find and fill the search box ──
        # The input is typically the first text input in the "Find your collection day" section
        search_input = page.locator("input[type='text'], input[type='search']").first
        search_input.wait_for(state="visible", timeout=10_000)
        search_input.fill(ADDRESS_SEARCH)
        search_input.press("Enter")
        log.info(f"Searched for: {ADDRESS_SEARCH}")

        # ── Wait for address suggestions to appear ──
        try:
            # Address results often appear as a list/dropdown beneath the search box
            page.wait_for_selector("ul li, .address-result, [class*='result'], [class*='suggestion']",
                                   timeout=8_000)
        except PWTimeout:
            # Fallback: wait a moment and try clicking any visible result
            page.wait_for_timeout(3_000)

        # ── Click the first address result ──
        result = page.locator("ul li, .address-result, [class*='result'], [class*='suggestion']").first
        result_text = result.inner_text()
        log.info(f"Selecting address: {result_text.strip()}")
        result.click()

        # ── Wait for bin collection info to load ──
        page.wait_for_timeout(3_000)

        # ── Grab full page text to parse ──
        content = page.locator("body").inner_text()
        browser.close()

    return _parse_bin_info(content, result_text.strip())


def _parse_bin_info(content: str, address: str) -> dict:
    """Parse the page text for next collection date and bin types."""
    result = {
        "address": address,
        "date":    "Unknown",
        "bins":    [],
        "raw":     content,
    }

    lines = content.splitlines()

    # Look for a Wednesday date pattern: "Wednesday, 12 March 2025" or similar
    date_pattern = re.compile(
        r"(Wednesday[,\s]+\d{1,2}\s+\w+\s+\d{4}|"
        r"Wednesday\s+\d{1,2}\s+\w+\s+\d{4}|"
        r"Wed\s+\d{1,2}\s+\w+\s+\d{4})",
        re.IGNORECASE
    )

    for line in lines:
        m = date_pattern.search(line)
        if m:
            result["date"] = m.group(0).strip()
            break

    # Look for bin types
    bin_keywords = {
        "BrownBin":    ["brown bin", "brownbin", "brown"],
        "RecycleBin":  ["recycle bin", "recyclebin", "recycling bin", "blue bin", "blue"],
        "ResidualBin": ["residual bin", "residualbin", "general waste", "black bin", "grey bin"],
    }

    content_lower = content.lower()
    for bin_name, keywords in bin_keywords.items():
        for kw in keywords:
            if kw in content_lower:
                result["bins"].append(bin_name)
                break

    # Deduplicate
    result["bins"] = list(dict.fromkeys(result["bins"]))

    log.info(f"Parsed → date: {result['date']}, bins: {result['bins']}")
    return result


# ── Email sender ─────────────────────────────
def send_email(info: dict):
    today = datetime.now().strftime("%A %d %B %Y")
    bins_html = "".join(
        f"<li style='padding:6px 0;font-size:1.1em;'>{get_bin_emoji(b)} <strong>{b}</strong></li>"
        for b in info["bins"]
    ) or "<li>⚠️ Could not determine bin type — check website manually.</li>"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
      <h2 style="color:#2d6a4f;">🗑️ Bin Collection Reminder</h2>
      <p style="color:#555;">Checked on <strong>{today}</strong></p>

      <table style="border-collapse:collapse;width:100%;">
        <tr>
          <td style="padding:8px;background:#f0f4f0;border-radius:6px;">
            <strong>📍 Address</strong><br>{info["address"]}
          </td>
        </tr>
        <tr><td style="height:10px;"></td></tr>
        <tr>
          <td style="padding:8px;background:#e8f5e9;border-radius:6px;">
            <strong>📅 Next collection</strong><br>
            <span style="font-size:1.2em;color:#1b5e20;">{info["date"]}</span>
          </td>
        </tr>
        <tr><td style="height:10px;"></td></tr>
        <tr>
          <td style="padding:8px;background:#fff3e0;border-radius:6px;">
            <strong>🪣 Put out tonight:</strong>
            <ul style="margin:8px 0 0 0;padding-left:20px;">
              {bins_html}
            </ul>
          </td>
        </tr>
      </table>

      <p style="font-size:0.8em;color:#aaa;margin-top:24px;">
        Auto-generated by bin_checker.py •
        <a href="{COUNCIL_URL}">Lisburn & Castlereagh Council</a>
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    recipients = [r.strip() for r in EMAIL_TO.split(",")]

    msg["Subject"] = f"🗑️ Bin Day Tomorrow — {info['date']}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        log.info(f"✅ Email sent to {EMAIL_TO}")
    except Exception as e:
        log.error(f"❌ Failed to send email: {e}")


# ── Main job ─────────────────────────────────
def run_job():
    log.info("=" * 50)
    log.info("Running bin collection check...")
    try:
        info = fetch_bin_info()
        send_email(info)
    except Exception as e:
        log.error(f"Job failed: {e}", exc_info=True)
        # Send a fallback error email
        send_email({
            "address": ADDRESS_SEARCH,
            "date":    "⚠️ Could not retrieve — check site manually",
            "bins":    [],
        })


# ── Scheduler ────────────────────────────────
if __name__ == "__main__":
    log.info("Bin Checker started.")
    log.info(f"Address   : {ADDRESS_SEARCH}")
    log.info(f"Notify    : {EMAIL_TO}")
    log.info(f"Schedule  : Every Tuesday at 18:30 GMT")

    if RUN_NOW:
        log.info("RUN_NOW=true → running immediately for testing...")
        run_job()
    else:
        # Schedule for every Tuesday at 18:30
        schedule.every().tuesday.at("18:30").do(run_job)
        log.info("Scheduler active. Waiting for next Tuesday 18:30 GMT...")

        while True:
            schedule.run_pending()
            time.sleep(30)

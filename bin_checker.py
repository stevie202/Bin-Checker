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

# -----------------------------------------------------------
# CONFIG -- edit these or set as env variables
# -----------------------------------------------------------
ADDRESS_SEARCH  = os.getenv("BIN_ADDRESS",    "79 Redhill Road")
EMAIL_FROM      = os.getenv("EMAIL_FROM",     "your_email@gmail.com")
EMAIL_TO        = os.getenv("EMAIL_TO",       "your_email@gmail.com")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD", "your_app_password")
SMTP_HOST       = os.getenv("SMTP_HOST",      "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT",  "587"))
RUN_NOW         = os.getenv("RUN_NOW",        "false").lower() == "true"
COUNCIL_URL     = "https://www.lisburncastlereagh.gov.uk/w/collection-days-and-holiday-information"
# -----------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)


# -- Bin emojis
BIN_EMOJI = {
    "brown":    "🟤",
    "recycle":  "♻️",
    "residual": "🗑️",
    "green":    "🟢",
    "blue":     "🔵",
}

def get_bin_emoji(bin_name):
    name_lower = bin_name.lower()
    for key, emoji in BIN_EMOJI.items():
        if key in name_lower:
            return emoji
    return "🗂️"


# -- Scraper
def fetch_bin_info():
    log.info("Launching browser...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load page
        page.goto(COUNCIL_URL, wait_until="networkidle", timeout=30_000)
        log.info("Page loaded.")

        # Debug: log all inputs found
        inputs = page.locator("input").all()
        log.info(f"Found {len(inputs)} input(s):")
        for i, inp in enumerate(inputs):
            log.info(f"  [{i}] type={inp.get_attribute('type')} "
                     f"name={inp.get_attribute('name')} "
                     f"placeholder={inp.get_attribute('placeholder')} "
                     f"id={inp.get_attribute('id')}")

        # Try to find the search input
        search_selectors = [
            "input[placeholder*='address' i]",
            "input[placeholder*='postcode' i]",
            "input[placeholder*='search' i]",
            "input[name*='address' i]",
            "input[name*='search' i]",
            "input[id*='address' i]",
            "input[id*='search' i]",
            "input[type='text']",
        ]

        search_input = None
        for sel in search_selectors:
            candidate = page.locator(sel).first
            try:
                candidate.wait_for(state="visible", timeout=2_000)
                search_input = candidate
                log.info(f"Using search input: {sel}")
                break
            except PWTimeout:
                continue

        if not search_input:
            raise RuntimeError("Could not find search input on page")

        search_input.click()
        search_input.fill(ADDRESS_SEARCH)
        log.info(f"Typed: {ADDRESS_SEARCH}")
        page.wait_for_timeout(2_000)

        # Try submit button, fall back to Enter
        try:
            btn = page.locator(
                "button[type='submit'], button:has-text('Search'), "
                "button:has-text('Find'), input[type='submit']"
            ).first
            btn.click()
            log.info("Clicked submit button.")
        except Exception:
            search_input.press("Enter")
            log.info("Pressed Enter.")

        page.wait_for_timeout(3_000)

        # Save debug screenshot + HTML after search
        page.screenshot(path="debug_after_search.png", full_page=True)
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        log.info("Saved debug_after_search.png and debug_page.html")

        # Log body text to see what the page shows
        body_text = page.locator("body").inner_text()
        log.info("=== PAGE TEXT AFTER SEARCH (first 2000 chars) ===")
        log.info(body_text[:2000])
        log.info("=================================================")

        # Try to find address result dropdown
        result_selectors = [
            "[class*='autocomplete'] li",
            "[class*='suggestion']",
            "[class*='result'] li",
            "[class*='dropdown'] li",
            "[role='listbox'] [role='option']",
            "[role='option']",
            "ul[class*='address'] li",
            "ul li[data-value]",
            ".address-list li",
            "select option",
        ]

        result_locator = None
        for sel in result_selectors:
            try:
                page.wait_for_selector(sel, timeout=4_000)
                result_locator = page.locator(sel).first
                log.info(f"Found result with: {sel}")
                break
            except PWTimeout:
                continue

        if not result_locator:
            raise RuntimeError("Could not find address results -- check debug_page.html artifact")

        result_text = result_locator.inner_text()
        log.info(f"Clicking result: {result_text.strip()}")
        result_locator.click()

        page.wait_for_timeout(4_000)

        # Save post-selection debug files
        page.screenshot(path="debug_after_select.png", full_page=True)
        with open("debug_page_after_select.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        content = page.locator("body").inner_text()
        log.info("=== PAGE TEXT AFTER SELECTION (first 1500 chars) ===")
        log.info(content[:1500])
        log.info("====================================================")

        browser.close()

    return _parse_bin_info(content, result_text.strip())


def _parse_bin_info(content, address):
    result = {
        "address": address,
        "date":    "Unknown",
        "bins":    [],
        "raw":     content,
    }

    # Look for any date pattern (collection is on a Wednesday)
    date_pattern = re.compile(
        r"(Wednesday[,\s]+\d{1,2}\s+\w+\s+\d{4}|"
        r"Wednesday\s+\d{1,2}\s+\w+\s+\d{4}|"
        r"Wed\s+\d{1,2}\s+\w+\s+\d{4}|"
        r"\d{1,2}\s+\w+\s+\d{4})",   # fallback: any date
        re.IGNORECASE
    )

    for line in content.splitlines():
        m = date_pattern.search(line)
        if m:
            result["date"] = m.group(0).strip()
            break

    # Bin type keywords
    bin_keywords = {
        "BrownBin":    ["brown bin", "brownbin", "brown"],
        "RecycleBin":  ["recycle bin", "recyclebin", "recycling bin", "blue bin", "blue"],
        "ResidualBin": ["residual bin", "residualbin", "general waste", "black bin", "grey bin", "residual"],
    }

    content_lower = content.lower()
    for bin_name, keywords in bin_keywords.items():
        for kw in keywords:
            if kw in content_lower:
                result["bins"].append(bin_name)
                break

    result["bins"] = list(dict.fromkeys(result["bins"]))
    log.info(f"Parsed -> date: {result['date']}, bins: {result['bins']}")
    return result


# -- Email sender
def send_email(info):
    today = datetime.now().strftime("%A %d %B %Y")
    bins_html = "".join(
        f"<li style='padding:6px 0;font-size:1.1em;'>{get_bin_emoji(b)} <strong>{b}</strong></li>"
        for b in info["bins"]
    ) or "<li>Could not determine bin type -- check website manually.</li>"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
      <h2 style="color:#2d6a4f;">Bin Collection Reminder</h2>
      <p style="color:#555;">Checked on <strong>{today}</strong></p>
      <table style="border-collapse:collapse;width:100%;">
        <tr>
          <td style="padding:8px;background:#f0f4f0;border-radius:6px;">
            <strong>Address</strong><br>{info["address"]}
          </td>
        </tr>
        <tr><td style="height:10px;"></td></tr>
        <tr>
          <td style="padding:8px;background:#e8f5e9;border-radius:6px;">
            <strong>Next collection</strong><br>
            <span style="font-size:1.2em;color:#1b5e20;">{info["date"]}</span>
          </td>
        </tr>
        <tr><td style="height:10px;"></td></tr>
        <tr>
          <td style="padding:8px;background:#fff3e0;border-radius:6px;">
            <strong>Put out tonight:</strong>
            <ul style="margin:8px 0 0 0;padding-left:20px;">
              {bins_html}
            </ul>
          </td>
        </tr>
      </table>
      <p style="font-size:0.8em;color:#aaa;margin-top:24px;">
        Auto-generated by bin_checker.py --
        <a href="{COUNCIL_URL}">Lisburn &amp; Castlereagh Council</a>
      </p>
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


# -- Main job
def run_job():
    log.info("=" * 50)
    log.info("Running bin collection check...")
    try:
        info = fetch_bin_info()
        send_email(info)
    except Exception as e:
        log.error(f"Job failed: {e}", exc_info=True)
        send_email({
            "address": ADDRESS_SEARCH,
            "date":    "Could not retrieve -- check site manually",
            "bins":    [],
        })


# -- Scheduler
if __name__ == "__main__":
    log.info(f"Bin Checker started. Address: {ADDRESS_SEARCH}, Notify: {EMAIL_TO}")

    if RUN_NOW:
        log.info("RUN_NOW=true -- running immediately...")
        run_job()
    else:
        schedule.every().tuesday.at("18:30").do(run_job)
        log.info("Waiting for Tuesday 18:30 GMT...")
        while True:
            schedule.run_pending()
            time.sleep(30)

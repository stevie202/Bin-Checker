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
IFRAME_URL     = "lisburn.isl-fusion.com"

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

        page.goto(COUNCIL_URL, wait_until="networkidle", timeout=60_000)
        log.info("Page loaded.")

        # Dismiss cookie banner
        try:
            accept_btn = page.locator("button:has-text('I Accept Cookies')").first
            accept_btn.wait_for(state="visible", timeout=8_000)
            accept_btn.click()
            log.info("Dismissed cookie banner.")
            page.wait_for_timeout(2_000)
        except PWTimeout:
            log.info("No cookie banner.")

        # Get the isl-fusion iframe
        frame = page.frame(url="**lisburn.isl-fusion.com**") or page.frame(name="iFrameResizer0")
        if not frame:
            raise RuntimeError("Could not find isl-fusion iframe")
        log.info(f"Found iframe: {frame.url}")

        # Wait for and fill search input
        frame.wait_for_selector("input", timeout=15_000)
        search_input = frame.locator("input").first
        search_input.click()
        search_input.fill(ADDRESS_SEARCH)
        log.info(f"Typed: {ADDRESS_SEARCH}")
        page.wait_for_timeout(2_000)

        # Click Search button
        try:
            search_btn = frame.locator("button:has-text('Search'), input[type='submit'], button[type='submit']").first
            search_btn.click()
            log.info("Clicked Search button.")
        except Exception:
            search_input.press("Enter")
            log.info("Pressed Enter.")

        page.wait_for_timeout(3_000)

        # Find address result link inside iframe
        result_locator = None
        for sel in ["a", "li", "[class*='result']", "[class*='address']"]:
            try:
                frame.wait_for_selector(sel, timeout=4_000)
                for c in frame.locator(sel).all():
                    text = c.inner_text().strip()
                    if "redhill" in text.lower():
                        result_locator = c
                        log.info(f"Found result '{text}' with: {sel}")
                        break
                if result_locator:
                    break
            except (PWTimeout, Exception):
                continue

        if not result_locator:
            page.screenshot(path="debug_after_search.png", full_page=True)
            raise RuntimeError("Could not find address in results")

        result_text = result_locator.inner_text().strip()
        result_locator.click()
        log.info(f"Clicked: {result_text}")
        page.wait_for_timeout(4_000)

        # Save debug files
        page.screenshot(path="debug_after_select.png", full_page=True)
        with open("debug_after_select.html", "w", encoding="utf-8") as f:
            f.write(frame.content())

        content = frame.locator("body").inner_text()
        log.info("=== IFRAME TEXT ===")
        log.info(content[:1000])
        browser.close()

    return _parse_bin_info(content, result_text)


def _parse_bin_info(content, address):
    """
    Actual page format:
        Next Collections
        Wednesday 11th March
         BrownBin  RecycleBin        <- bins on same line, space-separated
        Wednesday 18th March
         ResidualBin
    """
    result = {"address": address, "date": "Unknown", "bins": []}
    lines = [l.strip() for l in content.splitlines() if l.strip()]

    date_re = re.compile(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}\w*\s+\w+",
        re.IGNORECASE
    )
    bin_names = ["BrownBin", "RecycleBin", "ResidualBin"]

    # Find 'Next Collections' marker
    try:
        start = next(i for i, l in enumerate(lines) if "Next Collections" in l)
    except StopIteration:
        log.warning("'Next Collections' not found in page text")
        return result

    # Find first date line after marker
    first_date_idx = None
    for i in range(start + 1, len(lines)):
        if date_re.match(lines[i]):
            first_date_idx = i
            result["date"] = lines[i]
            break

    if first_date_idx is None:
        log.warning("No date found after 'Next Collections'")
        return result

    # Collect bins from lines immediately after the date, until the next date line
    for i in range(first_date_idx + 1, min(first_date_idx + 5, len(lines))):
        if date_re.match(lines[i]):
            break
        for b in bin_names:
            if b.lower() in lines[i].lower() and b not in result["bins"]:
                result["bins"].append(b)

    log.info(f"Parsed -> date: {result['date']}, bins: {result['bins']}")
    return result


def send_email(info):
    today = datetime.now().strftime("%A %d %B %Y")
    bins_html = "".join(
        f"<li style='padding:4px 0;font-size:1.1em;'>{get_bin_emoji(b)} <strong>{b}</strong></li>"
        for b in info["bins"]
    ) or "<li>Could not determine bin type -- check website manually.</li>"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px;">
      <h2 style="color:#2d6a4f;">Bin Collection Reminder</h2>
      <p style="color:#555;">Checked: <strong>{today}</strong></p>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:8px;background:#f0f4f0;border-radius:6px;">
          <strong>Address</strong><br>{info["address"]}
        </td></tr>
        <tr><td style="height:10px;"></td></tr>
        <tr><td style="padding:8px;background:#e8f5e9;border-radius:6px;">
          <strong>Next collection</strong><br>
          <span style="font-size:1.2em;color:#1b5e20;">{info["date"]}</span>
        </td></tr>
        <tr><td style="height:10px;"></td></tr>
        <tr><td style="padding:8px;background:#fff3e0;border-radius:6px;">
          <strong>Put out tonight:</strong>
          <ul style="margin:8px 0 0 0;padding-left:20px;">{bins_html}</ul>
        </td></tr>
      </table>
      <p style="font-size:0.8em;color:#aaa;margin-top:24px;">
        Auto-generated -- <a href="{COUNCIL_URL}">Lisburn &amp; Castlereagh Council</a>
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

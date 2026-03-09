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

        page.goto(COUNCIL_URL, wait_until="networkidle", timeout=60_000)
        log.info("Page loaded.")

        # -- Dismiss cookie banner
        try:
            accept_btn = page.locator("button:has-text('I Accept Cookies')").first
            accept_btn.wait_for(state="visible", timeout=8_000)
            accept_btn.click()
            log.info("Dismissed cookie banner.")
            page.wait_for_timeout(1_500)
        except PWTimeout:
            log.info("No cookie banner found, continuing.")

        # -- Wait for search input
        log.info("Waiting for search input...")
        page.wait_for_selector("input[type='text']", timeout=20_000)
        log.info("Search input found.")

        # -- Fill in address
        search_input = page.locator("input[type='text']").first
        search_input.click()
        search_input.fill(ADDRESS_SEARCH)
        log.info(f"Typed: {ADDRESS_SEARCH}")
        page.wait_for_timeout(2_000)

        # -- Save debug screenshot after typing
        page.screenshot(path="debug_after_search.png", full_page=True)
        with open("debug_after_search.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        body_text = page.locator("body").inner_text()
        log.info("=== PAGE TEXT AFTER TYPING (first 2000 chars) ===")
        log.info(body_text[:2000])
        log.info("==================================================")

        # -- Look for address suggestions
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
            "select option:not([value=''])",
            "li[class*='item']",
        ]

        result_locator = None
        for sel in result_selectors:
            try:
                page.wait_for_selector(sel, timeout=5_000)
                result_locator = page.locator(sel).first
                log.info(f"Found result with selector: {sel}")
                break
            except PWTimeout:
                continue

        # -- If no dropdown, try pressing Enter/clicking Search button
        if not result_locator:
            log.info("No dropdown found, trying Enter key...")
            search_input.press("Enter")
            page.wait_for_timeout(3_000)

            for sel in result_selectors:
                try:
                    page.wait_for_selector(sel, timeout=5_000)
                    result_locator = page.locator(sel).first
                    log.info(f"Found result after Enter with selector: {sel}")
                    break
                except PWTimeout:
                    continue

        if not result_locator:
            page.screenshot(path="debug_after_search.png", full_page=True)
            raise RuntimeError("Could not find address results - check debug_after_search.html")

        result_text = result_locator.inner_text()
        log.info(f"Clicking result: {result_text.strip()}")
        result_locator.click()
        page.wait_for_timeout(4_000)

        # -- Save post-selection debug
        page.screenshot(path="debug_after_select.png", full_page=True)
        with open("debug_after_select.html", "w", encoding="utf-8") as f:
            f.write(page.content())

        content = page.locator("body").inner_text()
        log.info("=== PAGE TEXT AFTER SELECTION (first 2000 chars) ===")
        log.info(content[:2000])
        log.info("=====================================================")

        browser.close()

    return _parse_bin_info(content, result_text.strip())

def _parse_bin_info(content, address):
    result = {"address": address, "date": "Unknown", "bins": []}
    date_pattern = re.compile(
        r"(Wednesday[\s,]+\d{1,2}\s+\w+\s+\d{4}|"
        r"Wed\s+\d{1,2}\s+\w+\s+\d{4}|"
        r"\d{1,2}\s+\w+\s+\d{4})",
        re.IGNORECASE
    )
    for line in content.splitlines():
        m = date_pattern.search(line)
        if m:
            result["date"] = m.group(0).strip()
            break
    bin_keywords = {
        "BrownBin":    ["brown bin", "brownbin", "brown"],
        "RecycleBin":  ["recycle bin", "recyclebin", "recycling bin", "blue bin"],
        "ResidualBin": ["residual bin", "residualbin", "general waste", "black bin", "residual"],
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

# 🗑️ Bin Collection Day Checker

Automatically checks your bin collection day every **Tuesday at 18:30 GMT** and emails you the results.

---

## Setup (5 minutes)

### 1. Install dependencies
```bash
pip install playwright schedule
playwright install chromium
```

### 2. Configure credentials

**Option A — Edit the script directly** (lines 20–27 of `bin_checker.py`):
```python
EMAIL_FROM     = "your_email@gmail.com"
EMAIL_TO       = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
```

**Option B — Set environment variables** (recommended):
```bash
export EMAIL_FROM="your_email@gmail.com"
export EMAIL_TO="your_email@gmail.com"
export EMAIL_PASSWORD="your_app_password"
```

### 3. Get a Gmail App Password
> Required if you use Gmail with 2FA (which you should!)

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Create a new App Password → name it "Bin Checker"
3. Copy the 16-character password → use as `EMAIL_PASSWORD`

---

## Running

### Test it immediately
```bash
RUN_NOW=true python bin_checker.py
```

### Run on schedule (Tuesday 18:30 GMT)
```bash
python bin_checker.py
```
Keep this running in the background (e.g. in `tmux`, `screen`, or as a service).

---

## Run as a background service (Linux/Mac)

### Option A: tmux
```bash
tmux new -s bin_checker
python bin_checker.py
# Ctrl+B then D to detach
```

### Option B: systemd (Linux)
Create `/etc/systemd/system/bin_checker.service`:
```ini
[Unit]
Description=Bin Collection Checker
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/bin_checker.py
Restart=always
Environment="EMAIL_FROM=your@gmail.com"
Environment="EMAIL_TO=your@gmail.com"
Environment="EMAIL_PASSWORD=your_app_password"

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl enable bin_checker
sudo systemctl start bin_checker
```

### Option C: Windows Task Scheduler
- Trigger: Weekly, Tuesday, 18:30
- Action: `python C:\path\to\bin_checker.py`
- Set `RUN_NOW=true` env var only for testing

---

## What you'll receive

An HTML email every Tuesday evening like:

```
🗑️ Bin Day Tomorrow — Wednesday 12 March 2025

📍 Address:  79 Redhill Road, ...
📅 Next collection: Wednesday 12 March 2025
🪣 Put out tonight:
   🟤 BrownBin
   ♻️ RecycleBin
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Playwright not found | Run `playwright install chromium` |
| Email not sending | Check App Password, ensure "Less secure app" not needed |
| Address not found | Check `ADDRESS_SEARCH` matches the site's format |
| Bins show "Unknown" | The site HTML may have changed — open an issue |

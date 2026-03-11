"""
services/gmail.py
Gmail notifications via SMTP (App Password).
"""
import os
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

log = logging.getLogger(__name__)

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


# ── Core sender ───────────────────────────────────────────────

def send_email(to: str, subject: str, body_html: str, body_text: str = "") -> bool:
    """Send an email via Gmail SMTP."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        log.warning("Gmail credentials not configured — skipping email")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"ISP Admin <{GMAIL_ADDRESS}>"
        msg["To"]      = to

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, to, msg.as_string())

        log.info("Email sent → %s [%s]", to, subject)
        return True
    except Exception as e:
        log.error("Gmail error → %s: %s", to, e)
        return False


# ── HTML templates ────────────────────────────────────────────

_STYLE = """
body{font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:20px}
.card{background:#fff;border-radius:8px;padding:24px;max-width:480px;
      margin:0 auto;box-shadow:0 2px 8px rgba(0,0,0,.1)}
h2{color:#1a73e8;margin-top:0}
.detail{background:#f8f9fa;border-radius:4px;padding:12px;
        font-family:monospace;font-size:14px;line-height:1.8}
.label{color:#666;font-size:12px;margin-bottom:4px}
.footer{color:#999;font-size:11px;margin-top:16px;text-align:center}
"""


def email_pppoe_created(username: str, password: str, plan: str, expires: str) -> tuple[str, str]:
    """Returns (subject, html_body) for new PPPoE account."""
    subject = "✅ Your Internet Account is Ready"
    html = f"""
<html><head><style>{_STYLE}</style></head><body>
<div class="card">
  <h2>Your Internet Account is Active</h2>
  <p>Your PPPoE subscription has been set up successfully.</p>
  <div class="detail">
    <div class="label">Username</div><strong>{username}</strong><br>
    <div class="label">Password</div><strong>{password}</strong><br>
    <div class="label">Plan</div>{plan}<br>
    <div class="label">Expires</div>{expires}
  </div>
  <p>Use these credentials in your PPPoE client or router.</p>
  <div class="footer">ISP Support — reply to this email for help</div>
</div>
</body></html>"""
    return subject, html


def email_hotspot_voucher(code: str, profile: str) -> tuple[str, str]:
    subject = "🌐 Your Hotspot Voucher"
    html = f"""
<html><head><style>{_STYLE}</style></head><body>
<div class="card">
  <h2>Hotspot Voucher</h2>
  <p>Connect to our WiFi and enter this code in your browser:</p>
  <div class="detail" style="text-align:center;font-size:24px;letter-spacing:4px">
    <strong>{code}</strong>
  </div>
  <p>Plan: <strong>{profile}</strong></p>
  <div class="footer">ISP Support — reply to this email for help</div>
</div>
</body></html>"""
    return subject, html


def email_payment_confirmed(receipt: str, amount: float, plan: str) -> tuple[str, str]:
    subject = f"💰 Payment Confirmed — KSH {amount:.0f}"
    html = f"""
<html><head><style>{_STYLE}</style></head><body>
<div class="card">
  <h2>Payment Received</h2>
  <div class="detail">
    <div class="label">M-Pesa Receipt</div><strong>{receipt}</strong><br>
    <div class="label">Amount</div>KSH {amount:.0f}<br>
    <div class="label">Plan</div>{plan}
  </div>
  <p>Your service is being activated. You will receive another email shortly.</p>
  <div class="footer">ISP Support — reply to this email for help</div>
</div>
</body></html>"""
    return subject, html


def email_expiry_reminder(username: str, days: int, plan: str) -> tuple[str, str]:
    subject = f"⏰ Renewal Reminder — {days} day(s) left"
    html = f"""
<html><head><style>{_STYLE}</style></head><body>
<div class="card">
  <h2>Time to Renew!</h2>
  <p>Hello <strong>{username}</strong>,</p>
  <p>Your <strong>{plan}</strong> plan expires in <strong>{days} day(s)</strong>.</p>
  <p>Pay via M-Pesa to keep your internet running without interruption.</p>
  <div class="footer">ISP Support — reply to this email for help</div>
</div>
</body></html>"""
    return subject, html

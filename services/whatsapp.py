"""
services/whatsapp.py
WhatsApp notifications via pywhatkit.

⚠️  IMPORTANT — pywhatkit requires WhatsApp Web to be open in a Chrome
    session on the same machine. On Render (headless), install Chromium
    and keep a persistent WhatsApp Web session, OR swap this for the
    Meta WhatsApp Business API / Twilio sandbox.

    For quick local testing pywhatkit works fine.
    For Render production, set WHATSAPP_BACKEND=api and configure
    WHATSAPP_API_URL + WHATSAPP_API_TOKEN (e.g. Twilio).
"""
import os
import logging
import requests

log = logging.getLogger(__name__)

SENDER   = os.getenv("WHATSAPP_SENDER", "")
BACKEND  = os.getenv("WHATSAPP_BACKEND", "pywhatkit")   # pywhatkit | api

# Only used when WHATSAPP_BACKEND=api (e.g. Twilio / Meta)
API_URL   = os.getenv("WHATSAPP_API_URL", "")
API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")


# ── Sender ───────────────────────────────────────────────────

def send_whatsapp(phone: str, message: str) -> bool:
    """
    Send a WhatsApp message.
    phone: international format with country code, no + (e.g. 254712345678)
    """
    if BACKEND == "api":
        return _send_via_api(phone, message)
    return _send_via_pywhatkit(phone, message)


def _send_via_pywhatkit(phone: str, message: str) -> bool:
    try:
        import pywhatkit as pwk
        # sendwhatmsg_instantly opens WhatsApp Web and sends immediately
        pwk.sendwhatmsg_instantly(
            phone_no=f"+{phone}",
            message=message,
            wait_time=12,
            tab_close=True,
            close_time=3,
        )
        log.info("WhatsApp sent via pywhatkit → %s", phone)
        return True
    except Exception as e:
        log.error("pywhatkit error → %s: %s", phone, e)
        return False


def _send_via_api(phone: str, message: str) -> bool:
    """Generic REST API sender (Twilio / Meta Cloud API)."""
    if not API_URL:
        log.warning("WHATSAPP_API_URL not set, skipping WhatsApp")
        return False
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_TOKEN}",
                     "Content-Type": "application/json"},
            json={"to": f"whatsapp:+{phone}", "body": message},
            timeout=10,
        )
        resp.raise_for_status()
        log.info("WhatsApp sent via API → %s", phone)
        return True
    except Exception as e:
        log.error("WhatsApp API error → %s: %s", phone, e)
        return False


# ── Message templates ────────────────────────────────────────

def msg_pppoe_created(username: str, password: str, plan: str, expires: str) -> str:
    return (
        f"✅ *ISP Account Created*\n"
        f"──────────────────\n"
        f"Username : `{username}`\n"
        f"Password : `{password}`\n"
        f"Plan     : {plan}\n"
        f"Expires  : {expires}\n"
        f"──────────────────\n"
        f"PPPoE connection — enter these in your router/PC.\n"
        f"Support: Reply to this message."
    )


def msg_hotspot_voucher(code: str, profile: str) -> str:
    return (
        f"🌐 *Hotspot Voucher*\n"
        f"──────────────────\n"
        f"Code  : `{code}`\n"
        f"Plan  : {profile}\n"
        f"──────────────────\n"
        f"Connect to the WiFi, open your browser,\n"
        f"and enter this code when prompted."
    )


def msg_payment_received(receipt: str, amount: float, plan: str) -> str:
    return (
        f"💰 *Payment Received*\n"
        f"Receipt : {receipt}\n"
        f"Amount  : KSH {amount:.0f}\n"
        f"Plan    : {plan}\n"
        f"Thank you! Your service is being activated."
    )


def msg_expiry_reminder(username: str, days: int) -> str:
    return (
        f"⏰ *Renewal Reminder*\n"
        f"Hi {username}, your internet plan expires in *{days} day(s)*.\n"
        f"Pay via M-Pesa to renew. Paybill: XXXXXX"
    )

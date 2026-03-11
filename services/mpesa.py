"""
services/mpesa.py
M-Pesa Daraja integration — STK Push + callback verification.
Supports sandbox and production environments.
"""
import os
import base64
import logging
import requests
from datetime import datetime

log = logging.getLogger(__name__)

CONSUMER_KEY    = os.getenv("MPESA_CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET", "")
SHORTCODE       = os.getenv("MPESA_SHORTCODE", "")
PASSKEY         = os.getenv("MPESA_PASSKEY", "")
ENV             = os.getenv("MPESA_ENV", "sandbox")
CALLBACK_URL    = os.getenv("MPESA_CALLBACK_URL", "")

BASE_URL = (
    "https://api.safaricom.co.ke"
    if ENV == "production"
    else "https://sandbox.safaricom.co.ke"
)

# ── Helpers ──────────────────────────────────────────────────

def _get_token() -> str:
    """Fetch OAuth2 bearer token from Daraja."""
    credentials = base64.b64encode(
        f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()
    ).decode()
    resp = requests.get(
        f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {credentials}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _get_password_and_timestamp() -> tuple[str, str]:
    """Generate the Daraja password (base64 of shortcode+passkey+timestamp)."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    raw = f"{SHORTCODE}{PASSKEY}{ts}"
    password = base64.b64encode(raw.encode()).decode()
    return password, ts


# ── STK Push ─────────────────────────────────────────────────

def stk_push(phone: str, amount: int, account_ref: str, description: str) -> dict:
    """
    Initiate Lipa Na M-Pesa Online (STK Push).

    Args:
        phone       : Customer phone in format 2547XXXXXXXX
        amount      : Amount in KES (integer)
        account_ref : Short reference shown on customer phone (e.g. username)
        description : Transaction description

    Returns:
        Daraja response dict with CheckoutRequestID
    """
    token = _get_token()
    password, timestamp = _get_password_and_timestamp()

    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password":          password,
        "Timestamp":         timestamp,
        "TransactionType":   "CustomerPayBillOnline",
        "Amount":            amount,
        "PartyA":            phone,
        "PartyB":            SHORTCODE,
        "PhoneNumber":       phone,
        "CallBackURL":       CALLBACK_URL,
        "AccountReference":  account_ref[:12],   # max 12 chars
        "TransactionDesc":   description[:13],   # max 13 chars
    }

    resp = requests.post(
        f"{BASE_URL}/mpesa/stkpush/v1/processrequest",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    log.info("STK Push → phone=%s amount=%s checkout=%s",
             phone, amount, data.get("CheckoutRequestID"))
    return data


def parse_callback(body: dict) -> dict:
    """
    Parse the M-Pesa STK callback POST body.

    Returns a normalised dict:
        {
          "checkout_id": str,
          "result_code": int,    # 0 = success
          "result_desc": str,
          "amount": float | None,
          "receipt": str | None,
          "phone": str | None,
          "paid_at": datetime | None,
        }
    """
    try:
        stk = body["Body"]["stkCallback"]
        checkout_id = stk["CheckoutRequestID"]
        result_code = stk["ResultCode"]
        result_desc = stk["ResultDesc"]

        if result_code != 0:
            return {
                "checkout_id": checkout_id,
                "result_code": result_code,
                "result_desc": result_desc,
                "amount": None, "receipt": None,
                "phone": None,  "paid_at": None,
            }

        items = {
            item["Name"]: item.get("Value")
            for item in stk["CallbackMetadata"]["Item"]
        }
        paid_at_raw = items.get("TransactionDate")
        paid_at = (
            datetime.strptime(str(paid_at_raw), "%Y%m%d%H%M%S")
            if paid_at_raw else None
        )
        return {
            "checkout_id": checkout_id,
            "result_code": result_code,
            "result_desc": result_desc,
            "amount":      float(items.get("Amount", 0)),
            "receipt":     items.get("MpesaReceiptNumber"),
            "phone":       str(items.get("PhoneNumber", "")),
            "paid_at":     paid_at,
        }
    except (KeyError, TypeError, ValueError) as e:
        log.error("Callback parse error: %s — body=%s", e, body)
        raise ValueError(f"Invalid M-Pesa callback payload: {e}")


# ── Plan pricing map ─────────────────────────────────────────
# Plan key → (display label, amount KES, service type)

PLANS = {
    # PPPoE monthly plans
    "plan-500":  ("PPPoE 5Mbps 1-device (KSH 500)",   500,  "pppoe"),
    "plan-700":  ("PPPoE 5Mbps 2-device (KSH 700)",   700,  "pppoe"),
    "plan-1000": ("PPPoE 7Mbps 5-device (KSH 1000)",  1000, "pppoe"),
    "plan-1300": ("PPPoE 10Mbps Unlimited (KSH 1300)", 1300, "pppoe"),
    # Hotspot time plans
    "hs-3min":   ("Hotspot 3 min (KSH 4)",     4,   "hotspot"),
    "hs-2hr":    ("Hotspot 2 hr (KSH 8)",      8,   "hotspot"),
    "hs-4hr":    ("Hotspot 4 hr (KSH 13)",     13,  "hotspot"),
    "hs-6hr":    ("Hotspot 6 hr (KSH 18)",     18,  "hotspot"),
    "hs-daily":  ("Hotspot Daily (KSH 28)",    28,  "hotspot"),
    "hs-2day":   ("Hotspot 2 Days (KSH 48)",   48,  "hotspot"),
    "hs-weekly": ("Hotspot Weekly (KSH 190)",  190, "hotspot"),
    "hs-monthly":("Hotspot Monthly (KSH 500)", 500, "hotspot"),
}

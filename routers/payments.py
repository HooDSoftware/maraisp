"""
routers/payments.py
POST /payments/initiate   — Customer initiates STK Push
POST /payments/callback   — M-Pesa Daraja POSTs result here
GET  /payments/status/{checkout_id}
GET  /payments/           — Admin: list all payments
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, Payment, PPPoEUser, HotspotVoucher, NotificationLog
from services import mikrotik, mpesa, whatsapp, gmail

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Schemas ───────────────────────────────────────────────────

class InitiateRequest(BaseModel):
    phone:    str   # 2547XXXXXXXX
    plan:     str   # e.g. plan-1000 or hs-daily
    username: str = ""   # desired PPPoE username (leave blank for hotspot)
    email:    str = ""   # optional email for notifications


# ── Helpers ───────────────────────────────────────────────────

def _rand(n: int) -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(n))


def _notify(phone: str, email: str, wa_msg: str, em_subject: str, em_html: str, db: Session):
    """Fire WhatsApp + email notifications and log both."""
    wa_ok = whatsapp.send_whatsapp(phone, wa_msg)
    db.add(NotificationLog(channel="whatsapp", recipient=phone,
                           message=wa_msg, success=wa_ok))

    if email:
        em_ok = gmail.send_email(email, em_subject, em_html)
        db.add(NotificationLog(channel="gmail", recipient=email,
                               message=em_subject, success=em_ok))
    db.commit()


# ── Routes ────────────────────────────────────────────────────

@router.post("/initiate")
def initiate_payment(req: InitiateRequest, db: Session = Depends(get_db)):
    """Customer triggers STK Push for their chosen plan."""
    plan_info = mpesa.PLANS.get(req.plan)
    if not plan_info:
        raise HTTPException(400, f"Unknown plan '{req.plan}'")

    label, amount, service_type = plan_info

    # Generate reference
    ref = req.username if req.username else f"HS{_rand(6)}"

    try:
        result = mpesa.stk_push(
            phone=req.phone,
            amount=amount,
            account_ref=ref,
            description=f"Internet {req.plan}",
        )
    except Exception as e:
        raise HTTPException(502, f"M-Pesa error: {e}")

    checkout_id = result.get("CheckoutRequestID")
    if not checkout_id:
        raise HTTPException(502, "No CheckoutRequestID in M-Pesa response")

    # Persist pending payment
    payment = Payment(
        checkout_id=checkout_id,
        phone=req.phone,
        amount=amount,
        plan=req.plan,
        service_type=service_type,
        username=ref if service_type == "pppoe" else None,
        status="pending",
    )
    db.add(payment)
    db.commit()

    return {
        "checkout_id": checkout_id,
        "message": f"STK Push sent to {req.phone}. Enter M-Pesa PIN.",
        "amount": amount,
        "plan": label,
    }


@router.post("/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    """
    M-Pesa Daraja calls this after the customer completes (or cancels) payment.
    Must return 200 immediately — Daraja will retry on failure.
    """
    try:
        body = await request.json()
    except Exception:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    try:
        cb = mpesa.parse_callback(body)
    except ValueError as e:
        log.error("Bad callback: %s", e)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment = db.query(Payment).filter_by(checkout_id=cb["checkout_id"]).first()
    if not payment:
        log.warning("Callback for unknown checkout_id: %s", cb["checkout_id"])
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    if cb["result_code"] != 0:
        payment.status = "failed"
        db.commit()
        log.info("Payment failed: %s — %s", cb["checkout_id"], cb["result_desc"])
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    # ── Payment succeeded ────────────────────────────────────
    payment.status        = "paid"
    payment.mpesa_receipt = cb["receipt"]
    payment.paid_at       = cb["paid_at"] or datetime.utcnow()
    db.commit()

    plan_info = mpesa.PLANS.get(payment.plan, ("", payment.amount, payment.service_type))
    label = plan_info[0]

    if payment.service_type == "pppoe":
        _activate_pppoe(payment, db)
    else:
        _activate_hotspot(payment, db)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


def _activate_pppoe(payment: Payment, db: Session):
    """Create PPPoE account and notify customer."""
    username = payment.username or f"u{_rand(8)}"
    password = _rand(10)
    plan     = payment.plan

    try:
        mikrotik.pppoe_add(username=username, password=password,
                           plan=plan, comment=f"phone={payment.phone}")
    except Exception as e:
        log.error("MikroTik PPPoE create failed: %s", e)
        payment.status = "paid_activation_error"
        db.commit()
        return

    expires = (datetime.utcnow() + timedelta(
        days=mikrotik.PLAN_DURATION_DAYS.get(plan, 30)
    )).strftime("%d %b %Y")

    # Persist user record
    db.add(PPPoEUser(
        username=username, phone=payment.phone,
        plan=plan, expires_at=datetime.utcnow() + timedelta(
            days=mikrotik.PLAN_DURATION_DAYS.get(plan, 30)
        )
    ))
    payment.username = username
    db.commit()

    # Notify
    wa  = whatsapp.msg_pppoe_created(username, password, plan, expires)
    sub, html = gmail.email_pppoe_created(username, password, plan, expires)
    wa_ok = whatsapp.send_whatsapp(payment.phone, wa)
    db.add(NotificationLog(channel="whatsapp", recipient=payment.phone,
                           message=wa, success=wa_ok))
    db.commit()
    log.info("PPPoE activated: %s for %s", username, payment.phone)


def _activate_hotspot(payment: Payment, db: Session):
    """Create hotspot voucher and notify customer."""
    code     = _rand(8)
    profile  = payment.plan   # e.g. hs-daily

    try:
        mikrotik.hotspot_add_user(
            username=code, password=code,
            profile=profile,
            comment=f"phone={payment.phone} receipt={payment.mpesa_receipt}"
        )
    except Exception as e:
        log.error("MikroTik hotspot create failed: %s", e)
        payment.status = "paid_activation_error"
        db.commit()
        return

    db.add(HotspotVoucher(
        code=code, plan=profile, phone=payment.phone
    ))
    payment.voucher_code = code
    db.commit()

    wa = whatsapp.msg_hotspot_voucher(code, profile)
    wa_ok = whatsapp.send_whatsapp(payment.phone, wa)
    db.add(NotificationLog(channel="whatsapp", recipient=payment.phone,
                           message=wa, success=wa_ok))
    db.commit()
    log.info("Hotspot voucher created: %s for %s", code, payment.phone)


@router.get("/status/{checkout_id}")
def payment_status(checkout_id: str, db: Session = Depends(get_db)):
    p = db.query(Payment).filter_by(checkout_id=checkout_id).first()
    if not p:
        raise HTTPException(404, "Payment not found")
    return {
        "checkout_id":   p.checkout_id,
        "status":        p.status,
        "plan":          p.plan,
        "amount":        p.amount,
        "receipt":       p.mpesa_receipt,
        "username":      p.username,
        "voucher_code":  p.voucher_code,
        "created_at":    p.created_at,
        "paid_at":       p.paid_at,
    }


@router.get("/")
def list_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    payments = db.query(Payment).order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": p.id, "checkout_id": p.checkout_id,
            "phone": p.phone, "amount": p.amount, "plan": p.plan,
            "service_type": p.service_type, "status": p.status,
            "receipt": p.mpesa_receipt, "username": p.username,
            "voucher_code": p.voucher_code,
            "created_at": p.created_at, "paid_at": p.paid_at,
        }
        for p in payments
    ]

"""
routers/reports.py
Reporting endpoints for admin dashboard.
GET /reports/summary         — revenue totals + subscriber counts
GET /reports/revenue/daily   — daily revenue for last 30 days
GET /reports/plans           — breakdown by plan
GET /reports/notifications   — notification log
"""
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Payment, PPPoEUser, HotspotVoucher, NotificationLog

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    total_revenue = db.query(func.sum(Payment.amount)).filter_by(status="paid").scalar() or 0
    total_payments = db.query(Payment).filter_by(status="paid").count()
    pending        = db.query(Payment).filter_by(status="pending").count()
    failed         = db.query(Payment).filter_by(status="failed").count()
    pppoe_users    = db.query(PPPoEUser).filter_by(active=True).count()
    vouchers_total = db.query(HotspotVoucher).count()
    vouchers_used  = db.query(HotspotVoucher).filter_by(used=True).count()

    # Revenue today
    today = datetime.utcnow().date()
    rev_today = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "paid",
        func.date(Payment.paid_at) == today,
    ).scalar() or 0

    # Revenue this month
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    rev_month = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "paid",
        Payment.paid_at >= month_start,
    ).scalar() or 0

    return {
        "revenue": {
            "total":        float(total_revenue),
            "today":        float(rev_today),
            "this_month":   float(rev_month),
        },
        "payments": {
            "paid":    total_payments,
            "pending": pending,
            "failed":  failed,
        },
        "subscribers": {
            "pppoe_active":     pppoe_users,
            "hotspot_vouchers": vouchers_total,
            "hotspot_used":     vouchers_used,
        },
    }


@router.get("/revenue/daily")
def daily_revenue(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    payments = db.query(Payment).filter(
        Payment.status == "paid",
        Payment.paid_at >= since,
    ).all()

    daily: dict = defaultdict(float)
    for p in payments:
        if p.paid_at:
            key = p.paid_at.strftime("%Y-%m-%d")
            daily[key] += p.amount

    # Fill in zero days
    result = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        result.append({"date": d, "revenue": daily.get(d, 0.0)})

    return result


@router.get("/plans")
def plan_breakdown(db: Session = Depends(get_db)):
    payments = db.query(Payment).filter_by(status="paid").all()
    plans: dict = defaultdict(lambda: {"count": 0, "revenue": 0.0})
    for p in payments:
        plans[p.plan]["count"]   += 1
        plans[p.plan]["revenue"] += p.amount
    return [
        {"plan": k, "count": v["count"], "revenue": v["revenue"]}
        for k, v in sorted(plans.items(), key=lambda x: -x[1]["revenue"])
    ]


@router.get("/notifications")
def notification_log(limit: int = 100, db: Session = Depends(get_db)):
    logs = db.query(NotificationLog).order_by(
        NotificationLog.sent_at.desc()
    ).limit(limit).all()
    return [
        {
            "id": n.id, "channel": n.channel, "recipient": n.recipient,
            "message": n.message, "success": n.success,
            "error": n.error, "sent_at": n.sent_at,
        }
        for n in logs
    ]

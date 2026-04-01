from datetime import datetime
import hashlib
from .models import UsageLog, Notification, Location

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def now_ts():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def now_date():
    return datetime.now().strftime("%d/%m/%Y")

def now_time():
    return datetime.now().strftime("%H:%M:%S")

def norm(v):
    return v.strip().upper() if isinstance(v, str) else v

def first_free_location(db):
    return db.query(Location).filter(Location.status == "FREE").order_by(Location.id.asc()).first()

def plate_usage_display(db, plate_set_id: str):
    logs = db.query(UsageLog).filter(UsageLog.plate_set_id == plate_set_id, UsageLog.action == "OUT").order_by(UsageLog.id.desc()).all()
    if not logs:
        return {"last_used_date": "No usage found", "usage_count": "No usage found", "days_since_last_used": "No usage found"}
    last = logs[0].action_date
    try:
        last_dt = datetime.strptime(last, "%d/%m/%Y")
        days = (datetime.now() - last_dt).days
    except Exception:
        days = "No usage found"
    return {"last_used_date": last, "usage_count": len(logs), "days_since_last_used": days}

def replacement_usage_display(db, replacement):
    logs = db.query(UsageLog).filter(UsageLog.plate_set_id == replacement.plate_set_id, UsageLog.action == "OUT").order_by(UsageLog.id.desc()).all()
    qualified = []
    try:
        recv = datetime.strptime(replacement.receiving_date, "%d/%m/%Y")
        for l in logs:
            try:
                ldt = datetime.strptime(l.action_date, "%d/%m/%Y")
                if ldt >= recv:
                    qualified.append(l)
            except Exception:
                continue
    except Exception:
        qualified = []
    if not qualified:
        return {"last_used_date": "No usage found", "usage_count": "No usage found", "days_since_last_used": "No usage found"}
    last = qualified[0].action_date
    days = (datetime.now() - datetime.strptime(last, "%d/%m/%Y")).days
    return {"last_used_date": last, "usage_count": len(qualified), "days_since_last_used": days}

def plate_age(receiving_date: str):
    try:
        return (datetime.now() - datetime.strptime(receiving_date, "%d/%m/%Y")).days
    except Exception:
        return ""

def create_notification(db, email: str, title: str, message: str):
    db.add(Notification(user_email=email, title=title, message=message, created_at=now_ts()))
    db.commit()

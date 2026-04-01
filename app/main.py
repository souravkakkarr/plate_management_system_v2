from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path

from .db import Base, engine, SessionLocal
from .models import User, Location, PlateSet, ReplacementPlate, UsageLog, ScrapRequest, Notification
from .utils import (
    hash_password, verify_password, now_date, now_time, now_ts, norm,
    first_free_location, plate_usage_display, replacement_usage_display,
    plate_age, create_notification,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html", "xml"])
)

app = FastAPI(title="Plate Management")
app.add_middleware(SessionMiddleware, secret_key="CHANGE-THIS-SECRET")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def render_template(name: str, **context):
    template = templates.get_template(name)
    return HTMLResponse(template.render(**context))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_user(request: Request, db: Session):
    email = request.session.get("user_email")
    if not email:
        return None
    return db.query(User).filter(User.email == email, User.is_active == "YES").first()

def require_login(request: Request, db: Session):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

def require_roles(user, *roles):
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Not authorized")

def seed_locations(db: Session):
    if db.query(Location).first():
        return
    for rack in range(1, 11):
        rack_no = f"R{rack:02d}"
        for shelf in ["A", "B"]:
            for slot in range(1, 7):
                section_code = f"{shelf}{slot}"
                for pos in range(1, 21):
                    position_no = f"{pos:02d}"
                    location_id = f"{rack_no}-{section_code}-{position_no}"
                    db.add(Location(
                        location_id=location_id,
                        rack_no=rack_no,
                        shelf_code=shelf,
                        section_code=section_code,
                        position_no=position_no,
                        status="FREE"
                    ))
    db.commit()

def seed_users(db: Session):
    fixed = [
        ("OWNER", "OWNER", "SOURAVKAKKAR2K3@GMAIL.COM", "owner123"),
        ("TECH_TEAM", "TECH TEAM", "SOURAVKAKKARR@GMAIL.COM", "tech123"),
        ("DESIGNER", "DESIGNER", "DESIGNER_OF_COMPANY@GMAIL.COM", "designer123"),
        ("PLATE_MANAGER", "PLATE MANAGER", "PLATE_MANAGER_OF_COMPANY@GMAIL.COM", "plate123"),
    ]
    for role, full_name, email, password in fixed:
        row = db.query(User).filter(User.role == role).first()
        if not row:
            db.add(User(
                role=role,
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                is_active="YES"
            ))
    db.commit()

def seed_notifications(db: Session):
    if db.query(Notification).first():
        return
    owner = db.query(User).filter(User.role=="OWNER").first()
    designer = db.query(User).filter(User.role=="DESIGNER").first()
    if owner:
        create_notification(db, owner.email, "SYSTEM READY", "PLATE MANAGEMENT SYSTEM INITIALIZED.")
    if designer:
        create_notification(db, designer.email, "WELCOME", "YOU CAN START CREATING MASTERS NOW.")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_locations(db)
    seed_users(db)
    seed_notifications(db)
    db.close()

def menu_for(role):
    items = [("Dashboard", "/dashboard"), ("Show Record", "/show-record"), ("Usage Log", "/usage-log")]
    if role in ("OWNER", "TECH_TEAM", "DESIGNER"):
        items.insert(1, ("Plate Set Master", "/plate-sets/create"))
        items.insert(2, ("Replacement Plate Master", "/replacement-plates/create"))
        items.append(("Show Masters", "/show-masters"))
    if role in ("OWNER", "DESIGNER"):
        items.append(("Scrap Request", "/scrap/request"))
    if role == "OWNER":
        items.append(("Scrap Approval", "/scrap/approval"))
    if role in ("OWNER", "TECH_TEAM"):
        items.append(("Database Control", "/admin/users"))
    return items

def base_context(request: Request, db: Session, title: str):
    user = current_user(request, db)
    return {
        "request": request,
        "title": title,
        "user": user,
        "menu_items": menu_for(user.role) if user else [],
        "plate_age": plate_age,
    }

@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)

@app.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    return render_template("login.html", **base_context(request, db, "Login"), error=None)

@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    email = norm(email)
    user = db.query(User).filter(User.email == email, User.is_active == "YES").first()
    if not user or not verify_password(password, user.password_hash):
        return render_template("login.html", **base_context(request, db, "Login"), error="INVALID EMAIL OR PASSWORD.")
    request.session["user_email"] = user.email
    return RedirectResponse("/dashboard", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

@app.get("/dashboard")
def dashboard(request: Request, rack: str = "R01", db: Session = Depends(get_db)):
    user = require_login(request, db)
    notes_q = db.query(Notification).filter(Notification.user_email == user.email).order_by(Notification.id.desc())
    notifications = notes_q.limit(5).all()
    rack_counts = {}
    for section in ["A1","A2","A3","A4","A5","A6","B1","B2","B3","B4","B5","B6"]:
        location_ids = [x.location_id for x in db.query(Location).filter(Location.rack_no == rack, Location.section_code == section).all()]
        count = db.query(PlateSet).filter(PlateSet.location_id.in_(location_ids), PlateSet.status == "ACTIVE").count() if location_ids else 0
        rack_counts[section] = count
    return render_template("dashboard.html", **base_context(request, db, "Dashboard"),
                          rack=rack, racks=[f"R{i:02d}" for i in range(1,11)],
                          notifications=notifications, rack_counts=rack_counts)

@app.get("/notifications")
def all_notifications(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    notes = db.query(Notification).filter(Notification.user_email == user.email).order_by(Notification.id.desc()).all()
    return render_template("notifications.html", **base_context(request, db, "Notifications"), notifications=notes)

@app.get("/plate-sets/create")
def plate_set_form(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM", "DESIGNER")
    location = first_free_location(db)
    return render_template("plate_set_form.html", **base_context(request, db, "Create Plate Set"), next_location=location.location_id if location else "NO FREE LOCATION", saved=None, errors=[])

@app.post("/plate-sets/create")
def plate_set_create(
    request: Request,
    receiving_date: str = Form(...),
    job_id: str = Form(...),
    job_name: str = Form(...),
    party_name: str = Form(...),
    plate_set_id: str = Form(...),
    no_of_plates: int = Form(...),
    plate_size: str = Form(...),
    gripper_size_mm: int = Form(...),
    color_details: str = Form(...),
    remarks: str = Form(""),
    plate_from_party: str = Form(...),
    vendor_name: str = Form(""),
    vendor_plate_id: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM", "DESIGNER")
    errors = []
    receiving_date = norm(receiving_date)
    job_id = norm(job_id)
    job_name = norm(job_name)
    party_name = norm(party_name)
    plate_set_id = norm(plate_set_id)
    color_details = norm(color_details)
    remarks = norm(remarks)
    plate_from_party = norm(plate_from_party)
    vendor_name = norm(vendor_name)
    vendor_plate_id = norm(vendor_plate_id)
    plate_size = norm(plate_size)

    if db.query(PlateSet).filter(PlateSet.job_id == job_id).first():
        errors.append("JOB ID ALREADY EXISTS.")
    if db.query(PlateSet).filter(PlateSet.plate_set_id == plate_set_id).first():
        errors.append("PLATE SET ID ALREADY EXISTS.")
    if plate_from_party == "NO" and not vendor_name:
        errors.append("VENDOR NAME IS REQUIRED WHEN PLATE FROM PARTY IS NO.")
    if plate_size not in ("770X1080", "790X1080"):
        errors.append("INVALID PLATE SIZE.")
    location = first_free_location(db)
    if not location:
        errors.append("NO FREE LOCATION AVAILABLE.")
    if errors:
        return render_template("plate_set_form.html", **base_context(request, db, "Create Plate Set"), next_location=location.location_id if location else "NO FREE LOCATION", saved=None, errors=errors)

    row = PlateSet(
        receiving_date=receiving_date,
        job_id=job_id,
        job_name=job_name,
        party_name=party_name,
        plate_set_id=plate_set_id,
        no_of_plates=no_of_plates,
        plate_size=plate_size,
        gripper_size_mm=gripper_size_mm,
        color_details=color_details,
        remarks=remarks,
        plate_from_party=plate_from_party,
        vendor_name=vendor_name if plate_from_party == "NO" else None,
        vendor_plate_id=vendor_plate_id if plate_from_party == "NO" else None,
        location_id=location.location_id,
        status="ACTIVE",
        created_at=now_ts(),
    )
    db.add(row)
    location.status = "OCCUPIED"
    db.add(UsageLog(action_date=receiving_date, action_time=now_time(), plate_set_id=plate_set_id, action="IN", remarks="AUTO ENTRY ON MASTER CREATION"))
    db.commit()
    create_notification(db, user.email, "PLATE SET SAVED", f"PLATE SET {plate_set_id} WAS SAVED SUCCESSFULLY.")
    next_loc = first_free_location(db)
    return render_template("plate_set_form.html", **base_context(request, db, "Create Plate Set"), next_location=next_loc.location_id if next_loc else "NO FREE LOCATION", saved=plate_set_id, errors=[])

def color_code(color):
    mapping = {"CYAN":"CYAN","MAGENTA":"MGNT","YELLOW":"YLLW","BLACK":"BLCK","PANTONE":"PNTN"}
    return mapping.get(color, color[:4])

@app.get("/api/plate-context")
def api_plate_context(job_id: str, db: Session = Depends(get_db)):
    job_id = norm(job_id)
    plate = db.query(PlateSet).filter(PlateSet.job_id == job_id).first()
    if not plate:
        return {"found": False}
    return {"found": True, "plate_set_id": plate.plate_set_id, "location_id": plate.location_id}

@app.get("/replacement-plates/create")
def replacement_form(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM", "DESIGNER")
    return render_template("replacement_form.html", **base_context(request, db, "Create Replacement Plate"), saved=None, errors=[])

@app.post("/replacement-plates/create")
def replacement_create(request: Request, receiving_date: str = Form(...), job_id: str = Form(...), color: str = Form(...), plate_from_party: str = Form(...), vendor_name: str = Form(""), vendor_plate_id: str = Form(""), db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM", "DESIGNER")
    errors = []
    receiving_date = norm(receiving_date)
    job_id = norm(job_id)
    color = norm(color)
    plate_from_party = norm(plate_from_party)
    vendor_name = norm(vendor_name)
    vendor_plate_id = norm(vendor_plate_id)

    plate = db.query(PlateSet).filter(PlateSet.job_id == job_id, PlateSet.status == "ACTIVE").first()
    if not plate:
        errors.append("JOB ID NOT FOUND IN ACTIVE PLATE SET MASTER.")
    if plate_from_party == "NO" and not vendor_name:
        errors.append("VENDOR NAME IS REQUIRED WHEN PLATE FROM PARTY IS NO.")
    if errors:
        return render_template("replacement_form.html", **base_context(request, db, "Create Replacement Plate"), saved=None, errors=errors)

    replacement_plate_id = f"{plate.plate_set_id}-{color_code(color)}-{receiving_date.replace('/','')}"
    if db.query(ReplacementPlate).filter(ReplacementPlate.replacement_plate_id == replacement_plate_id).first():
        errors.append("REPLACEMENT PLATE ID ALREADY EXISTS.")
        return render_template("replacement_form.html", **base_context(request, db, "Create Replacement Plate"), saved=None, errors=errors)

    row = ReplacementPlate(receiving_date=receiving_date, job_id=job_id, plate_set_id=plate.plate_set_id, color=color, replacement_plate_id=replacement_plate_id, location_id=plate.location_id, plate_from_party=plate_from_party, vendor_name=vendor_name if plate_from_party == "NO" else None, vendor_plate_id=vendor_plate_id if plate_from_party == "NO" else None, status="ACTIVE", created_at=now_ts())
    db.add(row)
    db.commit()
    create_notification(db, user.email, "REPLACEMENT SAVED", f"REPLACEMENT {replacement_plate_id} WAS SAVED SUCCESSFULLY.")
    return render_template("replacement_form.html", **base_context(request, db, "Create Replacement Plate"), saved=replacement_plate_id, errors=[])

@app.get("/show-record")
def show_record(request: Request, job_id: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    job_id = norm(job_id)
    plate = db.query(PlateSet).filter(PlateSet.job_id == job_id).first() if job_id else None
    replacements = db.query(ReplacementPlate).filter(ReplacementPlate.job_id == job_id).order_by(ReplacementPlate.id.desc()).all() if job_id else []
    plate_stats = plate_usage_display(db, plate.plate_set_id) if plate else None
    repl_rows = []
    for r in replacements:
        s = replacement_usage_display(db, r)
        repl_rows.append((r, s))
    return render_template("show_record.html", **base_context(request, db, "Show Record"), query=job_id, plate=plate, plate_stats=plate_stats, replacements=repl_rows)

@app.get("/show-masters")
def show_masters(request: Request, master: str = "PLATE_SET_MASTER", db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM", "DESIGNER")
    master = norm(master)
    headers, rows = [], []
    if master == "PLATE_SET_MASTER":
        headers = ["RECEIVING DATE","JOB ID","JOB NAME","PARTY NAME","PLATE SET ID","NO. OF PLATES","PLATE SIZE","GRIPPER SIZE MM","COLOR DETAILS","REMARKS","PLATE FROM PARTY","VENDOR NAME","VENDOR PLATE ID","LOCATION ID","LAST USED DATE","USAGE COUNT","DAYS SINCE LAST USED","AGE OF PLATE","STATUS"]
        data = db.query(PlateSet).order_by(PlateSet.id.desc()).all()
        for p in data:
            s = plate_usage_display(db, p.plate_set_id)
            rows.append([p.receiving_date,p.job_id,p.job_name,p.party_name,p.plate_set_id,p.no_of_plates,p.plate_size,p.gripper_size_mm,p.color_details,p.remarks or "",p.plate_from_party,p.vendor_name or "",p.vendor_plate_id or "",p.location_id,s["last_used_date"],s["usage_count"],s["days_since_last_used"],plate_age(p.receiving_date),p.status])
    elif master == "REPLACEMENT_PLATE_MASTER":
        headers = ["RECEIVING DATE","JOB ID","PLATE SET ID","COLOUR OF REPLACEMENT","REPLACEMENT PLATE ID","LOCATION ID","PLATE FROM PARTY","VENDOR NAME","VENDOR PLATE ID","LAST USED DATE","USAGE COUNT","DAYS SINCE LAST USED","AGE OF PLATE","STATUS"]
        data = db.query(ReplacementPlate).order_by(ReplacementPlate.id.desc()).all()
        for r in data:
            s = replacement_usage_display(db, r)
            rows.append([r.receiving_date,r.job_id,r.plate_set_id,r.color,r.replacement_plate_id,r.location_id,r.plate_from_party,r.vendor_name or "",r.vendor_plate_id or "",s["last_used_date"],s["usage_count"],s["days_since_last_used"],plate_age(r.receiving_date),r.status])
    else:
        master = "LOCATION_MASTER"
        headers = ["LOCATION ID","RACK NO","SHELF","SECTION","POSITION","STATUS"]
        data = db.query(Location).order_by(Location.id.asc()).all()
        for l in data:
            rows.append([l.location_id,l.rack_no,l.shelf_code,l.section_code,l.position_no,l.status])
    return render_template("show_masters.html", **base_context(request, db, "Show Masters"), master=master, headers=headers, rows=rows)

@app.get("/usage-log")
def usage_log(request: Request, plate_set_id: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    plate_set_id = norm(plate_set_id)
    q = db.query(UsageLog)
    if plate_set_id:
        q = q.filter(UsageLog.plate_set_id == plate_set_id)
    logs = q.order_by(UsageLog.id.desc()).all()
    return render_template("usage_log.html", **base_context(request, db, "Usage Log"), logs=logs, plate_set_id=plate_set_id)

@app.post("/usage-log")
def usage_log_create(request: Request, plate_set_id: str = Form(...), action: str = Form(...), remarks: str = Form(""), db: Session = Depends(get_db)):
    user = require_login(request, db)
    plate_set_id = norm(plate_set_id)
    action = norm(action)
    remarks = norm(remarks)
    plate = db.query(PlateSet).filter(PlateSet.plate_set_id == plate_set_id, PlateSet.status == "ACTIVE").first()
    if not plate:
        return RedirectResponse("/usage-log?plate_set_id=" + plate_set_id, status_code=302)
    db.add(UsageLog(action_date=now_date(), action_time=now_time(), plate_set_id=plate_set_id, action=action, remarks=remarks))
    db.commit()
    return RedirectResponse("/usage-log?plate_set_id=" + plate_set_id, status_code=302)

@app.get("/scrap/request")
def scrap_request_page(request: Request, plate_set_id: str = "", db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "DESIGNER")
    plate_set_id = norm(plate_set_id)
    repls = db.query(ReplacementPlate).filter(ReplacementPlate.plate_set_id == plate_set_id, ReplacementPlate.status == "ACTIVE").all() if plate_set_id else []
    return render_template("scrap_request.html", **base_context(request, db, "Scrap Request"), replacements=repls, plate_set_id=plate_set_id)

@app.post("/scrap/request/plate-set")
def scrap_request_plate_set(request: Request, identifier: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "DESIGNER")
    ident = norm(identifier)
    reason = norm(reason)
    plate = db.query(PlateSet).filter((PlateSet.job_id == ident) | (PlateSet.plate_set_id == ident)).first()
    if not plate:
        return RedirectResponse("/scrap/request", status_code=302)
    db.add(ScrapRequest(request_type="PLATE_SET", target_job_id=plate.job_id, target_plate_set_id=plate.plate_set_id, requested_by_email=user.email, reason=reason, status="PENDING", created_at=now_ts()))
    db.commit()
    owner = db.query(User).filter(User.role == "OWNER").first()
    if owner:
        create_notification(db, owner.email, "NEW SCRAP REQUEST", f"PLATE SET SCRAP REQUEST RECEIVED FOR {plate.plate_set_id}.")
    create_notification(db, user.email, "REQUEST SUBMITTED", f"YOUR SCRAP REQUEST FOR {plate.plate_set_id} HAS BEEN SUBMITTED.")
    return RedirectResponse("/scrap/request", status_code=302)

@app.post("/scrap/request/replacement")
def scrap_request_replacement(request: Request, plate_set_id: str = Form(...), replacement_plate_id: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "DESIGNER")
    plate_set_id = norm(plate_set_id)
    replacement_plate_id = norm(replacement_plate_id)
    reason = norm(reason)
    db.add(ScrapRequest(request_type="REPLACEMENT", target_plate_set_id=plate_set_id, target_replacement_plate_id=replacement_plate_id, requested_by_email=user.email, reason=reason, status="PENDING", created_at=now_ts()))
    db.commit()
    owner = db.query(User).filter(User.role == "OWNER").first()
    if owner:
        create_notification(db, owner.email, "NEW SCRAP REQUEST", f"REPLACEMENT SCRAP REQUEST RECEIVED FOR {replacement_plate_id}.")
    create_notification(db, user.email, "REQUEST SUBMITTED", f"YOUR SCRAP REQUEST FOR {replacement_plate_id} HAS BEEN SUBMITTED.")
    return RedirectResponse(f"/scrap/request?plate_set_id={plate_set_id}", status_code=302)

@app.get("/scrap/approval")
def scrap_approval(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER")
    pending = db.query(ScrapRequest).order_by(ScrapRequest.id.desc()).all()
    return render_template("scrap_approval.html", **base_context(request, db, "Scrap Approval"), requests=pending)

@app.post("/scrap/approval/{request_id}/approve")
def approve_scrap(request_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER")
    req = db.query(ScrapRequest).filter(ScrapRequest.id == request_id, ScrapRequest.status == "PENDING").first()
    if req:
        if req.request_type == "PLATE_SET":
            plate = db.query(PlateSet).filter(PlateSet.plate_set_id == req.target_plate_set_id).first()
            if plate:
                plate.status = "SCRAPPED"
                loc = db.query(Location).filter(Location.location_id == plate.location_id).first()
                if loc:
                    loc.status = "FREE"
                replacements = db.query(ReplacementPlate).filter(ReplacementPlate.plate_set_id == plate.plate_set_id).all()
                for r in replacements:
                    r.status = "SCRAPPED"
        elif req.request_type == "REPLACEMENT":
            repl = db.query(ReplacementPlate).filter(ReplacementPlate.replacement_plate_id == req.target_replacement_plate_id).first()
            if repl:
                repl.status = "SCRAPPED"
        req.status = "APPROVED"
        req.decided_at = now_ts()
        db.commit()
        create_notification(db, req.requested_by_email, "REQUEST APPROVED", f"YOUR SCRAP REQUEST HAS BEEN APPROVED.")
    return RedirectResponse("/scrap/approval", status_code=302)

@app.post("/scrap/approval/{request_id}/reject")
def reject_scrap(request_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER")
    req = db.query(ScrapRequest).filter(ScrapRequest.id == request_id, ScrapRequest.status == "PENDING").first()
    if req:
        req.status = "REJECTED"
        req.decided_at = now_ts()
        db.commit()
        create_notification(db, req.requested_by_email, "REQUEST REJECTED", f"YOUR SCRAP REQUEST HAS BEEN REJECTED.")
    return RedirectResponse("/scrap/approval", status_code=302)

@app.get("/admin/users")
def user_admin(request: Request, db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM")
    users = db.query(User).order_by(User.id.asc()).all()
    return render_template("user_admin.html", **base_context(request, db, "Database Control"), users=users)

@app.post("/admin/users/{user_id}")
def user_admin_update(request: Request, user_id: int, full_name: str = Form(...), email: str = Form(...), password: str = Form(""), db: Session = Depends(get_db)):
    user = require_login(request, db)
    require_roles(user, "OWNER", "TECH_TEAM")
    row = db.query(User).filter(User.id == user_id).first()
    if row:
        row.full_name = norm(full_name)
        row.email = norm(email)
        if password:
            row.password_hash = hash_password(password)
        db.commit()
    return RedirectResponse("/admin/users", status_code=302)

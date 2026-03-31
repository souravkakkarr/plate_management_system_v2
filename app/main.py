from datetime import datetime, date
from pathlib import Path
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, get_db, SessionLocal
from . import models
from .auth import verify_password, hash_password, require_permission, get_current_user
from .services import (
    create_plate_set,
    create_replacement_plate,
    get_plate_set_usage_summary,
    get_replacement_usage_summary,
    rack_visualization_data,
    create_notification,
    normalize_upper,
)

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title='Plate Management System')
app.add_middleware(SessionMiddleware, secret_key='replace-this-with-env-secret')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

Base.metadata.create_all(bind=engine)


def seed_data():
    db = SessionLocal()
    try:
        if not db.query(models.User).first():
            users = [
                ('souravkakkar2k3@gmail.com', 'OWNER', 'owner', 'owner123'),
                ('souravkakkarr@gmail.com', 'TECHNICAL TEAM', 'technical_team', 'tech123'),
                ('Designer_of_company@gmail.com', 'DESIGNER', 'designer', 'designer123'),
                ('Plate_manager_of_company@gmail.com', 'PLATE MANAGER', 'plate_manager', 'plate123'),
            ]
            for email, name, role, password in users:
                db.add(models.User(email=email, full_name=name, role=role, password_hash=hash_password(password), is_active=True))
            db.commit()
        if not db.query(models.LocationMaster).first():
            sort_order = 1
            for rack in ['R01', 'R02', 'R03']:
                for section in ['A1','A2','A3','A4','A5','A6','B1','B2','B3','B4','B5','B6']:
                    shelf_group = section[0]
                    for slot in range(1, 6):
                        slot_no = f'{slot:02d}'
                        location_id = f'{rack}-{section}-{slot_no}'
                        db.add(models.LocationMaster(
                            location_id=location_id,
                            rack_no=rack,
                            shelf_group=shelf_group,
                            section_code=section,
                            slot_no=slot_no,
                            sort_order=sort_order,
                        ))
                        sort_order += 1
            db.commit()
        if not db.query(models.PlateSetMaster).first():
            owner = db.query(models.User).filter_by(role='owner').first()
            create_plate_set(db, owner.id, {
                'job_id': 'JOB1001', 'job_name': 'SIDDHI AUTO CARTON', 'party_name': 'SIDDHI PACK',
                'plate_set_id': 'SIDDHI-CD102-AUTO-001', 'number_of_plates': 4,
                'plate_size': '770X1080', 'gripper_size_mm': 12, 'color_details': 'C M Y K',
                'plate_from_party': 'YES', 'vendor_name': None,
                'remarks': 'DUMMY SEED RECORD', 'receiving_date': date(2026, 3, 20)
            })
            create_plate_set(db, owner.id, {
                'job_id': 'JOB1002', 'job_name': 'MONARCH PHARMA', 'party_name': 'MONARCH',
                'plate_set_id': 'MONARCH-PHARMA-002', 'number_of_plates': 5,
                'plate_size': '790X1080', 'gripper_size_mm': 14, 'color_details': 'C M Y K + P',
                'plate_from_party': 'NO', 'vendor_name': 'GLOBAL PLATES',
                'remarks': 'DUMMY SEED RECORD', 'receiving_date': date(2026, 3, 22)
            })
            create_replacement_plate(db, owner.id, {
                'job_id': 'JOB1001',
                'replacement_plate_receiving_date': date(2026, 3, 25),
                'colour_of_replacement': 'MAGENTA',
                'plate_from_party': 'YES',
                'vendor_name': None,
            })
            ps1 = db.query(models.PlateSetMaster).filter_by(job_id='JOB1001').first()
            ps2 = db.query(models.PlateSetMaster).filter_by(job_id='JOB1002').first()
            db.add_all([
                models.UsageLog(plate_set_id=ps1.plate_set_id, action_type='OUT', action_date=date(2026,3,26), action_time='10:30:00', remarks='SEED OUT', created_by_user_id=owner.id),
                models.UsageLog(plate_set_id=ps1.plate_set_id, action_type='IN', action_date=date(2026,3,26), action_time='18:00:00', remarks='SEED IN', created_by_user_id=owner.id),
                models.UsageLog(plate_set_id=ps2.plate_set_id, action_type='OUT', action_date=date(2026,3,27), action_time='11:00:00', remarks='SEED OUT', created_by_user_id=owner.id),
            ])
            db.commit()
    finally:
        db.close()


seed_data()


def context(request: Request, **kwargs):
    return {'request': request, 'current_user': get_current_user(request), 'date': date, **kwargs}


@app.get('/', response_class=HTMLResponse)
def root(request: Request):
    if get_current_user(request):
        return RedirectResponse('/dashboard', status_code=303)
    return RedirectResponse('/login', status_code=303)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse('login.html', context(request))


@app.post('/login')
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email.strip(), models.User.is_active == True).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse('login.html', context(request, error='Invalid credentials.'))
    request.session['user_id'] = user.id
    return RedirectResponse('/dashboard', status_code=303)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=303)


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request, rack_no: str = 'R01', db: Session = Depends(get_db)):
    user = require_permission(request, 'view_dashboard')
    notifications = []
    if user.role in {'owner', 'designer'}:
        notifications = db.query(models.Notification).filter(models.Notification.user_id == user.id).order_by(models.Notification.created_at.desc()).limit(10).all()
    rack_data = rack_visualization_data(db, rack_no)
    racks = [r[0] for r in db.query(models.LocationMaster.rack_no).distinct().order_by(models.LocationMaster.rack_no).all()]
    return templates.TemplateResponse('dashboard.html', context(request, rack_data=rack_data, rack_no=rack_no, racks=racks, notifications=notifications))


@app.get('/plate-sets/new', response_class=HTMLResponse)
def plate_set_form(request: Request, db: Session = Depends(get_db)):
    require_permission(request, 'create_plate_set')
    from .services import get_first_vacant_location
    location = get_first_vacant_location(db)
    return templates.TemplateResponse('plate_set_form.html', context(request, location=location, success=None, error=None))


@app.post('/plate-sets/new', response_class=HTMLResponse)
def plate_set_create(
    request: Request,
    job_id: str = Form(...),
    job_name: str = Form(...),
    party_name: str = Form(...),
    plate_set_id: str = Form(...),
    number_of_plates: int = Form(...),
    plate_size: str = Form(...),
    gripper_size_mm: int = Form(...),
    color_details: str = Form(...),
    plate_from_party: str = Form(...),
    vendor_name: str = Form(''),
    remarks: str = Form(''),
    receiving_date: str = Form(...),
    db: Session = Depends(get_db),
):
    user = require_permission(request, 'create_plate_set')
    from .services import get_first_vacant_location
    try:
        plate_set = create_plate_set(db, user.id, {
            'job_id': job_id,
            'job_name': job_name,
            'party_name': party_name,
            'plate_set_id': plate_set_id,
            'number_of_plates': number_of_plates,
            'plate_size': plate_size,
            'gripper_size_mm': gripper_size_mm,
            'color_details': color_details,
            'plate_from_party': plate_from_party,
            'vendor_name': vendor_name,
            'remarks': remarks,
            'receiving_date': datetime.strptime(receiving_date, '%Y-%m-%d').date(),
        })
        location = db.query(models.LocationMaster).filter_by(location_id=plate_set.location_id).first()
        return templates.TemplateResponse('plate_set_form.html', context(request, location=location, success=f'Plate Set created successfully. Assigned location: {plate_set.location_id}', error=None))
    except Exception as exc:
        location = get_first_vacant_location(db)
        return templates.TemplateResponse('plate_set_form.html', context(request, location=location, error=str(exc), success=None))


@app.get('/replacement-plates/new', response_class=HTMLResponse)
def replacement_form(request: Request):
    require_permission(request, 'create_replacement_plate')
    return templates.TemplateResponse('replacement_form.html', context(request, fetched=None, success=None, error=None))


@app.post('/replacement-plates/fetch', response_class=HTMLResponse)
def replacement_fetch(request: Request, job_id: str = Form(...), db: Session = Depends(get_db)):
    require_permission(request, 'create_replacement_plate')
    plate_set = db.query(models.PlateSetMaster).filter_by(job_id=normalize_upper(job_id)).first()
    if not plate_set:
        return templates.TemplateResponse('replacement_form.html', context(request, fetched=None, error='No plate set found for this Job ID.', success=None))
    return templates.TemplateResponse('replacement_form.html', context(request, fetched=plate_set, error=None, success=None))


@app.post('/replacement-plates/new', response_class=HTMLResponse)
def replacement_create(
    request: Request,
    job_id: str = Form(...),
    replacement_plate_receiving_date: str = Form(...),
    colour_of_replacement: str = Form(...),
    plate_from_party: str = Form(...),
    vendor_name: str = Form(''),
    db: Session = Depends(get_db),
):
    user = require_permission(request, 'create_replacement_plate')
    plate_set = db.query(models.PlateSetMaster).filter_by(job_id=normalize_upper(job_id)).first()
    try:
        replacement = create_replacement_plate(db, user.id, {
            'job_id': job_id,
            'replacement_plate_receiving_date': datetime.strptime(replacement_plate_receiving_date, '%Y-%m-%d').date(),
            'colour_of_replacement': colour_of_replacement,
            'plate_from_party': plate_from_party,
            'vendor_name': vendor_name,
        })
        return templates.TemplateResponse('replacement_form.html', context(request, fetched=plate_set, success=f'Replacement Plate created: {replacement.replacement_plate_id}', error=None))
    except Exception as exc:
        return templates.TemplateResponse('replacement_form.html', context(request, fetched=plate_set, error=str(exc), success=None))


@app.get('/records', response_class=HTMLResponse)
def records_page(request: Request):
    require_permission(request, 'view_records')
    return templates.TemplateResponse('records.html', context(request, plate_set=None, replacement_rows=[], searched=False))


@app.post('/records', response_class=HTMLResponse)
def records_search(request: Request, job_id: str = Form(...), db: Session = Depends(get_db)):
    require_permission(request, 'view_records')
    search_id = normalize_upper(job_id)
    plate_set = db.query(models.PlateSetMaster).filter_by(job_id=search_id).first()
    replacements = db.query(models.ReplacementPlateMaster).filter_by(job_id=search_id).order_by(models.ReplacementPlateMaster.id).all()
    plate_usage = get_plate_set_usage_summary(db, plate_set.plate_set_id) if plate_set else None
    replacement_rows = []
    for rep in replacements:
        usage = get_replacement_usage_summary(db, rep)
        replacement_rows.append((rep, usage))
    return templates.TemplateResponse('records.html', context(request, plate_set=plate_set, plate_usage=plate_usage, replacement_rows=replacement_rows, searched=True, searched_job_id=search_id))


@app.get('/usage-log', response_class=HTMLResponse)
def usage_log_page(request: Request, db: Session = Depends(get_db)):
    require_permission(request, 'use_usage_log')
    logs = db.query(models.UsageLog).order_by(models.UsageLog.created_at.desc()).limit(50).all()
    return templates.TemplateResponse('usage_log.html', context(request, logs=logs, success=None, error=None))


@app.post('/usage-log', response_class=HTMLResponse)
def usage_log_create(
    request: Request,
    plate_set_id: str = Form(...),
    action_type: str = Form(...),
    action_date: str = Form(...),
    action_time: str = Form(...),
    remarks: str = Form(''),
    db: Session = Depends(get_db),
):
    user = require_permission(request, 'use_usage_log')
    normalized_plate_set = normalize_upper(plate_set_id)
    plate_set = db.query(models.PlateSetMaster).filter_by(plate_set_id=normalized_plate_set).first()
    if not plate_set:
        logs = db.query(models.UsageLog).order_by(models.UsageLog.created_at.desc()).limit(50).all()
        return templates.TemplateResponse('usage_log.html', context(request, logs=logs, error='Plate Set ID not found.', success=None))
    db.add(models.UsageLog(
        plate_set_id=plate_set.plate_set_id,
        action_type=normalize_upper(action_type),
        action_date=datetime.strptime(action_date, '%Y-%m-%d').date(),
        action_time=action_time,
        remarks=normalize_upper(remarks),
        created_by_user_id=user.id,
    ))
    db.commit()
    logs = db.query(models.UsageLog).order_by(models.UsageLog.created_at.desc()).limit(50).all()
    return templates.TemplateResponse('usage_log.html', context(request, logs=logs, success='Usage log added.', error=None))


@app.get('/scrap-requests', response_class=HTMLResponse)
def scrap_request_page(request: Request):
    require_permission(request, 'raise_scrap_request')
    return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=None, replacements=[], success=None, error=None, mode=None))


@app.post('/scrap-requests/plate-set/search', response_class=HTMLResponse)
def scrap_plate_set_search(request: Request, search_value: str = Form(...), db: Session = Depends(get_db)):
    require_permission(request, 'raise_scrap_request')
    sv = normalize_upper(search_value)
    plate_set = db.query(models.PlateSetMaster).filter(
        (models.PlateSetMaster.job_id == sv) | (models.PlateSetMaster.plate_set_id == sv)
    ).first()
    return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=plate_set, replacements=[], mode='plate_set', error=None if plate_set else 'No plate set found.', success=None))


@app.post('/scrap-requests/plate-set', response_class=HTMLResponse)
def scrap_plate_set_request(request: Request, plate_set_id: str = Form(...), reason: str = Form(''), db: Session = Depends(get_db)):
    user = require_permission(request, 'raise_scrap_request')
    psid = normalize_upper(plate_set_id)
    plate_set = db.query(models.PlateSetMaster).filter_by(plate_set_id=psid).first()
    if not plate_set:
        return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=None, replacements=[], mode='plate_set', error='Plate set not found.', success=None))
    sr = models.ScrapRequest(request_type='plate_set', target_plate_set_id=plate_set.plate_set_id, target_job_id=plate_set.job_id, requested_by_user_id=user.id, request_reason=normalize_upper(reason))
    db.add(sr)
    db.flush()
    owner = db.query(models.User).filter_by(role='owner').first()
    create_notification(db, owner.id, 'New Plate Set Scrap Request', f'Plate Set {plate_set.plate_set_id} requested for scrap by {user.email}', 'scrap')
    create_notification(db, user.id, 'Scrap Request Submitted', f'Your plate set scrap request for {plate_set.plate_set_id} has been submitted.', 'scrap')
    db.commit()
    return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=plate_set, replacements=[], mode='plate_set', success='Scrap request submitted.', error=None))


@app.post('/scrap-requests/replacement/search', response_class=HTMLResponse)
def scrap_replacement_search(request: Request, plate_set_id: str = Form(...), db: Session = Depends(get_db)):
    require_permission(request, 'raise_scrap_request')
    replacements = db.query(models.ReplacementPlateMaster).filter_by(plate_set_id=normalize_upper(plate_set_id)).all()
    return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=None, replacements=replacements, mode='replacement', error=None if replacements else 'No replacement plates found for this Plate Set ID.', success=None, selected_plate_set_id=normalize_upper(plate_set_id)))


@app.post('/scrap-requests/replacement', response_class=HTMLResponse)
def scrap_replacement_request(request: Request, replacement_plate_id: str = Form(...), reason: str = Form(''), db: Session = Depends(get_db)):
    user = require_permission(request, 'raise_scrap_request')
    replacement = db.query(models.ReplacementPlateMaster).filter_by(replacement_plate_id=normalize_upper(replacement_plate_id)).first()
    if not replacement:
        return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=None, replacements=[], mode='replacement', error='Replacement plate not found.', success=None))
    db.add(models.ScrapRequest(request_type='replacement_plate', target_plate_set_id=replacement.plate_set_id, target_replacement_plate_id=replacement.replacement_plate_id, target_job_id=replacement.job_id, requested_by_user_id=user.id, request_reason=normalize_upper(reason)))
    owner = db.query(models.User).filter_by(role='owner').first()
    create_notification(db, owner.id, 'New Replacement Scrap Request', f'Replacement Plate {replacement.replacement_plate_id} requested for scrap by {user.email}', 'scrap')
    create_notification(db, user.id, 'Scrap Request Submitted', f'Your replacement plate scrap request for {replacement.replacement_plate_id} has been submitted.', 'scrap')
    db.commit()
    replacements = db.query(models.ReplacementPlateMaster).filter_by(plate_set_id=replacement.plate_set_id).all()
    return templates.TemplateResponse('scrap_requests.html', context(request, plate_set=None, replacements=replacements, mode='replacement', selected_plate_set_id=replacement.plate_set_id, success='Scrap request submitted.', error=None))


@app.get('/scrap-approval', response_class=HTMLResponse)
def scrap_approval_page(request: Request, db: Session = Depends(get_db)):
    require_permission(request, 'approve_scrap_request')
    pending = db.query(models.ScrapRequest).filter_by(request_status='Pending').order_by(models.ScrapRequest.requested_at.desc()).all()
    return templates.TemplateResponse('scrap_approval.html', context(request, pending=pending))


@app.post('/scrap-approval/{request_id}/{decision}', response_class=HTMLResponse)
def scrap_decide(request_id: int, decision: str, request: Request, note: str = Form(''), db: Session = Depends(get_db)):
    user = require_permission(request, 'approve_scrap_request')
    sr = db.query(models.ScrapRequest).filter_by(id=request_id).first()
    if sr and sr.request_status == 'Pending':
        sr.request_status = 'Approved' if decision == 'approve' else 'Rejected'
        sr.approved_by_user_id = user.id
        sr.decision_note = note
        sr.decided_at = datetime.now()
        if decision == 'approve':
            if sr.request_type == 'plate_set':
                plate_set = db.query(models.PlateSetMaster).filter_by(plate_set_id=sr.target_plate_set_id).first()
                if plate_set:
                    plate_set.status = 'SCRAPPED'
            else:
                replacement = db.query(models.ReplacementPlateMaster).filter_by(replacement_plate_id=sr.target_replacement_plate_id).first()
                if replacement:
                    replacement.status = 'SCRAPPED'
        create_notification(db, sr.requested_by_user_id, f'Scrap Request {sr.request_status}', f'Your {sr.request_type} scrap request has been {sr.request_status.lower()}.', 'scrap')
        db.commit()
    return RedirectResponse('/scrap-approval', status_code=303)


@app.get('/database-control', response_class=HTMLResponse)
def database_control(request: Request, db: Session = Depends(get_db), success: str | None = None, error: str | None = None):
    require_permission(request, 'database_control')
    users = db.query(models.User).order_by(models.User.id).all()
    plate_sets = db.query(models.PlateSetMaster).order_by(models.PlateSetMaster.id.desc()).limit(20).all()
    replacements = db.query(models.ReplacementPlateMaster).order_by(models.ReplacementPlateMaster.id.desc()).limit(20).all()
    return templates.TemplateResponse('database_control.html', context(request, users=users, plate_sets=plate_sets, replacements=replacements, success=success, error=error))


@app.post('/database-control/users/{user_id}', response_class=HTMLResponse)
def update_user(user_id: int, request: Request, full_name: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    require_permission(request, 'database_control')
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        return database_control(request, db, error='User not found.')
    normalized_email = email.strip()
    normalized_name = normalize_upper(full_name)
    existing = db.query(models.User).filter(models.User.email == normalized_email, models.User.id != user_id).first()
    if existing:
        return database_control(request, db, error='Email already exists for another authorized user.')
    user.email = normalized_email
    user.full_name = normalized_name
    db.commit()
    return database_control(request, db, success='Authorized user updated successfully.')


@app.get('/master-tables', response_class=HTMLResponse)
def master_tables(request: Request, db: Session = Depends(get_db)):
    require_permission(request, 'view_master_tables')
    plate_sets = db.query(models.PlateSetMaster).order_by(models.PlateSetMaster.id.desc()).all()
    replacements = db.query(models.ReplacementPlateMaster).order_by(models.ReplacementPlateMaster.id.desc()).all()
    return templates.TemplateResponse('master_tables.html', context(request, plate_sets=plate_sets, replacements=replacements))

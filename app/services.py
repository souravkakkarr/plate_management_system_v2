from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models

COLOUR_CODE_MAP = {
    'CYAN': 'CYAN',
    'MAGENTA': 'MGNT',
    'YELLOW': 'YLLW',
    'BLACK': 'BLCK',
    'PANTONE': 'PNTN',
}


def normalize_upper(value: str | None):
    if value is None:
        return None
    value = value.strip().upper()
    return value or None


def get_first_vacant_location(db: Session):
    active_locations = {
        row[0] for row in db.query(models.PlateSetMaster.location_id)
        .filter(models.PlateSetMaster.status == 'ACTIVE').all()
    }
    locations = db.query(models.LocationMaster).order_by(models.LocationMaster.sort_order.asc()).all()
    for loc in locations:
        if loc.location_id not in active_locations:
            return loc
    return None


def create_notification(db: Session, user_id: int, title: str, message: str, notification_type: str = 'info'):
    db.add(models.Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
    ))


def create_plate_set(db: Session, current_user_id: int, payload: dict):
    payload = {k: normalize_upper(v) if isinstance(v, str) else v for k, v in payload.items()}
    existing_job = db.query(models.PlateSetMaster).filter(models.PlateSetMaster.job_id == payload['job_id']).first()
    if existing_job:
        raise ValueError('Job ID already exists.')
    existing_plate_set = db.query(models.PlateSetMaster).filter(models.PlateSetMaster.plate_set_id == payload['plate_set_id']).first()
    if existing_plate_set:
        raise ValueError('Plate Set ID already exists.')
    if payload['plate_from_party'] not in {'YES', 'NO'}:
        raise ValueError('Plate From Party must be YES or NO.')
    if payload['plate_from_party'] == 'NO' and not payload.get('vendor_name'):
        raise ValueError('Vendor Name is required when Plate From Party is NO.')
    if payload['plate_from_party'] == 'YES':
        payload['vendor_name'] = None

    location = get_first_vacant_location(db)
    if not location:
        raise ValueError('No vacant location available in Location Master.')

    plate_set = models.PlateSetMaster(
        job_id=payload['job_id'],
        job_name=payload['job_name'],
        party_name=payload['party_name'],
        plate_set_id=payload['plate_set_id'],
        number_of_plates=payload['number_of_plates'],
        plate_size=payload['plate_size'],
        gripper_size_mm=payload['gripper_size_mm'],
        color_details=payload['color_details'],
        plate_from_party=payload['plate_from_party'],
        vendor_name=payload.get('vendor_name'),
        remarks=payload.get('remarks') or None,
        receiving_date=payload['receiving_date'],
        location_id=location.location_id,
        status='ACTIVE',
        created_by_user_id=current_user_id,
    )
    db.add(plate_set)
    db.flush()
    usage = models.UsageLog(
        plate_set_id=plate_set.plate_set_id,
        action_type='IN',
        action_date=payload['receiving_date'],
        action_time=datetime.now().strftime('%H:%M:%S'),
        remarks='AUTO-CREATED ON PLATE SET MASTER CREATION',
        created_by_user_id=current_user_id,
    )
    db.add(usage)
    db.commit()
    return plate_set


def create_replacement_plate(db: Session, current_user_id: int, payload: dict):
    payload = {k: normalize_upper(v) if isinstance(v, str) else v for k, v in payload.items()}
    plate_set = db.query(models.PlateSetMaster).filter(models.PlateSetMaster.job_id == payload['job_id']).first()
    if not plate_set:
        raise ValueError('No plate set found for this Job ID.')
    if payload['plate_from_party'] not in {'YES', 'NO'}:
        raise ValueError('Plate From Party must be YES or NO.')
    if payload['plate_from_party'] == 'NO' and not payload.get('vendor_name'):
        raise ValueError('Vendor Name is required when Plate From Party is NO.')
    if payload['plate_from_party'] == 'YES':
        payload['vendor_name'] = None

    colour_code = COLOUR_CODE_MAP[payload['colour_of_replacement']]
    date_token = payload['replacement_plate_receiving_date'].strftime('%d%m%Y')
    replacement_plate_id = f"{plate_set.plate_set_id}-{colour_code}-{date_token}"
    existing = db.query(models.ReplacementPlateMaster).filter(
        models.ReplacementPlateMaster.replacement_plate_id == replacement_plate_id
    ).first()
    if existing:
        raise ValueError('Replacement Plate ID already exists.')

    replacement = models.ReplacementPlateMaster(
        replacement_plate_receiving_date=payload['replacement_plate_receiving_date'],
        job_id=plate_set.job_id,
        plate_set_id=plate_set.plate_set_id,
        colour_of_replacement=payload['colour_of_replacement'],
        replacement_plate_id=replacement_plate_id,
        location_id=plate_set.location_id,
        status='ACTIVE',
        plate_from_party=payload['plate_from_party'],
        vendor_name=payload.get('vendor_name'),
        created_by_user_id=current_user_id,
    )
    db.add(replacement)
    db.commit()
    return replacement


def get_plate_set_usage_summary(db: Session, plate_set_id: str):
    usage_rows = db.query(models.UsageLog).filter(models.UsageLog.plate_set_id == plate_set_id).all()
    if not usage_rows:
        return {'last_used_date': 'No usage found', 'usage_count': 'No usage found', 'days_since_last_used': 'No usage found'}
    out_rows = [row for row in usage_rows if row.action_type == 'OUT']
    if not out_rows:
        return {'last_used_date': 'No usage found', 'usage_count': 'No usage found', 'days_since_last_used': 'No usage found'}
    latest = max(out_rows, key=lambda x: x.action_date)
    return {
        'last_used_date': latest.action_date.strftime('%d/%m/%Y'),
        'usage_count': str(len(out_rows)),
        'days_since_last_used': str((date.today() - latest.action_date).days),
    }


def get_replacement_usage_summary(db: Session, replacement: models.ReplacementPlateMaster):
    usage_rows = db.query(models.UsageLog).filter(
        models.UsageLog.plate_set_id == replacement.plate_set_id,
        models.UsageLog.action_type == 'OUT',
        models.UsageLog.action_date >= replacement.replacement_plate_receiving_date,
    ).all()
    if not usage_rows:
        return {'last_used_date': 'No usage found', 'usage_count': 'No usage found', 'days_since_last_used': 'No usage found'}
    latest = max(usage_rows, key=lambda x: x.action_date)
    return {
        'last_used_date': latest.action_date.strftime('%d/%m/%Y'),
        'usage_count': str(len(usage_rows)),
        'days_since_last_used': str((date.today() - latest.action_date).days),
    }


def rack_visualization_data(db: Session, rack_no: str):
    active_locations = db.query(models.PlateSetMaster.location_id).filter(models.PlateSetMaster.status == 'ACTIVE').subquery()
    result = {key: 0 for key in ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'B1', 'B2', 'B3', 'B4', 'B5', 'B6']}
    rows = db.query(models.LocationMaster.section_code, func.count(models.LocationMaster.id)).filter(
        models.LocationMaster.rack_no == rack_no,
        models.LocationMaster.location_id.in_(active_locations)
    ).group_by(models.LocationMaster.section_code).all()
    for section_code, count in rows:
        result[section_code] = count
    return result

from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from .database import SessionLocal
from . import models

pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated='auto')

ROLE_PERMISSIONS = {
    'owner': {
        'view_dashboard', 'create_plate_set', 'create_replacement_plate', 'view_records',
        'use_usage_log', 'raise_scrap_request', 'approve_scrap_request', 'database_control',
        'view_notifications', 'view_master_tables'
    },
    'technical_team': {
        'view_dashboard', 'create_plate_set', 'create_replacement_plate', 'view_records',
        'use_usage_log', 'database_control', 'view_master_tables'
    },
    'designer': {
        'view_dashboard', 'create_plate_set', 'create_replacement_plate', 'view_records',
        'use_usage_log', 'raise_scrap_request', 'view_notifications', 'view_master_tables'
    },
    'plate_manager': {'view_dashboard', 'view_records', 'use_usage_log'},
}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_current_user(request: Request):
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    finally:
        db.close()


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={'Location': '/login'})
    return user


def require_permission(request: Request, permission: str):
    user = require_user(request)
    if permission not in ROLE_PERMISSIONS.get(user.role, set()):
        raise HTTPException(status_code=403, detail='You are not authorized to access this page.')
    return user

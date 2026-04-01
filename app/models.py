from sqlalchemy import Column, Integer, String, Text
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(String(10), default="YES")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(String(50), unique=True, nullable=False)
    rack_no = Column(String(10), nullable=False)
    shelf_code = Column(String(2), nullable=False)
    section_code = Column(String(4), nullable=False)
    position_no = Column(String(4), nullable=False)
    status = Column(String(20), default="FREE")

class PlateSet(Base):
    __tablename__ = "plate_sets"
    id = Column(Integer, primary_key=True, index=True)
    receiving_date = Column(String(20), nullable=False)
    job_id = Column(String(120), unique=True, nullable=False)
    job_name = Column(Text, nullable=False)
    party_name = Column(Text, nullable=False)
    plate_set_id = Column(String(120), unique=True, nullable=False)
    no_of_plates = Column(Integer, nullable=False)
    plate_size = Column(String(30), nullable=False)
    gripper_size_mm = Column(Integer, nullable=False)
    color_details = Column(Text, nullable=False)
    remarks = Column(Text, default="")
    plate_from_party = Column(String(10), nullable=False)
    vendor_name = Column(Text)
    vendor_plate_id = Column(String(120))
    location_id = Column(String(50), nullable=False)
    status = Column(String(20), default="ACTIVE")
    created_at = Column(String(30))

class ReplacementPlate(Base):
    __tablename__ = "replacement_plates"
    id = Column(Integer, primary_key=True, index=True)
    receiving_date = Column(String(20), nullable=False)
    job_id = Column(String(120), nullable=False)
    plate_set_id = Column(String(120), nullable=False)
    color = Column(String(30), nullable=False)
    replacement_plate_id = Column(String(180), unique=True, nullable=False)
    location_id = Column(String(50), nullable=False)
    plate_from_party = Column(String(10), nullable=False)
    vendor_name = Column(Text)
    vendor_plate_id = Column(String(120))
    status = Column(String(20), default="ACTIVE")
    created_at = Column(String(30))

class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    action_date = Column(String(20), nullable=False)
    action_time = Column(String(20), nullable=False)
    plate_set_id = Column(String(120), nullable=False)
    action = Column(String(10), nullable=False)
    remarks = Column(Text, default="")

class ScrapRequest(Base):
    __tablename__ = "scrap_requests"
    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(String(30), nullable=False)
    target_job_id = Column(String(120))
    target_plate_set_id = Column(String(120))
    target_replacement_plate_id = Column(String(180))
    requested_by_email = Column(String(255), nullable=False)
    reason = Column(Text, default="")
    status = Column(String(20), default="PENDING")
    created_at = Column(String(30))
    decided_at = Column(String(30))
    decision_note = Column(Text, default="")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(String(10), default="NO")
    created_at = Column(String(30))

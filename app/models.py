from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LocationMaster(Base):
    __tablename__ = 'location_master'
    id = Column(Integer, primary_key=True)
    location_id = Column(String, unique=True, nullable=False, index=True)
    rack_no = Column(String, nullable=False, index=True)
    shelf_group = Column(String, nullable=False)
    section_code = Column(String, nullable=False, index=True)
    slot_no = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlateSetMaster(Base):
    __tablename__ = 'plate_set_master'
    id = Column(Integer, primary_key=True)
    job_id = Column(String, unique=True, nullable=False, index=True)
    job_name = Column(String, nullable=False)
    party_name = Column(String, nullable=False)
    plate_set_id = Column(String, unique=True, nullable=False, index=True)
    number_of_plates = Column(Integer, nullable=False)
    plate_size = Column(String, nullable=False)
    gripper_size_mm = Column(Integer, nullable=False)
    color_details = Column(String, nullable=False)
    plate_from_party = Column(String, nullable=False)
    vendor_name = Column(String)
    remarks = Column(Text)
    receiving_date = Column(Date, nullable=False)
    location_id = Column(String, ForeignKey('location_master.location_id'), nullable=False, index=True)
    status = Column(String, default='ACTIVE', nullable=False)
    created_by_user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship('User')
    location = relationship('LocationMaster')
    usage_logs = relationship('UsageLog', back_populates='plate_set')


class ReplacementPlateMaster(Base):
    __tablename__ = 'replacement_plate_master'
    id = Column(Integer, primary_key=True)
    replacement_plate_receiving_date = Column(Date, nullable=False)
    job_id = Column(String, nullable=False, index=True)
    plate_set_id = Column(String, nullable=False, index=True)
    colour_of_replacement = Column(String, nullable=False)
    replacement_plate_id = Column(String, unique=True, nullable=False, index=True)
    location_id = Column(String, nullable=False)
    status = Column(String, default='ACTIVE', nullable=False)
    plate_from_party = Column(String, nullable=False)
    vendor_name = Column(String)
    created_by_user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship('User')


class UsageLog(Base):
    __tablename__ = 'usage_log'
    id = Column(Integer, primary_key=True)
    plate_set_id = Column(String, ForeignKey('plate_set_master.plate_set_id'), nullable=False, index=True)
    action_type = Column(String, nullable=False)
    action_date = Column(Date, nullable=False)
    action_time = Column(String, nullable=False)
    remarks = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plate_set = relationship('PlateSetMaster', back_populates='usage_logs')
    creator = relationship('User')


class ScrapRequest(Base):
    __tablename__ = 'scrap_requests'
    id = Column(Integer, primary_key=True)
    request_type = Column(String, nullable=False)
    target_plate_set_id = Column(String, index=True)
    target_replacement_plate_id = Column(String, index=True)
    target_job_id = Column(String, index=True)
    requested_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    request_reason = Column(Text)
    request_status = Column(String, default='Pending', nullable=False)
    approved_by_user_id = Column(Integer, ForeignKey('users.id'))
    decision_note = Column(Text)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    decided_at = Column(DateTime(timezone=True))

    requester = relationship('User', foreign_keys=[requested_by_user_id])
    approver = relationship('User', foreign_keys=[approved_by_user_id])


class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User')

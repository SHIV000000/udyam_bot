# udyam\database.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, JSON, Enum, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone, timedelta
import secrets
import uuid
import enum
import os

Base = declarative_base()

class FormStatus(enum.Enum):
    INITIATED = "Initiated"
    AWAITING_OTP = "Awaiting OTP"
    OTP_VERIFIED = "OTP Verified"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ERROR = "Error"

class RegistrationStage(enum.Enum):
    INITIATED = "Initiated"
    AADHAAR_SUBMITTED = "Aadhaar Submitted"
    OTP_REQUESTED = "OTP Requested"
    OTP_VERIFIED = "OTP Verified"
    
    # PAN related stages
    PAN_DATA_FILLING = "PAN Data Filling"
    PAN_SELECT_BOX_DONE = "PAN Select Box Done"
    PAN_NUMBER_ADDED = "PAN Number Added"
    PAN_NAME_ADDED = "PAN Name Added"
    PAN_DATE_ADDED = "PAN Date Added"
    PAN_CHECKBOX_CHECKED = "PAN Checkbox Checked"
    PAN_BUTTON_CLICKED = "PAN Button Clicked"
    PAN_SUBMITTED = "PAN Submitted"
    
    # Other stages
    GST_BTN_CLICKABLE = "GST Button Clickable"
    BASIC_DETAILS_FILLED = "Basic Details Filled"
    ADDRESS_FILLED = "Address Filled"
    BANK_DETAILS_FILLED = "Bank Details Filled"
    NIC_CODES_SELECTED = "NIC Codes Selected"
    EMPLOYEE_DETAILS_FILLED = "Employee Details Filled"
    INVESTMENT_DETAILS_FILLED = "Investment Details Filled"
    TURNOVER_DETAILS_FILLED = "Turnover Details Filled"
    ADDITIONAL_DETAILS_FILLED = "Additional Details Filled"
    DISTRICT_SELECTED = "District Selected"
    FORM_SUBMITTED = "Form Submitted"
    CAPTCHA_REQUIRED = "CAPTCHA Required"
    COMPLETED = "Completed"
    ERROR = "Error"


class Gender(enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"

class SocialCategory(enum.Enum):
    GENERAL = "General"
    SC = "SC"
    ST = "ST"
    OBC = "OBC"

class Vendor(Base):
    __tablename__ = 'vendors'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    api_key = Column(String(64), unique=True, nullable=False)
    api_key_expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    def generate_api_key(self):
        self.api_key = secrets.token_urlsafe(32)
        self.api_key_expires_at = datetime.now(timezone.utc) + timedelta(days=30)

class UdyamRegistration(Base):
    __tablename__ = 'udyam_registrations'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id = Column(String(36), ForeignKey('vendors.id'), nullable=False)
    vendor = relationship("Vendor", back_populates="registrations")
    
    aadhaar = Column(String(12), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    pan = Column(String(10), nullable=False, index=True)
    pan_name = Column(String(100), nullable=False)
    dob = Column(String(10), nullable=False)
    mobile = Column(String(10), nullable=False)
    email = Column(String(100), nullable=False)
    social_category = Column(Enum(SocialCategory), nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    specially_abled = Column(Boolean, nullable=False)
    enterprise_name = Column(String(100), nullable=False)
    unit_name = Column(String(100), nullable=False)
    
    # Plant address
    premises_number = Column(String(50), nullable=False)
    building_name = Column(String(100), nullable=False)
    village_town = Column(String(100), nullable=False)
    block = Column(String(100), nullable=False)
    road_street_lane = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    district = Column(String(50), nullable=False)
    pincode = Column(String(6), nullable=False)
    
    # Official address
    official_premises_number = Column(String(50), nullable=False)
    official_address = Column(String(200), nullable=False)
    official_town = Column(String(100), nullable=False)
    official_block = Column(String(100), nullable=False)
    official_lane = Column(String(100), nullable=False)
    official_city = Column(String(100), nullable=False)
    official_state = Column(String(50), nullable=False)
    official_district = Column(String(50), nullable=False)
    official_pincode = Column(String(6), nullable=False)
    
    date_of_incorporation = Column(String(10), nullable=False)
    date_of_commencement = Column(String(10), nullable=False)
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(20), nullable=False)
    ifsc_code = Column(String(11), nullable=False)
    
    # Additional fields
    major_activity = Column(String(20), nullable=False)
    second_form_section = Column(String(20), nullable=True)
    nic_codes = Column(JSON, nullable=False)
    male_employees = Column(Integer, nullable=False)
    female_employees = Column(Integer, nullable=False)
    other_employees = Column(Integer, nullable=False)
    investment_wdv = Column(Float, nullable=False)
    investment_exclusion_cost = Column(Float, nullable=False)
    total_turnover = Column(Float, nullable=False)
    export_turnover = Column(Float, nullable=False)
    
    have_gstin = Column(String(3), nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    form_status = Column(Enum(FormStatus), default=FormStatus.INITIATED)
    current_stage = Column(Enum(RegistrationStage), default=RegistrationStage.INITIATED)
    stage_details = Column(JSON, default={})
    error_message = Column(String(500))
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_aadhaar_pan', 'aadhaar', 'pan'),
        Index('idx_vendor_id', 'vendor_id'),
    )

Vendor.registrations = relationship("UdyamRegistration", order_by=UdyamRegistration.created_at, back_populates="vendor")

database_url = os.getenv('DATABASE_URL', 'sqlite:///udyam_registrations.db')
engine = create_engine(database_url)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def get_db_session():
    return Session()

if __name__ == "__main__":
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Database schema updated successfully.")





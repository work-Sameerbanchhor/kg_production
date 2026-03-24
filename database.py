"""
Database models and setup for Kalyan College Management System.
Uses SQLAlchemy with SQLite.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./college_management.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Student(Base):
    """Student model with all 34 fields from the CSV dataset."""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Core admission fields
    admission_no = Column(String(50), unique=True, index=True, nullable=False)
    student_name = Column(String(200), index=True, nullable=False)
    mobile_no = Column(String(20))
    course = Column(String(200), nullable=False)
    subject = Column(String(200))
    admission_date = Column(String(20))
    
    # Family information
    father_name = Column(String(200))
    mother_name = Column(String(200))
    father_occupation = Column(String(100))
    
    # Personal details
    dob = Column(String(20))
    gender = Column(String(20))
    category = Column(String(20))
    subcast = Column(String(100))
    
    # Address
    permanent_address = Column(Text)
    present_address = Column(Text)
    district = Column(String(100))
    state = Column(String(50))
    domicile = Column(String(10))
    
    # Contact & ID
    email = Column(String(200))
    aadhaar_no = Column(String(20))
    
    # Additional subjects
    subject_4 = Column(String(200))
    subject_5 = Column(String(200))
    subject_6 = Column(String(200))
    
    # Last examination details
    last_exam = Column(String(100))
    last_exam_year = Column(String(10))
    last_subject = Column(String(100))
    last_roll_no = Column(String(50))
    last_enroll_no = Column(String(50))
    board = Column(String(200))
    total_marks = Column(String(20))
    obtain_marks = Column(String(20))
    division = Column(String(20))
    percentage = Column(String(20))
    remark = Column(Text)
    
    # --- New Fields from New Forms ---
    # Form/Session Fields
    admission_form_no = Column(String(50))
    session = Column(String(50))
    
    # Office Use Fields
    university_enrolment_no = Column(String(100))
    receipt_no_date = Column(String(100))
    cast_class = Column(String(100))
    
    # NEP 2020 Course/Subject Fields
    faculty = Column(String(100))
    annual_semester = Column(String(100))
    course_type = Column(String(50))
    class_name = Column(String(100))
    dsc_1 = Column(String(100))
    dsc_2 = Column(String(100))
    dsc_3 = Column(String(100))
    vac_sec = Column(String(100))
    ge_dse = Column(String(100))
    aec = Column(String(100))
    research_project = Column(String(100))
    
    # Personal Info Fields
    abc_id = Column(String(100))
    blood_group = Column(String(20))
    father_mobile_no = Column(String(20))
    religion = Column(String(50))
    mother_tongue = Column(String(50))
    
    # Bank Fields
    bank_name_address = Column(String(200))
    bank_ac_no = Column(String(50))
    ifsc_code = Column(String(20))

    # Page 2 Fields
    guardian_annual_income = Column(String(50))
    extra_curricular = Column(String(200))  # Comma separated
    medium_of_exam = Column(String(50))
    is_convicted = Column(String(10))
    academic_history_json = Column(Text)  # JSON representation of academic table
    # ---------------------------------
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to fee records
    fee_records = relationship("FeeRecord", back_populates="student", cascade="all, delete-orphan")


class FeeRecord(Base):
    """Fee payment record for a student."""
    __tablename__ = "fee_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    receipt_no = Column(String(50), unique=True, index=True)
    date = Column(String(20))
    academic_year = Column(String(20))
    fee_period = Column(String(100))
    installment = Column(String(20))  # "FIRST" or "SECOND"
    
    # Fee breakdown heads
    tuition = Column(Float, default=0)
    various_heads = Column(Float, default=0)
    practical = Column(Float, default=0)
    admission_fee = Column(Float, default=0)
    amalgamated_fund = Column(Float, default=0)
    library_dev = Column(Float, default=0)
    home_examination = Column(Float, default=0)
    establishment_fund = Column(Float, default=0)
    student_dev = Column(Float, default=0)
    college_dev = Column(Float, default=0)
    cycle_stand = Column(Float, default=0)
    caution_money = Column(Float, default=0)
    seminar_ws = Column(Float, default=0)
    computer_maint = Column(Float, default=0)
    physical_edu = Column(Float, default=0)
    non_aided_staff = Column(Float, default=0)
    gym_dev = Column(Float, default=0)
    
    # Payment info
    total_amount = Column(Float, default=0)
    payment_mode = Column(String(50))  # CASH, ONLINE, CHEQUE
    payment_status = Column(String(20), default="PAID")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("Student", back_populates="fee_records")


def init_db():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

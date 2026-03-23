"""
Kalyan College Management System - FastAPI Backend
Admission management + Fee management
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from sqlalchemy import or_
from database import init_db, get_db, Student, FeeRecord
from fee_structure import COURSES, get_fee_structure, get_all_fee_structures, FEE_INSTALLMENTS
from datetime import datetime
import csv
import io
import random
import os

app = FastAPI(title="Kalyan College Management System", version="1.0.0")

# Initialize database on startup and auto-import CSV
@app.on_event("startup")
def startup():
    init_db()
    # Auto-import CSV if database is empty
    auto_import_csv()


def auto_import_csv():
    """Auto-import kalyan_2024_admission_data.csv from current directory on first run."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        count = db.query(Student).count()
        if count > 0:
            print(f"✅ Database already has {count} students. Skipping CSV import.")
            return

        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kalyan_2024_admission_data.csv")
        if not os.path.exists(csv_path):
            print(f"⚠️ CSV file not found at: {csv_path}")
            return

        print(f"📁 Auto-importing CSV from: {csv_path}")
        imported = 0
        skipped = 0

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    admission_no = row.get("Admission No", "").strip()
                    if not admission_no:
                        skipped += 1
                        continue

                    student = Student()
                    for csv_col, db_col in CSV_HEADER_MAP.items():
                        val = row.get(csv_col, "").strip()
                        setattr(student, db_col, val)

                    db.add(student)
                    imported += 1
                except Exception as e:
                    skipped += 1

        db.commit()
        print(f"✅ CSV import complete: {imported} students imported, {skipped} skipped.")
    except Exception as e:
        print(f"❌ CSV auto-import error: {e}")
        db.rollback()
    finally:
        db.close()

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ═══════════════════════════════════════════════════════════
#  ROOT - Serve HTML
# ═══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════
#  COURSES API
# ═══════════════════════════════════════════════════════════

@app.get("/api/courses")
def list_courses():
    return {"courses": COURSES}


# ═══════════════════════════════════════════════════════════
#  STUDENT CRUD APIs
# ═══════════════════════════════════════════════════════════

STUDENT_FIELDS = [
    "admission_no", "student_name", "mobile_no", "course", "subject",
    "admission_date", "father_name", "mother_name", "father_occupation",
    "dob", "gender", "category", "subcast", "permanent_address",
    "present_address", "district", "state", "domicile", "email",
    "aadhaar_no", "subject_4", "subject_5", "subject_6", "last_exam",
    "last_exam_year", "last_subject", "last_roll_no", "last_enroll_no",
    "board", "total_marks", "obtain_marks", "division", "percentage", "remark",
]


def student_to_dict(s: Student) -> dict:
    return {field: getattr(s, field, "") or "" for field in STUDENT_FIELDS} | {
        "id": s.id,
        "created_at": str(s.created_at) if s.created_at else "",
        "updated_at": str(s.updated_at) if s.updated_at else "",
    }


@app.post("/api/students")
async def create_student(data: dict, db: Session = Depends(get_db)):
    # Check duplicate admission_no
    existing = db.query(Student).filter(Student.admission_no == data.get("admission_no")).first()
    if existing:
        raise HTTPException(status_code=400, detail="Admission number already exists")

    student = Student()
    for field in STUDENT_FIELDS:
        setattr(student, field, data.get(field, ""))

    db.add(student)
    db.commit()
    db.refresh(student)
    return {"message": "Student added successfully", "student": student_to_dict(student)}


@app.get("/api/students")
def list_students(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.query(Student).count()
    students = (
        db.query(Student)
        .order_by(Student.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "students": [student_to_dict(s) for s in students],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/students/search")
def search_students(
    q: str = Query("", min_length=0),
    course: str = Query(""),
    category: str = Query(""),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Student)

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Student.student_name.ilike(search_term),
                Student.admission_no.ilike(search_term),
                Student.mobile_no.ilike(search_term),
            )
        )

    if course:
        query = query.filter(Student.course == course)

    if category:
        query = query.filter(Student.category == category)

    total = query.count()
    students = (
        query.order_by(Student.student_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "students": [student_to_dict(s) for s in students],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student": student_to_dict(student)}


@app.put("/api/students/{student_id}")
async def update_student(student_id: int, data: dict, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    for field in STUDENT_FIELDS:
        if field in data:
            setattr(student, field, data[field])

    student.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(student)
    return {"message": "Student updated successfully", "student": student_to_dict(student)}


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(student)
    db.commit()
    return {"message": "Student deleted successfully"}


# ═══════════════════════════════════════════════════════════
#  CSV IMPORT
# ═══════════════════════════════════════════════════════════

CSV_HEADER_MAP = {
    "Admission No": "admission_no",
    "Student Name": "student_name",
    "Mobile No": "mobile_no",
    "Course": "course",
    "Subject": "subject",
    "Admission Date": "admission_date",
    "Father Name": "father_name",
    "Mother Name": "mother_name",
    "Father Occupation": "father_occupation",
    "DOB": "dob",
    "Gender": "gender",
    "Category": "category",
    "Subcast": "subcast",
    "Permanent Address": "permanent_address",
    "Present Address": "present_address",
    "District": "district",
    "State": "state",
    "Domicile": "domicile",
    "Email": "email",
    "Aadhaar No": "aadhaar_no",
    "Subject 4": "subject_4",
    "Subject 5": "subject_5",
    "Subject 6": "subject_6",
    "Last Exam": "last_exam",
    "Last Exam Year": "last_exam_year",
    "Last Subject": "last_subject",
    "Last Roll No": "last_roll_no",
    "Last Enroll No": "last_enroll_no",
    "Board": "board",
    "Total Marks": "total_marks",
    "Obtain Marks": "obtain_marks",
    "Division": "division",
    "Percentage": "percentage",
    "Remark": "remark",
}


@app.post("/api/students/import-csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    decoded = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(decoded))

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        try:
            admission_no = row.get("Admission No", "").strip()
            if not admission_no:
                skipped += 1
                continue

            existing = db.query(Student).filter(Student.admission_no == admission_no).first()
            if existing:
                skipped += 1
                continue

            student = Student()
            for csv_col, db_col in CSV_HEADER_MAP.items():
                val = row.get(csv_col, "").strip()
                setattr(student, db_col, val)

            db.add(student)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")
            skipped += 1

    db.commit()
    return {
        "message": f"Import complete: {imported} imported, {skipped} skipped",
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],
    }


# ═══════════════════════════════════════════════════════════
#  FEE STRUCTURE APIs
# ═══════════════════════════════════════════════════════════

@app.get("/api/fee-structure")
def all_fee_structures():
    return {"structures": get_all_fee_structures()}


@app.get("/api/fee-structure/{course}")
def fee_structure_for_course(course: str):
    structure = get_fee_structure(course)
    if not structure:
        raise HTTPException(status_code=404, detail="Fee structure not found for this course")
    return structure


# ═══════════════════════════════════════════════════════════
#  FEE PAYMENT APIs
# ═══════════════════════════════════════════════════════════

@app.post("/api/fees/pay")
async def record_fee_payment(data: dict, db: Session = Depends(get_db)):
    student_id = data.get("student_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Generate receipt number
    receipt_no = f"{random.randint(10000, 99999)}"

    fee_record = FeeRecord(
        student_id=student_id,
        receipt_no=receipt_no,
        date=data.get("date", datetime.now().strftime("%d-%m-%Y")),
        academic_year=data.get("academic_year", "2024-25"),
        fee_period=data.get("fee_period", ""),
        installment=data.get("installment", "FIRST"),
        tuition=float(data.get("tuition", 0)),
        various_heads=float(data.get("various_heads", 0)),
        practical=float(data.get("practical", 0)),
        admission_fee=float(data.get("admission_fee", 0)),
        amalgamated_fund=float(data.get("amalgamated_fund", 0)),
        library_dev=float(data.get("library_dev", 0)),
        home_examination=float(data.get("home_examination", 0)),
        establishment_fund=float(data.get("establishment_fund", 0)),
        student_dev=float(data.get("student_dev", 0)),
        college_dev=float(data.get("college_dev", 0)),
        cycle_stand=float(data.get("cycle_stand", 0)),
        caution_money=float(data.get("caution_money", 0)),
        seminar_ws=float(data.get("seminar_ws", 0)),
        computer_maint=float(data.get("computer_maint", 0)),
        physical_edu=float(data.get("physical_edu", 0)),
        non_aided_staff=float(data.get("non_aided_staff", 0)),
        gym_dev=float(data.get("gym_dev", 0)),
        total_amount=float(data.get("total_amount", 0)),
        payment_mode=data.get("payment_mode", "CASH"),
        payment_status="PAID",
    )

    db.add(fee_record)
    db.commit()
    db.refresh(fee_record)

    return {
        "message": "Fee payment recorded successfully",
        "receipt_no": receipt_no,
        "fee_record_id": fee_record.id,
    }


@app.get("/api/fees/student/{student_id}")
def get_student_fees(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = db.query(FeeRecord).filter(FeeRecord.student_id == student_id).order_by(FeeRecord.id.desc()).all()

    total_paid = sum(r.total_amount for r in records)
    fee_structure = get_fee_structure(student.course)
    year_total = fee_structure["installments"]["year_total"] if fee_structure else 0

    return {
        "student_name": student.student_name,
        "admission_no": student.admission_no,
        "course": student.course,
        "total_fee": year_total,
        "total_paid": total_paid,
        "balance": year_total - total_paid,
        "records": [
            {
                "id": r.id,
                "receipt_no": r.receipt_no,
                "date": r.date,
                "academic_year": r.academic_year,
                "installment": r.installment,
                "total_amount": r.total_amount,
                "payment_mode": r.payment_mode,
                "payment_status": r.payment_status,
            }
            for r in records
        ],
    }


@app.get("/api/fees/receipt/{fee_record_id}/pdf")
def generate_fee_receipt_pdf(fee_record_id: int, db: Session = Depends(get_db)):
    fee_record = db.query(FeeRecord).filter(FeeRecord.id == fee_record_id).first()
    if not fee_record:
        raise HTTPException(status_code=404, detail="Fee record not found")

    student = db.query(Student).filter(Student.id == fee_record.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    os.makedirs("export_pdf", exist_ok=True)
    pdf_path = f"export_pdf/Receipt_{fee_record.receipt_no}.pdf"

    c = canvas.Canvas(pdf_path, pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFont("Courier-Bold", 14)
    c.drawString(50, height - 50, "                KALYAN P.G. COLLEGE - BHILAI")
    c.setFont("Courier", 12)
    c.drawString(50, height - 70, "         College of Arts, Commerce, Science & Education")
    c.drawString(50, height - 90, "               Phone : (PNT)-2223665 (BSP) - 9406")

    c.setFont("Courier-Bold", 12)
    c.drawString(200, height - 130, "FEE RECEIPT")

    c.setFont("Courier", 10)
    c.drawString(50, height - 170, f"Receipt No.     {fee_record.receipt_no:<28} Date :   {fee_record.date}")

    c.drawString(50, height - 210, f"Year :          {fee_record.academic_year:<19} Class   :         {student.course}")
    c.drawString(50, height - 230, f"Name :          {student.student_name:<19} ADMN.NO.:         {student.admission_no}")

    if fee_record.fee_period:
        fee_period_str = fee_record.fee_period
        if " TO " in fee_period_str:
            parts = fee_period_str.split(" TO ")
            if len(parts) == 2:
                c.drawString(50, height - 250, f"Fee paid for the period from       {parts[0]:<12} TO    {parts[1]}")
            else:
                c.drawString(50, height - 250, f"Fee paid for the period from       {fee_period_str}")
        else:
            c.drawString(50, height - 250, f"Fee paid for the period from       {fee_period_str}")
    else:
        c.drawString(50, height - 250, f"Fee paid for the period from       -")

    y = height - 290

    def draw_row(y_pos, col1_name, col1_val, col2_name, col2_val, col3_name, col3_val, col4_name, col4_val):
        c.drawString(50, y_pos, f"{col1_name:<16} {col1_val:>6.2f}  {col2_name:<15} {col2_val:>6.2f}  {col3_name:<15} {col3_val:>6.2f}  {col4_name:<15} {col4_val:>6.2f}")

    draw_row(y, "Tuition", fee_record.tuition, "Enrolment", 0.00, "Staff Welfare", 0.00, "Physical Edu.", fee_record.physical_edu)
    y -= 20
    draw_row(y, "Stationery", 0.00, "GYM", fee_record.gym_dev, "Extra-2", 0.00, "Establish", fee_record.establishment_fund)
    y -= 20
    draw_row(y, "Seminar/WS", fee_record.seminar_ws, "Cycle", fee_record.cycle_stand, "Decit", 0.00, "Development", fee_record.college_dev)
    y -= 20
    draw_row(y, "Application", 0.00, "Visual Lab.", 0.00, "Amalgamated", fee_record.amalgamated_fund, "Cultural", 0.00)
    y -= 20
    draw_row(y, "Admission", fee_record.admission_fee, "Immigration", 0.00, "Icard", 0.00, "Comp/EEM/EL.", fee_record.computer_maint)
    y -= 20
    draw_row(y, "Student Dev.", fee_record.student_dev, "Caution Money", fee_record.caution_money, "Extra", fee_record.various_heads, "Stu.Coun.", 0.00)
    y -= 20
    draw_row(y, "NGS Fund", 0.00, "Laboratory", fee_record.practical, "Model Lesson", 0.00, "Others -6", fee_record.non_aided_staff)
    y -= 20
    draw_row(y, "Communic.", 0.00, "ET-Lab.", 0.00, "Library Dev.", fee_record.library_dev, "", 0.00)
    y -= 20
    draw_row(y, "Pers.Dev", 0.00, "Others -4", fee_record.home_examination, "Others -5", 0.00, "", 0.00)

    y -= 40
    c.drawString(50, y, f"{(fee_record.payment_mode or 'CASH') + '-NO':<23}           DATE                  Total :           {fee_record.total_amount:>10.2f}")

    y -= 40
    c.drawString(50, y, f"Rs. {fee_record.total_amount} only")
    c.drawString(450, y - 20, "CASHIER")

    c.save()

    return FileResponse(path=pdf_path, filename=f"Receipt_{fee_record.receipt_no}.pdf", media_type='application/pdf')


# ═══════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════

@app.get("/api/dashboard")
def dashboard_stats(db: Session = Depends(get_db)):
    total_students = db.query(Student).count()
    total_fee_records = db.query(FeeRecord).count()
    total_collected = db.query(FeeRecord).with_entities(
        db.query(FeeRecord).with_entities(FeeRecord.total_amount).subquery()
    ).count()

    # Count by course
    from sqlalchemy import func
    course_counts = (
        db.query(Student.course, func.count(Student.id))
        .group_by(Student.course)
        .all()
    )

    # Count by gender
    gender_counts = (
        db.query(Student.gender, func.count(Student.id))
        .group_by(Student.gender)
        .all()
    )

    # Count by category
    category_counts = (
        db.query(Student.category, func.count(Student.id))
        .group_by(Student.category)
        .all()
    )

    # Total fees collected
    from sqlalchemy import func as sqlfunc
    fees_sum = db.query(sqlfunc.sum(FeeRecord.total_amount)).scalar() or 0

    return {
        "total_students": total_students,
        "total_fee_records": total_fee_records,
        "total_fees_collected": fees_sum,
        "total_courses": len(COURSES),
        "course_distribution": {c: count for c, count in course_counts},
        "gender_distribution": {g or "Unknown": count for g, count in gender_counts},
        "category_distribution": {c or "Unknown": count for c, count in category_counts},
    }

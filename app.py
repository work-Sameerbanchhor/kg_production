"""
Kalyan College Management System - FastAPI Backend
Admission management + Fee management
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import socket
import netifaces

load_dotenv()

# --- Optional Dependencies ---
try:
    from google import genai
    from google.genai import types
    from pydantic import BaseModel, Field
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from zeroconf import ServiceInfo
    # NEW: Import the Async version of Zeroconf
    from zeroconf.asyncio import AsyncZeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
# -----------------------------

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
import json

# ═══════════════════════════════════════════════════════════
#  SERVER CONFIGURATION & LIFECYCLE
# ═══════════════════════════════════════════════════════════

PORT = 52002  # Global port variable
aio_zeroconf_instance = None

def get_all_network_ips():
    """
    Get all IPv4 addresses grouped by type using netifaces.
    Returns a dict with keys: 'wifi', 'ethernet', 'self_assign'
    Each value is a list of IPs found for that category.
    Falls back to socket-based detection if netifaces is unavailable.
    """
    wifi_ips = []
    ethernet_ips = []
    self_assign_ips = []

    try:
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            ipv4_list = addrs.get(netifaces.AF_INET, [])
            for entry in ipv4_list:
                ip = entry.get("addr", "")
                if not ip or ip.startswith("127."):
                    continue
                if ip.startswith("169.254."):
                    # APIPA / self-assigned (no DHCP / link-local)
                    self_assign_ips.append(ip)
                elif ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    wifi_ips.append(ip)
                else:
                    ethernet_ips.append(ip)
    except Exception:
        # Fallback: socket-based
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ip.startswith("127.") or ":" in ip:
                    continue
                if ip.startswith("169.254."):
                    self_assign_ips.append(ip)
                elif ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    wifi_ips.append(ip)
                else:
                    ethernet_ips.append(ip)
        except Exception:
            pass

    return {
        "wifi": list(set(wifi_ips)),
        "ethernet": list(set(ethernet_ips)),
        "self_assign": list(set(self_assign_ips)),
    }


def get_local_ip():
    """Primary LAN IP (wifi/ethernet) for mDNS, falls back to 127.0.0.1"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_wifi_ip():
    return get_all_network_ips()["wifi"][0] if get_all_network_ips()["wifi"] else None


def get_ethernet_ip():
    ips = get_all_network_ips()
    # Return self-assigned (APIPA) if present, else real ethernet
    return (ips["self_assign"] or ips["ethernet"] or [None])[0]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global aio_zeroconf_instance
    
    # Initialize database on startup
    init_db()
    
    # Start mDNS Broadcasting (Auto-Discovery) using AsyncZeroconf
    if HAS_ZEROCONF:
        ip_address = get_local_ip()
        if ip_address != "127.0.0.1":
            try:
                info = ServiceInfo(
                    "_http._tcp.local.",
                    "KalyanScanner._http._tcp.local.",
                    parsed_addresses=[ip_address],
                    port=PORT,
                    server="kalyanscanner.local."
                )
                aio_zeroconf_instance = AsyncZeroconf()
                await aio_zeroconf_instance.async_register_service(info)
                print(f"📡 Broadcasting KalyanScanner on {ip_address}:{PORT} via mDNS")
            except Exception as e:
                print(f"⚠️ Failed to start mDNS broadcasting: {repr(e)}")
    else:
        print("⚠️ 'zeroconf' library not installed. Auto-discovery will not work.")

    yield
    
    # Shutdown mDNS on exit safely
    if aio_zeroconf_instance:
        try:
            await aio_zeroconf_instance.async_unregister_all_services()
            await aio_zeroconf_instance.async_close()
        except:
            pass

app = FastAPI(
    title="Kalyan College Management System", 
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("student_passport_photos", exist_ok=True)
app.mount("/student_passport_photos", StaticFiles(directory="student_passport_photos"), name="student_passport_photos")

os.makedirs("Uploaded_pdfs", exist_ok=True)
app.mount("/Uploaded_pdfs", StaticFiles(directory="Uploaded_pdfs"), name="Uploaded_pdfs")

# ═══════════════════════════════════════════════════════════
#  ROOT - Serve HTML
# ═══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    with open("static/settings.html", "r") as f:
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
    
    # New Fields
    "admission_form_no", "session", "university_enrolment_no", "receipt_no_date",
    "cast_class", "faculty", "annual_semester", "course_type", "class_name",
    "dsc_1", "dsc_2", "dsc_3", "vac_sec", "ge_dse", "aec", "research_project",
    "abc_id", "blood_group", "father_mobile_no", "religion", "mother_tongue",
    "bank_name_address", "bank_ac_no", "ifsc_code", "guardian_annual_income",
    "extra_curricular", "medium_of_exam", "is_convicted", "academic_history_json",
    "photo_path"
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
#  FORM SCANNER API
# ═══════════════════════════════════════════════════════════

if HAS_GENAI:
    class StudentFormExtract(BaseModel):
        admission_no: str = Field(description="Admission No.")
        university_enrolment_no: str = Field(description="University Enrolment No.")
        admission_date: str = Field(description="Date of Admission")
        receipt_no_date: str = Field(description="Receipt No. & Date")
        cast_class: str = Field(description="Cast & Class")
        percentage: str = Field(description="% of the Previous Exam")
        student_name: str = Field(description="Name")
        abc_id: str = Field(description="ABC ID")
        mobile_no: str = Field(description="Mobile Number")
        email: str = Field(description="E-mail ID")
        dob: str = Field(description="Date of Birth in YYYY-MM-DD")
        blood_group: str = Field(description="Blood Group")
        faculty: str = Field(description="1. Faculty of")
        annual_semester: str = Field(description="2. Annual / Semester")
        course_type: str = Field(description="Semester (First/Second/...)")
        course_level: str = Field(description="3. Courses (UG / PG / Diploma / Ph.D)")
        course: str = Field(description="Specific Course")
        class_name: str = Field(description="CLASS (कक्षा)")
        dsc_1: str = Field(description="DSC - 1")
        dsc_2: str = Field(description="DSC - 2")
        dsc_3: str = Field(description="DSC - 3")
        vac_sec: str = Field(description="VAC / SEC")
        ge_dse: str = Field(description="GE / DSE")
        aec: str = Field(description="AEC")
        research_project: list[str] = Field(default_factory=list, description="List of checked items in: Research / Internship / Project / Ph.D")
        father_name: str = Field(description="4. Fathers Name")
        father_mobile_no: str = Field(description="Mobile No. (Fathers)")
        mother_name: str = Field(description="5. Mothers Name")
        mother_tongue: str = Field(description="Mother Tongue")
        religion: str = Field(description="6. Religion")
        bank_ac_no: str = Field(description="Bank A/c No.")
        aadhaar_no: str = Field(description="Aadhar No.")
        ifsc_code: str = Field(description="IFSC Code / Bank Name")
        present_address: str = Field(description="7. Local Address")
        permanent_address: str = Field(description="Permanent Address")
        guardian_annual_income: str = Field(description="8. Annual Income of Guardian")
        domicile: str = Field(description="9. C.G. Domicile (YES/NO)")
        category: str = Field(description="10. Category (GEN/OBC/SC/ST...)")
        extra_curricular: list[str] = Field(default_factory=list, description="11. List of checked items in: Extra Curricular Activities (NCC / NSS / SPORTS / CULTURAL...)")
        medium_of_exam: str = Field(description="13. Medium of Exam")
        is_convicted: str = Field(description="14. Convicted by court of law")
        ex_name_1: str = Field(description="Exam 1 name")
        ex_roll_1: str = Field(description="Exam 1 roll")
        ex_year_1: str = Field(description="Exam 1 year")
        ex_col_1: str = Field(description="Exam 1 college")
        ex_res_1: str = Field(description="Exam 1 result")
        ex_per_1: str = Field(description="Exam 1 percentage")
        ex_name_2: str = Field(description="Exam 2 name")
        ex_roll_2: str = Field(description="Exam 2 roll")
        ex_year_2: str = Field(description="Exam 2 year")
        ex_col_2: str = Field(description="Exam 2 college")
        ex_res_2: str = Field(description="Exam 2 result")
        ex_per_2: str = Field(description="Exam 2 percentage")
        ex_name_3: str = Field(description="Exam 3 name")
        ex_roll_3: str = Field(description="Exam 3 roll")
        ex_year_3: str = Field(description="Exam 3 year")
        ex_col_3: str = Field(description="Exam 3 college")
        ex_res_3: str = Field(description="Exam 3 result")
        ex_per_3: str = Field(description="Exam 3 percentage")
        ex_name_4: str = Field(description="Exam 4 name")
        ex_roll_4: str = Field(description="Exam 4 roll")
        ex_year_4: str = Field(description="Exam 4 year")
        ex_col_4: str = Field(description="Exam 4 college")
        ex_res_4: str = Field(description="Exam 4 result")
        ex_per_4: str = Field(description="Exam 4 percentage")
        ex_name_5: str = Field(description="Exam 5 name")
        ex_roll_5: str = Field(description="Exam 5 roll")
        ex_year_5: str = Field(description="Exam 5 year")
        ex_col_5: str = Field(description="Exam 5 college")
        ex_res_5: str = Field(description="Exam 5 result")
        ex_per_5: str = Field(description="Exam 5 percentage")
        sign_principal: bool = Field(default=False, description="True if Signature of Principal is present")
        sign_prof: bool = Field(default=False, description="True if Signature of Professor In-charge is present")
        sign_parent: bool = Field(default=False, description="True if Signature of Parent is present")
        sign_student: bool = Field(default=False, description="True if Signature of Student is present")
        photo_box: list[int] = Field(
            default_factory=list,
            description="IMPORTANT: Bounding box [ymin, xmin, ymax, xmax] of the student's passport photo on the first page, using normalized coordinates (0 to 1000). Return empty list [] if no photo attached."
        )

@app.post("/api/students/scan-form")
async def scan_student_form(files: list[UploadFile] = File(...)):
    import json
    if not HAS_GENAI:
        raise HTTPException(status_code=500, detail="Google GenAI SDK not installed or configured.")
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY missing in environment.")
        
    try:
        client = genai.Client()
        contents_list = []
        
        for f in files:
            content = await f.read()
            mime_type = f.content_type
            if mime_type not in ["application/pdf", "image/jpeg", "image/png", "image/webp"]:
                if "image" in mime_type:
                    mime_type = "image/jpeg"
                elif mime_type == "application/octet-stream" and f.filename:
                    if f.filename.lower().endswith(".pdf"):
                        mime_type = "application/pdf"
                    elif f.filename.lower().endswith((".jpg", ".jpeg")):
                        mime_type = "image/jpeg"
                    elif f.filename.lower().endswith(".png"):
                        mime_type = "image/png"
            
            contents_list.append(
                types.Part.from_bytes(
                    data=content,
                    mime_type=mime_type,
                )
            )
        
        prompt = (
            "Extract the student information from this admission form. "
            "Correct any spelling or grammatical mistakes in the text fields. "
            "Do not provide the exact text if it contains errors; instead, infer and provide the correctly spelled information. "
            "Return an empty string for missing fields. "
            "The form has multiple pages. "
            "IMPORTANT: Also locate the student's passport photo on the first page, and return its bounding box coordinates [ymin, xmin, ymax, xmax] normalized to 0-1000 scale in the `photo_box` field. "
            "If there is no physical photo glued/printed on the form, leave `photo_box` as an empty list []."
        )
        contents_list.append(prompt)
        
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=contents_list,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=StudentFormExtract.model_json_schema(),
                thinking_config=types.ThinkingConfig(
                    thinking_level="low"
                )
            )
        )
        
        data = json.loads(response.text)
        
        # Process photo cropping
        photo_box = data.get("photo_box", [])
        if photo_box and len(photo_box) == 4 and len(files) > 0:
            try:
                import io
                from PIL import Image
                
                f = files[0]
                await f.seek(0)
                content = await f.read()
                
                img = None
                if f.content_type == "application/pdf" or (f.filename and f.filename.lower().endswith(".pdf")):
                    import fitz # PyMuPDF
                    doc = fitz.open(stream=content, filetype="pdf")
                    if len(doc) > 0:
                        page = doc[0]
                        pix = page.get_pixmap(dpi=150)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    doc.close()
                else:
                    img = Image.open(io.BytesIO(content))
                    
                if img:
                    width, height = img.size
                    ymin, xmin, ymax, xmax = photo_box
                    
                    crop_box = (
                        int(xmin * width / 1000),
                        int(ymin * height / 1000),
                        int(xmax * width / 1000),
                        int(ymax * height / 1000)
                    )
                    
                    if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                        cropped = img.crop(crop_box)
                        
                        os.makedirs("student_passport_photos", exist_ok=True)
                        filename = f"photo_{int(datetime.utcnow().timestamp())}_{random.randint(100, 999)}.jpg"
                        filepath = f"student_passport_photos/{filename}"
                        cropped.convert("RGB").save(filepath, format="JPEG", quality=85)
                        
                        data["photo_url"] = f"/{filepath}"
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error extracting photo: {e}")
                
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API Error: {str(e)}")


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
#  PDF UPLOAD API
# ═══════════════════════════════════════════════════════════

@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    upload_dir = "Uploaded_pdfs"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        return {
            "message": "PDF uploaded successfully", 
            "filename": file.filename, 
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while saving the file: {str(e)}")

@app.get("/api/recent-pdfs")
def get_recent_pdfs():
    upload_dir = "Uploaded_pdfs"
    if not os.path.exists(upload_dir):
        return {"pdfs": []}
    files = []
    for f in os.listdir(upload_dir):
        if f.lower().endswith(".pdf"):
            path = os.path.join(upload_dir, f)
            files.append({
                "filename": f,
                "url": f"/Uploaded_pdfs/{f}",
                "time": os.path.getmtime(path)
            })
    files.sort(key=lambda x: x["time"], reverse=True)
    return {"pdfs": files[:5]}

# ═══════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════

@app.get("/api/dashboard")
def dashboard_stats(db: Session = Depends(get_db)):
    total_students = db.query(Student).count()
    total_fee_records = db.query(FeeRecord).count()
    
    from sqlalchemy import func
    course_counts = (
        db.query(Student.course, func.count(Student.id))
        .group_by(Student.course)
        .all()
    )

    gender_counts = (
        db.query(Student.gender, func.count(Student.id))
        .group_by(Student.gender)
        .all()
    )

    category_counts = (
        db.query(Student.category, func.count(Student.id))
        .group_by(Student.category)
        .all()
    )

    fees_sum = db.query(func.sum(FeeRecord.total_amount)).scalar() or 0

    return {
        "total_students": total_students,
        "total_fee_records": total_fee_records,
        "total_fees_collected": fees_sum,
        "total_courses": len(COURSES),
        "course_distribution": {c: count for c, count in course_counts},
        "gender_distribution": {g or "Unknown": count for g, count in gender_counts},
        "category_distribution": {c or "Unknown": count for c, count in category_counts},
    }


# ═══════════════════════════════════════════════════════════
#  SETTINGS APIs
# ═══════════════════════════════════════════════════════════

@app.get("/api/settings/upi")
def get_upi_settings():
    path = "settings/upi.json"
    default = {"upi_options": [], "active_upi": None}
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        try:
            data = json.load(f)
            if not isinstance(data, dict): return default
            if "upi_options" not in data: data["upi_options"] = []
            if "active_upi" not in data: data["active_upi"] = None
            return data
        except:
            return default

@app.post("/api/settings/upi")
async def save_upi_settings(data: dict):
    os.makedirs("settings", exist_ok=True)
    with open("settings/upi.json", "w") as f:
        json.dump(data, f, indent=4)
    return {"message": "UPI settings saved successfully"}


@app.get("/api/settings/themes")
def get_theme_settings():
    path = "settings/themes.json"
    default = {
        "active_mode": "light",
        "active_theme": "forest",
        "themes": [
            {"id": "forest", "name": "Forest", "primary": "#4a7c4a", "accent": "#b8944a"},
            {"id": "ocean", "name": "Ocean", "primary": "#2980b9", "accent": "#f39c12"},
            {"id": "midnight", "name": "Midnight", "primary": "#34495e", "accent": "#e74c3c"},
            {"id": "royal", "name": "Royal", "primary": "#8e44ad", "accent": "#f1c40f"},
            {"id": "crimson", "name": "Crimson", "primary": "#c0392b", "accent": "#2c3e50"},
            {"id": "sunset", "name": "Sunset", "primary": "#e67e22", "accent": "#2980b9"},
            {"id": "sakura", "name": "Sakura", "primary": "#d63384", "accent": "#4a7c4a"},
            {"id": "gray", "name": "Silver Gray", "primary": "#9e9e9e", "accent": "#333333"}
        ]
    }
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        try:
            data = json.load(f)
            if not isinstance(data, dict): return default
            if "themes" not in data: data["themes"] = default["themes"]
            return data
        except:
            return default

@app.post("/api/settings/themes")
async def save_theme_settings(data: dict):
    os.makedirs("settings", exist_ok=True)
    with open("settings/themes.json", "w") as f:
        json.dump(data, f, indent=4)
    return {"message": "Theme settings saved successfully"}

if __name__ == "__main__":
    import uvicorn
    import webbrowser

    print("\n🚀 Server starting...\n")
    print(f"   👉 Local URL:      http://127.0.0.1:{PORT}")

    network_ips = get_all_network_ips()

    # WiFi / LAN URLs (192.168.x.x, 10.x.x.x, 172.x.x.x)
    for ip in network_ips["wifi"]:
        print(f"   👉 WiFi URL:       http://{ip}:{PORT}")

    # Real Ethernet URLs (non-APIPA routed IPs that aren't private ranges)
    for ip in network_ips["ethernet"]:
        print(f"   👉 Ethernet URL:   http://{ip}:{PORT}")

    # Self-assigned / APIPA (169.254.x.x) - link-local, no DHCP
    for ip in network_ips["self_assign"]:
        print(f"   👉 Self-Assign IP: http://{ip}:{PORT}")

    print()  # blank line for readability

    # Auto open browser
    webbrowser.open(f"http://127.0.0.1:{PORT}")

    uvicorn.run(
        "app:app",
        host="0.0.0.0",   # allows network access
        port=PORT,
        reload=True        # 🔥 auto reload
    )
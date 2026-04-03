"""
Kalyan College Management System - FastAPI Backend
Admission management + Fee management (Merged Single File Version)
"""

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import socket
import netifaces
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from datetime import datetime
import csv
import io
import random
import os
import json

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

# ═══════════════════════════════════════════════════════════
#  DATABASE LOGIC (Merged from database.py)
# ═══════════════════════════════════════════════════════════

DATA_FILE = "database.json"

def init_db():
    if not os.path.exists(DATA_FILE):
        save_db({"students": [], "fee_records": [], "student_id_seq": 1, "fee_id_seq": 1})

def load_db():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    return {"students": [], "fee_records": [], "student_id_seq": 1, "fee_id_seq": 1}

def save_db(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_db():
    db = load_db()
    try:
        yield db
    finally:
        pass # we don't automatically save to prevent partial states. Save manually.

# Dummy classes to act as objects where needed
class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


# ═══════════════════════════════════════════════════════════
#  FEE STRUCTURE LOGIC (Merged from fee_structure.py)
# ═══════════════════════════════════════════════════════════

FEE_FILE = "fee-structure.json"

_COURSES_BASE = [
    "B.A.",
    "B.Com.",
    "B.Sc. (Biology)",
    "B.Sc. (Mathematics)",
    "B.Sc. Micro Biology",
    "B.Sc. IT (Information Technology)",
    "B.Sc. Computer Science",
    "B.Sc. Electronics",
    "B.Sc. Biotechnology",
    "BBA (Bachelor of Business Administration)",
    "BCA (Bachelor of Computer Applications)",
    "B.Lib (Bachelor of Library Science)",
    "BAJMC (Bachelor of Arts in Journalism & Mass Communication)",
    "M.A. (Previous)",
    "M.A. (Final)",
    "M.Com. (Previous)",
    "M.Com. (Final)",
    "M.Sc. (Botany - Previous)",
    "M.Sc. (Botany - Final)",
    "M.Sc. (Chemistry - Previous)",
    "M.Sc. (Chemistry - Final)",
    "M.Sc. (Mathematics - Previous)",
    "M.Sc. (Mathematics - Final)",
    "M.Sc. (Physics - Previous)",
    "M.Sc. (Physics - Final)",
    "M.Sc. (Zoology - Previous)",
    "M.Sc. (Zoology - Final)",
    "M.Sc. (Computer Science - Previous)",
    "M.Sc. (Computer Science - Final)",
    "M.Sc. (Biotechnology - Previous)",
    "M.Sc. (Biotechnology - Final)",
    "PGDCA (Post Graduate Diploma in Computer Applications)",
]

_FEE_INSTALLMENTS_BASE = {
    "B.A.": {
        "first": {"various": 3600, "tuition": 350, "practical": 0, "total": 3950},
        "second": {"various": 2200, "tuition": 350, "practical": 0, "total": 2550},
        "year_total": 6500,
    },
    "B.Com.": {
        "first": {"various": 7400, "tuition": 450, "practical": 0, "total": 7850},
        "second": {"various": 4000, "tuition": 450, "practical": 0, "total": 4450},
        "year_total": 12300,
    },
    "B.Sc. (Biology)": {
        "first": {"various": 8100, "tuition": 600, "practical": 150, "total": 8850},
        "second": {"various": 5000, "tuition": 600, "practical": 150, "total": 5750},
        "year_total": 14600,
    },
    "B.Sc. (Mathematics)": {
        "first": {"various": 8100, "tuition": 600, "practical": 150, "total": 8850},
        "second": {"various": 5000, "tuition": 600, "practical": 150, "total": 5750},
        "year_total": 14600,
    },
    "B.Sc. Micro Biology": {
        "first": {"various": 8500, "tuition": 1350, "practical": 450, "total": 10300},
        "second": {"various": 5000, "tuition": 1350, "practical": 450, "total": 6800},
        "year_total": 17100,
    },
    "B.Sc. IT (Information Technology)": {
        "first": {"various": 8500, "tuition": 1350, "practical": 450, "total": 10300},
        "second": {"various": 5000, "tuition": 1350, "practical": 450, "total": 6800},
        "year_total": 17100,
    },
    "B.Sc. Computer Science": {
        "first": {"various": 8500, "tuition": 1350, "practical": 450, "total": 10300},
        "second": {"various": 5000, "tuition": 1350, "practical": 450, "total": 6800},
        "year_total": 17100,
    },
    "B.Sc. Electronics": {
        "first": {"various": 8500, "tuition": 1350, "practical": 450, "total": 10300},
        "second": {"various": 5000, "tuition": 1350, "practical": 450, "total": 6800},
        "year_total": 17100,
    },
    "B.Sc. Biotechnology": {
        "first": {"various": 9400, "tuition": 4500, "practical": 2700, "total": 16600},
        "second": {"various": 4000, "tuition": 4500, "practical": 2700, "total": 11200},
        "year_total": 27800,
    },
    "BBA (Bachelor of Business Administration)": {
        "first": {"various": 11100, "tuition": 3000, "practical": 0, "total": 14100},
        "second": {"various": 2800, "tuition": 6500, "practical": 0, "total": 9300},
        "year_total": 23400,
    },
    "BCA (Bachelor of Computer Applications)": {
        "first": {"various": 12000, "tuition": 2000, "practical": 1800, "total": 15800},
        "second": {"various": 3600, "tuition": 5000, "practical": 1800, "total": 10400},
        "year_total": 26200,
    },
    "B.Lib (Bachelor of Library Science)": {
        "first": {"various": 8600, "tuition": 2000, "practical": 450, "total": 11050},
        "second": {"various": 4800, "tuition": 2000, "practical": 450, "total": 7250},
        "year_total": 18300,
    },
    "BAJMC (Bachelor of Arts in Journalism & Mass Communication)": {
        "first": {"various": 5650, "tuition": 3000, "practical": 0, "total": 8650},
        "second": {"various": 2000, "tuition": 3000, "practical": 600, "total": 5600},
        "year_total": 14250,
    },
    "M.A. (Previous)": {
        "first": {"various": 4200, "tuition": 750, "practical": 0, "total": 4950},
        "second": {"various": 2300, "tuition": 750, "practical": 0, "total": 3050},
        "year_total": 8000,
    },
    "M.A. (Final)": {
        "first": {"various": 4200, "tuition": 750, "practical": 0, "total": 4950},
        "second": {"various": 2300, "tuition": 750, "practical": 0, "total": 3050},
        "year_total": 8000,
    },
    "M.Com. (Previous)": {
        "first": {"various": 7500, "tuition": 750, "practical": 0, "total": 8250},
        "second": {"various": 4600, "tuition": 750, "practical": 0, "total": 5350},
        "year_total": 13600,
    },
    "M.Com. (Final)": {
        "first": {"various": 7500, "tuition": 750, "practical": 0, "total": 8250},
        "second": {"various": 4600, "tuition": 750, "practical": 0, "total": 5350},
        "year_total": 13600,
    },
    "M.Sc. (Botany - Previous)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Botany - Final)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Chemistry - Previous)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Chemistry - Final)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Mathematics - Previous)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Mathematics - Final)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Physics - Previous)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Physics - Final)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Zoology - Previous)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Zoology - Final)": {
        "first": {"various": 11200, "tuition": 0, "practical": 500, "total": 11700},
        "second": {"various": 3200, "tuition": 4000, "practical": 500, "total": 7700},
        "year_total": 19400,
    },
    "M.Sc. (Computer Science - Previous)": {
        "first": {"various": 10600, "tuition": 2000, "practical": 1200, "total": 13800},
        "second": {"various": 3900, "tuition": 4000, "practical": 1200, "total": 9100},
        "year_total": 22900,
    },
    "M.Sc. (Computer Science - Final)": {
        "first": {"various": 10600, "tuition": 2000, "practical": 1200, "total": 13800},
        "second": {"various": 3900, "tuition": 4000, "practical": 1200, "total": 9100},
        "year_total": 22900,
    },
    "M.Sc. (Biotechnology - Previous)": {
        "first": {"various": 8450, "tuition": 5150, "practical": 7500, "total": 21100},
        "second": {"various": 4900, "tuition": 4500, "practical": 4500, "total": 13900},
        "year_total": 35000,
    },
    "M.Sc. (Biotechnology - Final)": {
        "first": {"various": 8450, "tuition": 5150, "practical": 7500, "total": 21100},
        "second": {"various": 4900, "tuition": 4500, "practical": 4500, "total": 13900},
        "year_total": 35000,
    },
    "PGDCA (Post Graduate Diploma in Computer Applications)": {
        "first": {"various": 12350, "tuition": 1800, "practical": 0, "total": 14150},
        "second": {"various": 1800, "tuition": 7500, "practical": 0, "total": 9300},
        "year_total": 23450,
    },
}

_FEE_HEADS_DETAIL_BASE = {
    "B.A.": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1000, "Student Development": 250,
        "College Development": 650, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 2200, "Gym Development": 100, "TOTAL": 5800,
    },
    "B.Com.": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 6000, "Gym Development": 100, "TOTAL": 11400,
    },
    "B.Sc. (Biology)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 7700, "Gym Development": 100, "TOTAL": 13100,
    },
    "B.Sc. (Mathematics)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 7700, "Gym Development": 100, "TOTAL": 13100,
    },
    "B.Sc. IT (Information Technology)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8100, "Gym Development": 100, "TOTAL": 13500,
    },
    "B.Sc. Computer Science": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8100, "Gym Development": 100, "TOTAL": 13500,
    },
    "B.Sc. Electronics": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8100, "Gym Development": 100, "TOTAL": 13500,
    },
    "B.Sc. Micro Biology": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8100, "Gym Development": 100, "TOTAL": 13500,
    },
    "B.Sc. Biotechnology": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 100,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 0, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8000, "Gym Development": 100, "TOTAL": 13400,
    },
    "BBA (Bachelor of Business Administration)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 600, "Physical Education": 300,
        "Non Aided Staff Fund": 7350, "Gym Development": 100, "TOTAL": 13900,
    },
    "BCA (Bachelor of Computer Applications)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 600, "Physical Education": 300,
        "Non Aided Staff Fund": 9050, "Gym Development": 100, "TOTAL": 15600,
    },
    "B.Lib (Bachelor of Library Science)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 600, "Physical Education": 300,
        "Non Aided Staff Fund": 6850, "Gym Development": 100, "TOTAL": 13400,
    },
    "BAJMC (Bachelor of Arts in Journalism & Mass Communication)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 750, "Student Development": 500,
        "College Development": 0, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 600, "Physical Education": 300,
        "Non Aided Staff Fund": 3550, "Gym Development": 100, "TOTAL": 7650,
    },
    "M.A.": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1000, "Student Development": 250,
        "College Development": 700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 2300, "Gym Development": 100, "TOTAL": 6500,
    },
    "M.Com.": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 6150, "Gym Development": 100, "TOTAL": 12100,
    },
    "M.Sc.": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8450, "Gym Development": 100, "TOTAL": 14400,
    },
    "M.Sc. (Computer Science)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 8550, "Gym Development": 100, "TOTAL": 14500,
    },
    "M.Sc. (Biotechnology)": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 0, "Physical Education": 300,
        "Non Aided Staff Fund": 7400, "Gym Development": 100, "TOTAL": 13350,
    },
    "PGDCA": {
        "Admission Fees": 500, "Amalgamated Fund": 100, "Library Development": 500,
        "Home Examination": 200, "Establishment Fund": 1500, "Student Development": 500,
        "College Development": 1700, "Cycle Stand": 100, "Caution Money (Ref.)": 300,
        "Seminar / Workshop": 150, "Computer Maint.": 600, "Physical Education": 300,
        "Non Aided Staff Fund": 7600, "Gym Development": 100, "TOTAL": 14150,
    },
}

def load_fee_data() -> dict:
    if os.path.exists(FEE_FILE):
        try:
            with open(FEE_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    
    return {
        "COURSES": _COURSES_BASE,
        "FEE_INSTALLMENTS": _FEE_INSTALLMENTS_BASE,
        "FEE_HEADS_DETAIL": _FEE_HEADS_DETAIL_BASE
    }

def save_fee_data(data: dict):
    with open(FEE_FILE, "w") as f:
        json.dump(data, f, indent=4)

COURSES = load_fee_data().get("COURSES", _COURSES_BASE)

def get_fee_structure(course_name: str) -> dict | None:
    data = load_fee_data()
    installments_data = data.get("FEE_INSTALLMENTS", _FEE_INSTALLMENTS_BASE)
    installment = installments_data.get(course_name)
    if not installment:
        return None

    heads_key = course_name
    if course_name.startswith("M.A."):
        heads_key = "M.A."
    elif course_name.startswith("M.Com."):
        heads_key = "M.Com."
    elif "Computer Science" in course_name and course_name.startswith("M.Sc."):
        heads_key = "M.Sc. (Computer Science)"
    elif "Biotechnology" in course_name and course_name.startswith("M.Sc."):
        heads_key = "M.Sc. (Biotechnology)"
    elif course_name.startswith("M.Sc."):
        heads_key = "M.Sc."
    elif course_name.startswith("PGDCA"):
        heads_key = "PGDCA"

    heads_data = data.get("FEE_HEADS_DETAIL", _FEE_HEADS_DETAIL_BASE)
    heads = heads_data.get(heads_key, {})

    return {
        "course": course_name,
        "installments": installment,
        "detailed_heads": heads,
    }

def get_all_fee_structures() -> list:
    data = load_fee_data()
    courses_list = data.get("COURSES", _COURSES_BASE)
    result = []
    for course in courses_list:
        structure = get_fee_structure(course)
        if structure:
            result.append(structure)
    return result


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
    data = load_fee_data()
    return {"courses": data.get("COURSES", _COURSES_BASE)}


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


def student_to_dict(s: dict) -> dict:
    return {field: s.get(field, "") or "" for field in STUDENT_FIELDS} | {
        "id": s.get("id"),
        "created_at": str(s.get("created_at", "")),
        "updated_at": str(s.get("updated_at", "")),
    }


@app.post("/api/students")
async def create_student(data: dict, db: dict = Depends(get_db)):
    # Check duplicate admission_no
    existing = next((s for s in db["students"] if s.get("admission_no") == data.get("admission_no")), None)
    if existing:
        raise HTTPException(status_code=400, detail="Admission number already exists")

    student_id = db["student_id_seq"]
    db["student_id_seq"] += 1
    
    student = {
        "id": student_id,
        "created_at": str(datetime.utcnow()),
        "updated_at": str(datetime.utcnow())
    }
    for field in STUDENT_FIELDS:
        student[field] = data.get(field, "")

    db["students"].append(student)
    save_db(db)
    return {"message": "Student added successfully", "student": student_to_dict(student)}


@app.get("/api/students")
def list_students(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: dict = Depends(get_db),
):
    students_list = sorted(db["students"], key=lambda x: x.get("id", 0), reverse=True)
    total = len(students_list)
    
    start = (page - 1) * per_page
    end = start + per_page
    paginated_students = students_list[start:end]

    return {
        "students": [student_to_dict(s) for s in paginated_students],
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
    db: dict = Depends(get_db),
):
    filtered_students = db["students"]

    if q:
        q_lower = q.lower()
        filtered_students = [
            s for s in filtered_students
            if q_lower in s.get("student_name", "").lower() or
               q_lower in s.get("admission_no", "").lower() or
               q_lower in s.get("mobile_no", "").lower()
        ]

    if course:
        filtered_students = [s for s in filtered_students if s.get("course") == course]

    if category:
        filtered_students = [s for s in filtered_students if s.get("category") == category]

    filtered_students = sorted(filtered_students, key=lambda x: x.get("student_name", ""))
    total = len(filtered_students)

    start = (page - 1) * per_page
    end = start + per_page
    paginated_students = filtered_students[start:end]

    return {
        "students": [student_to_dict(s) for s in paginated_students],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@app.get("/api/students/{student_id}")
def get_student(student_id: int, db: dict = Depends(get_db)):
    student = next((s for s in db["students"] if s.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"student": student_to_dict(student)}


@app.put("/api/students/{student_id}")
async def update_student(student_id: int, data: dict, db: dict = Depends(get_db)):
    student = next((s for s in db["students"] if s.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    for field in STUDENT_FIELDS:
        if field in data:
            student[field] = data[field]

    student["updated_at"] = str(datetime.utcnow())
    save_db(db)
    return {"message": "Student updated successfully", "student": student_to_dict(student)}


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int, db: dict = Depends(get_db)):
    student = next((s for s in db["students"] if s.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    db["students"] = [s for s in db["students"] if s.get("id") != student_id]
    db["fee_records"] = [f for f in db["fee_records"] if f.get("student_id") != student_id]
    save_db(db)
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
        father_occupation: str = Field(description="Occupation of the Father") # Add this line
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
                    thinking_level="medium"
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
async def import_csv(file: UploadFile = File(...), db: dict = Depends(get_db)):
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

            existing = next((s for s in db["students"] if s.get("admission_no") == admission_no), None)
            if existing:
                skipped += 1
                continue

            student_id = db["student_id_seq"]
            db["student_id_seq"] += 1
            student = {
                "id": student_id,
                "created_at": str(datetime.utcnow()),
                "updated_at": str(datetime.utcnow())
            }
            
            for csv_col, db_col in CSV_HEADER_MAP.items():
                val = row.get(csv_col, "").strip()
                student[db_col] = val

            db["students"].append(student)
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)}")
            skipped += 1

    save_db(db)
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
async def record_fee_payment(data: dict, db: dict = Depends(get_db)):
    student_id = data.get("student_id")
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")

    try:
        student_id = int(student_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid student_id format")

    student = next((s for s in db["students"] if s.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    receipt_no = f"{random.randint(10000, 99999)}"

    fee_id = db["fee_id_seq"]
    db["fee_id_seq"] += 1
    
    fee_record = {
        "id": fee_id,
        "student_id": student_id,
        "receipt_no": receipt_no,
        "date": data.get("date", datetime.now().strftime("%d-%m-%Y")),
        "academic_year": data.get("academic_year", "2024-25"),
        "fee_period": data.get("fee_period", ""),
        "installment": data.get("installment", "FIRST"),
    }
    
    reserved_keys = {"student_id", "date", "academic_year", "fee_period", "installment", "payment_mode"}
    
    for k, v in data.items():
        if k not in reserved_keys:
            try:
                fee_record[k] = float(v) if v else 0.0
            except ValueError:
                fee_record[k] = v
                
    default_heads = [
        "tuition", "various_heads", "practical", "admission_fee",
        "amalgamated_fund", "library_dev", "home_examination",
        "establishment_fund", "student_dev", "college_dev",
        "cycle_stand", "caution_money", "seminar_ws",
        "computer_maint", "physical_edu", "non_aided_staff",
        "gym_dev", "total_amount"
    ]
    for head in default_heads:
         if head not in fee_record:
             fee_record[head] = 0.0

    fee_record["payment_mode"] = data.get("payment_mode", "CASH")
    fee_record["payment_status"] = "PAID"
    fee_record["created_at"] = str(datetime.utcnow())

    db["fee_records"].append(fee_record)
    save_db(db)

    return {
        "message": "Fee payment recorded successfully",
        "receipt_no": receipt_no,
        "fee_record_id": fee_id,
    }


@app.get("/api/fees/student/{student_id}")
def get_student_fees(student_id: int, db: dict = Depends(get_db)):
    student = next((s for s in db["students"] if s.get("id") == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    records = [f for f in db["fee_records"] if f.get("student_id") == student_id]
    records = sorted(records, key=lambda x: x.get("id", 0), reverse=True)

    total_paid = sum(r.get("total_amount", 0) for r in records)
    fee_structure = get_fee_structure(student.get("course", ""))
    year_total = fee_structure["installments"]["year_total"] if fee_structure else 0

    return {
        "student_name": student.get("student_name", ""),
        "admission_no": student.get("admission_no", ""),
        "course": student.get("course", ""),
        "total_fee": year_total,
        "total_paid": total_paid,
        "balance": year_total - total_paid,
        "records": [
            {
                "id": r.get("id"),
                "receipt_no": r.get("receipt_no"),
                "date": r.get("date"),
                "academic_year": r.get("academic_year"),
                "installment": r.get("installment"),
                "total_amount": r.get("total_amount"),
                "payment_mode": r.get("payment_mode"),
                "payment_status": r.get("payment_status"),
            }
            for r in records
        ],
    }


@app.get("/api/fees/receipt/{fee_record_id}/pdf")
def generate_fee_receipt_pdf(fee_record_id: int, db: dict = Depends(get_db)):
    fee_record_dict = next((f for f in db["fee_records"] if f.get("id") == fee_record_id), None)
    if not fee_record_dict:
        raise HTTPException(status_code=404, detail="Fee record not found")

    student_dict = next((s for s in db["students"] if s.get("id") == fee_record_dict.get("student_id")), None)
    if not student_dict:
        raise HTTPException(status_code=404, detail="Student not found")

    fee_record = Struct(**fee_record_dict)
    student = Struct(**student_dict)

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
    draw_row(y, "Communic.", 0.00, "ET-Lab.", 0.00, "Library Dev.", getattr(fee_record, 'library_dev', 0.0), "", 0.00)
    y -= 20
    draw_row(y, "Pers.Dev", 0.00, "Others -4", getattr(fee_record, 'home_examination', 0.0), "Others -5", 0.00, "", 0.00)

    dyn_heads = [(k, v) for k, v in fee_record_dict.items() if k.startswith("dyn_") and isinstance(v, (int, float)) and v > 0]
    while dyn_heads:
        chunk = dyn_heads[:4]
        dyn_heads = dyn_heads[4:]
        args = []
        for key, val in chunk:
            display_name = key[4:].replace('_', ' ').title()[:15]
            args.extend([display_name, val])
        while len(args) < 8:
            args.extend(["", 0.00])
        y -= 20
        draw_row(y, *args)

    y -= 40
    c.drawString(50, y, f"{(getattr(fee_record, 'payment_mode', 'CASH') or 'CASH') + '-NO':<23}           DATE                  Total :           {getattr(fee_record, 'total_amount', 0.0):>10.2f}")

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
def dashboard_stats(db: dict = Depends(get_db)):
    total_students = len(db["students"])
    total_fee_records = len(db["fee_records"])
    
    course_counts_dict = {}
    gender_counts_dict = {}
    category_counts_dict = {}
    
    for s in db["students"]:
        course = s.get("course", "")
        gender = s.get("gender", "")
        category = s.get("category", "")
        
        course_counts_dict[course] = course_counts_dict.get(course, 0) + 1
        gender_counts_dict[gender] = gender_counts_dict.get(gender, 0) + 1
        category_counts_dict[category] = category_counts_dict.get(category, 0) + 1
        
    fees_sum = sum(f.get("total_amount", 0) for f in db["fee_records"])

    return {
        "total_students": total_students,
        "total_fee_records": total_fee_records,
        "total_fees_collected": fees_sum,
        "total_courses": len(load_fee_data().get("COURSES", _COURSES_BASE)),
        "course_distribution": course_counts_dict,
        "gender_distribution": {g or "Unknown": count for g, count in gender_counts_dict.items()},
        "category_distribution": {c or "Unknown": count for c, count in category_counts_dict.items()},
    }


# ═══════════════════════════════════════════════════════════
#  SETTINGS APIs
# ═══════════════════════════════════════════════════════════

@app.get("/api/settings/fee-structure")
def get_fee_structure_settings():
    return load_fee_data()

@app.post("/api/settings/fee-structure")
async def save_fee_structure_settings(data: dict):
    save_fee_data(data)
    return {"message": "Fee structure saved successfully"}

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
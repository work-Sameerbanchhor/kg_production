"""
Database models and setup for Kalyan College Management System.
Uses JSON storage.
"""

import json
import os
from datetime import datetime

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

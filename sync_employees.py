# ============================================================
#   Smart Biometric Attendance System — Auto Employee Sync
#   PostgreSQL (biometric_db) → Odoo 19 (hr.employee)
#
#   Creates ONLY employees that exist in PostgreSQL.
#   Uses employees.employee_code as Odoo hr.employee barcode/badge.
#
#   Run:
#     python biometric_system/sync_employees.py
# ============================================================

import xmlrpc.client
from typing import Dict, List, Optional

try:
    from .config import ODOO_CONFIG
    from .database import get_connection
except ImportError:  # running as script
    from config import ODOO_CONFIG
    from database import get_connection


def odoo_authenticate():
    url = ODOO_CONFIG["url"]
    db = ODOO_CONFIG["db"]
    user = ODOO_CONFIG["username"]
    pwd = ODOO_CONFIG["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    version = common.version()
    print(f"✅ Connected to Odoo {version.get('server_version', '?')}")

    uid = common.authenticate(db, user, pwd, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed. Check config.py credentials.")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def fetch_biometric_employees() -> List[dict]:
    """Fetch all active employees from biometric_db."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            e.id,
            e.employee_code,
            e.full_name,
            e.email,
            e.designation,
            d.name AS department_name
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.is_active = TRUE
        ORDER BY e.id
        """
    )
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [dict(zip(columns, row)) for row in rows]


def get_existing_odoo_employees_by_barcode(models, uid) -> Dict[str, int]:
    """Return mapping: barcode(str) -> hr.employee.id"""
    db = ODOO_CONFIG["db"]
    pwd = ODOO_CONFIG["password"]

    # Fetch all employees that have a barcode.
    # Odoo search domain: [('barcode','!=',False)]
    emp_ids = models.execute_kw(
        db, uid, pwd,
        "hr.employee", "search",
        [[['barcode', '!=', False]]]
    )
    if not emp_ids:
        return {}

    employees = models.execute_kw(
        db, uid, pwd,
        "hr.employee", "read",
        [emp_ids],
        {"fields": ["id", "barcode"]}
    )

    mapping: Dict[str, int] = {}
    for e in employees:
        bc = e.get("barcode")
        if bc:
            mapping[str(bc).strip()] = e["id"]
    return mapping


def get_or_create_department(models, uid, department_name: Optional[str]) -> Optional[int]:
    if not department_name:
        return None

    db = ODOO_CONFIG["db"]
    pwd = ODOO_CONFIG["password"]

    existing = models.execute_kw(
        db, uid, pwd,
        "hr.department", "search",
        [[['name', '=', department_name]]]
    )
    if existing:
        return existing[0]

    new_id = models.execute_kw(
        db, uid, pwd,
        "hr.department", "create",
        [{"name": department_name}]
    )
    print(f"   📁 Created department '{department_name}' in Odoo (id={new_id})")
    return new_id


def sync_employees():
    print("\n" + "=" * 55)
    print("   EMPLOYEE SYNC: PostgreSQL → Odoo (only biometric_db employees)")
    print("=" * 55)

    uid_models = odoo_authenticate()
    uid, models = uid_models

    bio_employees = fetch_biometric_employees()
    print(f"\n📋 Found {len(bio_employees)} employee(s) in PostgreSQL biometric_db")

    existing = get_existing_odoo_employees_by_barcode(models, uid)
    print(f"📋 Found {len(existing)} employee(s) in Odoo with barcode/badge IDs")

    created = 0
    skipped = 0
    failed = 0

    db = ODOO_CONFIG["db"]
    pwd = ODOO_CONFIG["password"]

    for emp in bio_employees:
        code = str(emp.get("employee_code", "")).strip()
        name = emp.get("full_name") or ""

        # We must have barcode to match sync later.
        if not code:
            print(f"   ⚠️  Skipping '{name}' — employee_code is empty")
            skipped += 1
            continue

        if code in existing:
            print(f"   ⏭️  Skipping '{name}' — already exists in Odoo (barcode={code})")
            skipped += 1
            continue

        try:
            dept_id = get_or_create_department(models, uid, emp.get("department_name"))

            vals = {
                "name": name,
                "barcode": code,  # IMPORTANT: used by sync_attendance_to_odoo()
            }
            if dept_id:
                vals["department_id"] = dept_id
            if emp.get("designation"):
                # hr.employee has 'job_title' field in many Odoo versions
                vals["job_title"] = emp.get("designation")
            if emp.get("email"):
                vals["work_email"] = emp.get("email")

            new_id = models.execute_kw(db, uid, pwd, "hr.employee", "create", [vals])
            print(f"   ✅ Created '{name}' in Odoo (id={new_id}, badge={code})")
            created += 1

        except Exception as e:
            print(f"   ❌ Failed to create '{name}' (barcode={code}): {e}")
            failed += 1

    print("\n" + "=" * 55)
    print("   SYNC COMPLETE")
    print(f"   Created : {created}")
    print(f"   Skipped : {skipped} (already existed or invalid)")
    print(f"   Failed  : {failed}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    sync_employees()


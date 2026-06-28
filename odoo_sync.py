# ============================================================
#   Smart Biometric Attendance System — Odoo Sync (FIXED)
#   PostgreSQL → Odoo 19 hr.attendance
#   Production-safe UTC handling
# ============================================================

import xmlrpc.client
from datetime import datetime
import pytz


try:
    from .config import ODOO_CONFIG
    from .database import get_unsynced_attendance, mark_synced_to_odoo
except ImportError:
    from config import ODOO_CONFIG
    from database import get_unsynced_attendance, mark_synced_to_odoo


# ─────────────────────────────────────────────
# Convert DB timestamps to UTC-naive strings for Odoo
# ─────────────────────────────────────────────
# Odoo expects a datetime string; if we pass a local-time value as if it were UTC,
# it will be displayed with an offset. To avoid that, normalize everything to UTC.
DB_TZ = pytz.timezone("Asia/Karachi")


def to_utc_naive_str(dt):
    """Return 'YYYY-MM-DD HH:MM:SS' in UTC for Odoo RPC."""
    if dt is None:
        return False

    # If DB returns string
    if isinstance(dt, str):
        s = dt.split(".")[0] if "." in dt else dt
        # Try parsing as naive; assume it's DB_TZ
        parsed = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return DB_TZ.localize(parsed).astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")

    # If DB returns datetime
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        # Aware datetime -> convert to UTC
        return dt.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")

    # Naive datetime -> assume it's in DB timezone
    localized = DB_TZ.localize(dt)
    return localized.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")



# ─────────────────────────────────────────────
# Odoo Authentication
# ─────────────────────────────────────────────
def odoo_authenticate():
    try:
        url  = ODOO_CONFIG["url"]
        db   = ODOO_CONFIG["db"]
        user = ODOO_CONFIG["username"]
        pwd  = ODOO_CONFIG["password"]

        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")

        version = common.version()
        print(f"✅ Connected to Odoo {version.get('server_version', '?')}")

        uid = common.authenticate(db, user, pwd, {})
        if not uid:
            print("❌ Authentication failed")
            return None

        print(f"✅ Authenticated UID: {uid}")

        models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
        return uid, models

    except Exception as e:
        print(f"❌ Odoo connection error: {e}")
        return None


# ─────────────────────────────────────────────
# Fetch Odoo Employees
# ─────────────────────────────────────────────
def get_odoo_employees(models, uid):
    db  = ODOO_CONFIG["db"]
    pwd = ODOO_CONFIG["password"]

    ids = models.execute_kw(db, uid, pwd, "hr.employee", "search", [[]])

    if not ids:
        return []

    employees = models.execute_kw(
        db, uid, pwd,
        "hr.employee", "read",
        [ids],
        {"fields": ["id", "name", "barcode"]}
    )

    return [
        (e["id"], e["name"], e.get("barcode") or "")
        for e in employees
    ]


# ─────────────────────────────────────────────
# Check Attendance Module
# ─────────────────────────────────────────────
def check_attendance_module(models, uid):
    try:
        db  = ODOO_CONFIG["db"]
        pwd = ODOO_CONFIG["password"]

        models.execute_kw(db, uid, pwd,
                          "hr.attendance", "search", [[]], {"limit": 1})
        return True

    except Exception as e:
        print(f"❌ hr.attendance error: {e}")
        return False


# ─────────────────────────────────────────────
# MAIN SYNC FUNCTION
# ─────────────────────────────────────────────
def sync_attendance_to_odoo():

    print("\n==============================")
    print(" ODOO ATTENDANCE SYNC ")
    print("==============================\n")

    auth = odoo_authenticate()
    if not auth:
        return

    uid, models = auth

    if not check_attendance_module(models, uid):
        return

    unsynced = get_unsynced_attendance()

    if not unsynced:
        print("✅ No unsynced records")
        return

    print(f"📋 Records to sync: {len(unsynced)}")

    # Employee map (barcode → Odoo ID)
    odoo_emps = get_odoo_employees(models, uid)

    code_map = {
        str(barcode).strip(): emp_id
        for emp_id, _, barcode in odoo_emps
        if barcode
    }

    synced = 0
    skipped = 0
    failed = 0

    db  = ODOO_CONFIG["db"]
    pwd = ODOO_CONFIG["password"]

    for rec in unsynced:

        attendance_id = rec["attendance_id"]
        emp_code      = str(rec.get("employee_code", "")).strip()
        check_in      = rec.get("check_in")
        check_out     = rec.get("check_out")

        odoo_emp_id = code_map.get(emp_code)

        if not odoo_emp_id:
            print(f"⚠️ No Odoo employee for {emp_code}")
            skipped += 1
            continue

        if not check_in:
            skipped += 1
            continue

        try:
            vals = {
                "employee_id": odoo_emp_id,
                "check_in": to_utc_naive_str(check_in),
            }

            if check_out:
                vals["check_out"] = to_utc_naive_str(check_out)


            # Check open attendance
            open_att = models.execute_kw(
                db, uid, pwd,
                "hr.attendance", "search",
                [[("employee_id", "=", odoo_emp_id),
                  ("check_out", "=", False)]],
                {"limit": 1}
            )

            if open_att:
                models.execute_kw(
                    db, uid, pwd,
                    "hr.attendance", "write",
                    [open_att, {"check_out": to_utc_naive_str(check_out) or to_utc_naive_str(check_in)}]
                )

                mark_synced_to_odoo(attendance_id)
                print(f"🔄 Updated open attendance {attendance_id}")

            else:
                new_id = models.execute_kw(
                    db, uid, pwd,
                    "hr.attendance", "create",
                    [vals]
                )
                mark_synced_to_odoo(attendance_id)
                print(f"✅ Created attendance {attendance_id} → {new_id}")

            synced += 1

        except Exception as e:
            print(f"❌ Failed {attendance_id}: {e}")
            failed += 1

    print("\n==============================")
    print(f"Synced  : {synced}")
    print(f"Skipped : {skipped}")
    print(f"Failed  : {failed}")
    print("==============================\n")


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sync_attendance_to_odoo()
# ============================================================
# Smart Biometric Attendance System — DATABASE LAYER (FIXED)
# ============================================================

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

try:
    from .config import DB_CONFIG
except ImportError:
    from config import DB_CONFIG


# ─────────────────────────────────────────────
# DB CONNECTION
# ─────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ─────────────────────────────────────────────
# GET ALL EMPLOYEES + FACE ENCODINGS
# ─────────────────────────────────────────────
def get_all_employees():
    query = """
        SELECT
            e.id,
            e.employee_code,
            e.full_name,
            fe.encoding_data
        FROM employees e
        LEFT JOIN face_encodings fe ON fe.employee_id = e.id
        WHERE e.is_active = TRUE
        ORDER BY e.employee_code
    """

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return [
        (r["id"], r["employee_code"], r["full_name"], r["encoding_data"])
        for r in rows
    ]


# ─────────────────────────────────────────────
# SAVE FACE ENCODING
# ─────────────────────────────────────────────
def save_face_encoding(employee_id, encoding_bytes):
    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                "DELETE FROM face_encodings WHERE employee_id = %s",
                (employee_id,),
            )

            cur.execute(
                """
                INSERT INTO face_encodings (employee_id, encoding_data, created_at)
                VALUES (%s, %s::BYTEA, NOW())
                """,
                (employee_id, psycopg2.Binary(encoding_bytes)),
            )

        conn.commit()

    print("✅ Face encoding saved")


# ─────────────────────────────────────────────
# CHECK-IN (SAFE - ONE PER DAY)
# ─────────────────────────────────────────────
def mark_check_in(employee_id):
    today = datetime.now().date()

    with get_connection() as conn:
        with conn.cursor() as cur:

            # check already exists
            cur.execute("""
                SELECT id FROM attendance_logs
                WHERE employee_id = %s
                AND date = %s
                AND check_in IS NOT NULL
                LIMIT 1
            """, (employee_id, today))

            if cur.fetchone():
                print("⚠️ Already checked in today")
                return False

            cur.execute("""
                INSERT INTO attendance_logs
                (employee_id, check_in, date, status, synced_to_odoo, created_at)
                VALUES (%s, NOW(), %s, 'check_in', FALSE, NOW())
            """, (employee_id, today))

        conn.commit()

    print("✅ Check-in recorded")
    return True


# ─────────────────────────────────────────────
# CHECK-OUT (UPDATE LAST OPEN RECORD)
# ─────────────────────────────────────────────
def mark_check_out(employee_id):
    today = datetime.now().date()

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT id
                FROM attendance_logs
                WHERE employee_id = %s
                AND date = %s
                AND check_in IS NOT NULL
                AND check_out IS NULL
                ORDER BY id DESC
                LIMIT 1
            """, (employee_id, today))

            row = cur.fetchone()

            if not row:
                print("❌ No open check-in found")
                return False

            attendance_id = row[0]

            cur.execute("""
                UPDATE attendance_logs
                SET check_out = NOW(),
                    status = 'check_out'
                WHERE id = %s
            """, (attendance_id,))

        conn.commit()

    print("✅ Check-out recorded")
    return True


# ─────────────────────────────────────────────
# TODAY REPORT VIEW
# ─────────────────────────────────────────────
def get_today_attendance():
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT *
                    FROM daily_attendance
                    WHERE date = CURRENT_DATE
                    ORDER BY employee_code
                """)
                return cur.fetchall()

    except Exception as e:
        print(f"⚠️ daily_attendance view error: {e}")
        return []


# ─────────────────────────────────────────────
# UNSYNCED RECORDS FOR ODOO
# ─────────────────────────────────────────────
def get_unsynced_attendance():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            a.id AS attendance_id,
            e.employee_code,
            e.full_name,
            date_trunc('second', a.check_in) AS check_in,
            date_trunc('second', a.check_out) AS check_out,
            a.date,
            a.status
        FROM attendance_logs a
        JOIN employees e ON e.id = a.employee_id
        WHERE a.synced_to_odoo = FALSE
        AND a.check_in IS NOT NULL
        ORDER BY a.id
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return rows


# ─────────────────────────────────────────────
# MARK SYNCED TO ODOO
# ─────────────────────────────────────────────
def mark_synced_to_odoo(attendance_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE attendance_logs
                SET synced_to_odoo = TRUE
                WHERE id = %s
            """, (attendance_id,))
        conn.commit()

    print("✅ Synced to Odoo")
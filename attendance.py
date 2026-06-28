# ============================================================
# Smart Biometric Attendance System (webcam) — PKT VERSION
# ============================================================

import cv2
import numpy as np
from datetime import datetime
import pytz
import smtplib
from email.mime.text import MIMEText

try:
    from .camera_utils import open_usable_camera
except ImportError:
    from camera_utils import open_usable_camera


# ─────────────────────────────────────────────
# Pakistan Timezone
# ─────────────────────────────────────────────
PKT = pytz.timezone("Asia/Karachi")


def get_pk_time():
    return datetime.now(PKT)


def format_pk_time(dt):
    if isinstance(dt, str):
        dt = datetime.strptime(dt.split(".")[0], "%Y-%m-%d %H:%M:%S")
    return dt.astimezone(PKT).strftime("%Y-%m-%d %I:%M:%S %p")


# ─────────────────────────────────────────────
# EMAIL NOTIFICATION — ADD YOUR DETAILS BELOW
# ─────────────────────────────────────────────
import os`nfrom dotenv import load_dotenv`nload_dotenv()`nEMAIL_SENDER   = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")
def send_email_alert(employee_name, action="CHECK IN"):
    try:
        # NOTE: If checkout emails fail, this exception text will appear.

        time_now = get_pk_time().strftime("%Y-%m-%d %I:%M:%S %p")

        msg = MIMEText(f"""
Smart Biometric Attendance System
----------------------------------

✅ Attendance Recorded

👤 Employee : {employee_name}
🕐 Action   : {action}
📅 Time     : {time_now} (PKT)

----------------------------------
This is an automated alert.
        """)

        msg['Subject'] = f"🔔 Attendance: {employee_name} — {action}"
        msg['From']    = EMAIL_SENDER
        msg['To']      = EMAIL_RECEIVER

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"📧 Email alert sent for {employee_name} ({action})")

    except Exception as e:
        # Print full exception details to debug checkout email issues
        print(f"⚠️ Email failed: {type(e).__name__}: {e}")



# ─────────────────────────────────────────────
# SAFE IMPORTS
# ─────────────────────────────────────────────
try:
    from .face_embeddings import cosine_distance, get_face_embedding
    from .config import CAMERA_INDEX, INSIGHTFACE_MAX_COSINE_DISTANCE
    from .database import (
        get_today_attendance,
        get_all_employees,
        mark_check_in,
        mark_check_out,
    )
except ImportError:
    from face_embeddings import cosine_distance, get_face_embedding
    from config import CAMERA_INDEX, INSIGHTFACE_MAX_COSINE_DISTANCE
    from database import (
        get_today_attendance,
        get_all_employees,
        mark_check_in,
        mark_check_out,
    )


# ─────────────────────────────────────────────
# LOAD FACES
# ─────────────────────────────────────────────
def load_known_faces():
    employees = get_all_employees()

    encodings = []
    ids = []
    names = []

    for emp_id, code, name, enc in employees:
        if enc is None:
            continue

        encodings.append(np.frombuffer(bytes(enc), dtype=np.float32))
        ids.append(emp_id)
        names.append(name)

    return encodings, ids, names


# ─────────────────────────────────────────────
# REPORT (FIXED PKT DISPLAY)
# ─────────────────────────────────────────────
def print_today_report():
    rows = get_today_attendance()

    if not rows:
        print("\n📊 No attendance records")
        return

    print("\n" + "=" * 90)
    print("CODE | NAME | CHECK IN | CHECK OUT | STATUS")
    print("-" * 90)

    for r in rows:
        print(
            r.get("employee_code"),
            "|",
            r.get("full_name"),
            "|",
            format_pk_time(r.get("check_in")) if r.get("check_in") else "",
            "|",
            format_pk_time(r.get("check_out")) if r.get("check_out") else "",
            "|",
            r.get("status"),
        )

    print("=" * 90)


# ─────────────────────────────────────────────
# ATTENDANCE SYSTEM (FIXES: key quit + stable UI)
# ─────────────────────────────────────────────
def run_attendance(mode):
    if mode not in ["check_in", "check_out"]:
        return



    # Local import to avoid circular imports
    try:
        from .register_face import register_face
    except ImportError:
        from register_face import register_face

    encodings, ids, names = load_known_faces()

    if not encodings:
        print("❌ No faces found (no registered encodings in DB)")
        return

    # Probe multiple camera indexes (some systems have wrong default index)
    candidate_indexes = [CAMERA_INDEX] + [i for i in range(0, 6) if i != CAMERA_INDEX]

    cap, used_index, used_backend = open_usable_camera(
        camera_index=CAMERA_INDEX,
        candidate_indexes=candidate_indexes,
        backend_order=None,
        warmup_reads=3,
    )

    if cap is None:
        print(f"❌ Cannot open usable webcam. Tried indexes: {candidate_indexes}")
        return

    print(f"✅ Using webcam index: {used_index} (backend={used_backend})")


    processed = set()

    TARGET_W, TARGET_H = 960, 540

    try:
        print(f"\nRunning {mode}... Press Q or ESC to exit")

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ Failed to read frame")
                break

            frame = cv2.resize(frame, (TARGET_W, TARGET_H))

            now = get_pk_time().strftime("%Y-%m-%d %I:%M:%S %p")
            cv2.putText(
                frame,
                f"{mode.upper()} | {now}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            if 'dbg_i' not in locals():
                dbg_i = 0
            dbg_i += 1

            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

            if dbg_i <= 20:
                try:
                    print(
                        f"DBG frame#{dbg_i}: shape={frame.shape} mean={frame.mean():.4f} small_mean={small.mean():.4f}"
                    )
                except Exception:
                    pass

            try:
                boxes, embeddings = get_face_embedding(small)
            except Exception as e:
                if dbg_i <= 20:
                    print(f"❌ get_face_embedding failed on frame#{dbg_i}: {e}")
                boxes, embeddings = [], []

            for (x1, y1, x2, y2), emb in zip(boxes, embeddings):

                top, left, right, bottom = y1 * 2, x1 * 2, x2 * 2, y2 * 2

                name = "Unknown"
                color = (0, 0, 255)

                if encodings:
                    dists = [cosine_distance(e, emb) for e in encodings]
                    best = int(np.argmin(dists))

                    if dists[best] <= INSIGHTFACE_MAX_COSINE_DISTANCE:
                        emp_id = ids[best]
                        name = names[best]
                        color = (0, 255, 0)

                        if emp_id not in processed:
                            processed.add(emp_id)  # prevent repeating this employee every frame

                            # mark_check_in/mark_check_out must return True when it actually updates the DB
                            if mode == "check_in":
                                success = mark_check_in(emp_id)
                            else:
                                success = mark_check_out(emp_id)

                            action_label = "CHECK IN" if mode == "check_in" else "CHECK OUT"

                            # ✅ EMAIL ALERT — only send when DB marking succeeded
                            if success is True:
                                send_email_alert(name, action_label)
                            else:
                                if mode == "check_in":
                                    print(f"⚠️ Email skipped for {name} — already checked in today")
                                else:
                                    print(f"⚠️ Email skipped for {name} — no open check-in or already checked out")

                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(
                    frame,
                    name,
                    (left, max(0, top - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2,
                )

            try:
                cv2.imshow("Attendance System", frame)
            except Exception as e:
                print(f"⚠️ cv2.imshow failed: {e}")

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("1 Check In")
    print("2 Check Out")
    print("3 Report")

    c = input("Select: ").strip()

    if c == "1":
        run_attendance("check_in")
    elif c == "2":
        run_attendance("check_out")
    elif c == "3":
        print_today_report()


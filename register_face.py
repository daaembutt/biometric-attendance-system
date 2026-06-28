import os

import cv2

try:
    from .config import FACE_DATA_DIR, CAMERA_INDEX
    from .database import get_all_employees, save_face_encoding
    from .face_embeddings import get_face_embedding
except ImportError:  # when running as script
    from config import FACE_DATA_DIR, CAMERA_INDEX
    from database import get_all_employees, save_face_encoding
    from face_embeddings import get_face_embedding


def list_employees():
    employees = get_all_employees()
    print("\n📋 Employees Face Registration Status")
    print("-" * 60)
    for emp_id, code, name, encoding_data in employees:
        status = "Registered" if encoding_data is not None else "Not Registered"
        print(f"ID: {emp_id:<5} Code: {code:<10} Name: {name:<30} → {status}")
    print("-" * 60)


from typing import Tuple, Optional

try:
    from .camera_utils import open_usable_camera
except ImportError:
    from camera_utils import open_usable_camera


def _open_usable_camera():
    """Backward-compatible wrapper used by older code in this module."""

    candidate_indexes = [CAMERA_INDEX] + [i for i in range(0, 6) if i != CAMERA_INDEX]
    cap, used_index, used_backend = open_usable_camera(
        camera_index=CAMERA_INDEX,
        candidate_indexes=candidate_indexes,
        backend_order=None,
        warmup_reads=3,
    )

    return cap, used_index, candidate_indexes



def register_face(employee_id: int) -> bool:
    os.makedirs(FACE_DATA_DIR, exist_ok=True)

    employees = get_all_employees()
    emp = next((e for e in employees if e[0] == employee_id), None)
    if not emp:
        print("❌ Employee not found")
        return False

    _, code, name, _ = emp

    cap, used_index, tried_indexes = _open_usable_camera()
    if cap is None:
        print(f"❌ Cannot open usable webcam. Tried indexes: {tried_indexes}")
        return False

    print(f"\n📸 Registering face for {name} (Code: {code}).")
    print(f"📷 Using webcam index: {used_index}")
    print("Press SPACE to capture. Press Q to quit/cancel.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ Failed to read frame")
                break

            boxes, embs = get_face_embedding(frame)

            # Draw live UI
            for (x1, y1, x2, y2) in boxes:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            cv2.putText(
                frame,
                f"{name}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("Face Registration", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                print("⚠️ Registration cancelled")
                return False

            if key == ord(" "):
                print("📸 SPACE pressed")


                # Validate: exactly 1 face must be in frame
                if len(boxes) != 1 or len(embs) != 1:
                    print(f"⚠️ Capture rejected. boxes={len(boxes)} embs={len(embs)}")
                    continue

                emb = embs[0]
                embedding_bytes = emb.astype("float32").tobytes()

                save_face_encoding(employee_id, embedding_bytes)

                # Save face image (crop)
                x1, y1, x2, y2 = boxes[0]
                face_img = frame[y1:y2, x1:x2]
                img_path = os.path.join(FACE_DATA_DIR, f"emp_{employee_id}_{code}.jpg")
                cv2.imwrite(img_path, face_img)
                print(f"✅ Face image saved: {img_path}")
                return True

    finally:
        cap.release()
        cv2.destroyAllWindows()

    return False


if __name__ == "__main__":
    list_employees()
    try:
        raw = input("\nEnter Employee ID to register face: ").strip()
        employee_id = int(raw)
    except Exception:
        print("❌ Invalid Employee ID")
        raise SystemExit(1)

    register_face(employee_id)


import time
import cv2


def suppress_opencv_logs():
    """Best-effort OpenCV log suppression for Windows.

    Some OpenCV builds (including with contrib) expose cv2.utils.logging.
    If not present, we silently ignore.
    """

    try:
        # OpenCV >= 4 has this
        if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
            # 0..3 (more verbose -> larger). Use 0 to reduce noise.
            cv2.utils.logging.setLogLevel(0)
    except Exception:
        pass


def _try_open_with_backend(index: int, backend: int, warmup_reads: int = 3):
    cap = cv2.VideoCapture(index, backend)
    if not cap or not cap.isOpened():
        try:
            cap.release()
        except Exception:
            pass
        return None

    # Warm-up: give the camera time to start streaming
    time.sleep(0.15)

    ok_any = False
    blackish = True
    last_frame = None

    for _ in range(warmup_reads):
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        ok_any = True
        last_frame = frame

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_val = float(gray.mean())
            if mean_val > 20:
                blackish = False
                break
        except Exception:
            # If conversion fails, don't treat it as proof of black frame.
            blackish = False
            break

    if ok_any and not blackish:
        return cap

    try:
        cap.release()
    except Exception:
        pass
    return None


def open_usable_camera(
    camera_index: int,
    candidate_indexes,
    backend_order=None,
    warmup_reads: int = 3,
):
    """Probe multiple indexes/backends and return the first usable cv2.VideoCapture.

    Returns:
        (cap, used_index, used_backend)
    """

    suppress_opencv_logs()

    if backend_order is None:
        backend_order = [
            # Windows friendly backends
            getattr(cv2, "CAP_MSMF", None),
            getattr(cv2, "CAP_DSHOW", None),
        ]
        backend_order = [b for b in backend_order if b is not None]

    # Ensure uniqueness + preserve order
    seen = set()
    candidate_indexes = [i for i in candidate_indexes if not (i in seen or seen.add(i))]

    for idx in candidate_indexes:
        for backend in backend_order:
            cap = _try_open_with_backend(idx, backend, warmup_reads=warmup_reads)
            if cap is not None:
                return cap, idx, backend

    return None, None, None


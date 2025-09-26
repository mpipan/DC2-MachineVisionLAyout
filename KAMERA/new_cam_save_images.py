import os, cv2, time
from datetime import datetime

# Your four capture nodes (main "index 0" ones)
CAMERAS = ["/dev/video0", "/dev/video2", "/dev/video4", "/dev/video6"]

# Preferred sizes in order (width, height)
PREF_SIZES = [(3840, 3104), (3840, 2160), (3264, 2448)]
OUTPUT_DIR = "camera_images_fullres"
WARMUP_FRAMES = 8

os.makedirs(OUTPUT_DIR, exist_ok=True)

def set_mjpg_and_size(cap, w, h):
    # Force MJPG (needed for high resolutions over USB)
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    # Optional: lower FPS to reduce bandwidth pressure
    cap.set(cv2.CAP_PROP_FPS, 5)
    # Optional: small buffer for fresh frames
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    time.sleep(0.05)
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return (aw == w and ah == h), aw, ah

for cam in CAMERAS:
    print(f"\nOpening {cam} ...")
    cap = cv2.VideoCapture(cam, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"? Could not open {cam}")
        continue

    applied = False
    aw = ah = None
    for (w, h) in PREF_SIZES:
        ok, aw, ah = set_mjpg_and_size(cap, w, h)
        if ok:
            applied = True
            break

    # If none matched exactly, well just use whatever the driver applied last
    if not applied:
        aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"?? Requested sizes not exact. Using {aw}x{ah} (MJPG).")
    else:
        print(f"? Using {aw}x{ah} (MJPG).")

    # Warm up for AE/AWB/exposure
    ret = False
    frame = None
    for _ in range(WARMUP_FRAMES):
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.02)

    if ret and frame is not None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        node = os.path.basename(cam)
        # Save PNG to avoid re-compressing an already JPEG-decoded frame
        out_path = os.path.join(OUTPUT_DIR, f"{node}_{aw}x{ah}_{ts}.png")
        ok = cv2.imwrite(out_path, frame)
        if ok:
            print(f"?? Saved {out_path}")
        else:
            print(f"? Failed to save image for {cam}")
    else:
        print(f"? Failed to capture a frame from {cam}")

    cap.release()

print("\nDone.")

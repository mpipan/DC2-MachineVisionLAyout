import cv2
import os
import logging
import time
import config
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _set_camera_properties(cap, preferred_sizes):
    """Tries to set the camera to the highest possible resolution using MJPG format."""
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    
    for w, h in preferred_sizes:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        time.sleep(0.1)
        
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if actual_w == w and actual_h == h:
            logger.info(f"Successfully set resolution to {w}x{h} (MJPG).")
            return True
            
    logger.warning(f"Could not set any preferred resolution. Using default: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    return False

# Capture one camera at a time (original method)
def capture_from_all_cameras():
    """
    Captures a single high-resolution frame from each of the 4 connected USB cameras.

    Returns:
        dict: A dictionary of images, with keys 'A', 'B', 'C', 'D'.
              Returns an empty dictionary if capture fails.
    """
    images = {}
    for camera_name, device_path in config.CAMERA_DEVICE_PATHS.items():
        logger.info(f"Opening camera '{camera_name}' at {device_path}...")
        cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
        
        if not cap.isOpened():
            logger.error(f"Cannot open camera {camera_name} at {device_path}.")
            continue

        try:
            _set_camera_properties(cap, config.PREFERRED_SIZES)

            for _ in range(config.WARMUP_FRAMES):
                cap.read()
                time.sleep(0.05)

            ret, frame = cap.read()

            if ret and frame is not None:
                images[camera_name] = frame
                save_path = os.path.join(config.CAPTURED_PATH, f'{camera_name}_raw.png')
                cv2.imwrite(save_path, frame)
                logger.info(f"Successfully captured image from camera {camera_name} and saved to {save_path}")
            else:
                logger.warning(f"Failed to retrieve frame from camera {camera_name}.")
        finally:
            cap.release()
            logger.info(f"Released camera {camera_name}.")

    if len(images) != 4:
        logger.error(f"Expected 4 images, but only captured {len(images)}. Please check camera connections.")
        return {}
        
    return images



# # Capture two cameras at a time to avoid USB bandwidth issues
# def capture_from_all_cameras():
#     """
#     Captures frames by running two cameras at a time to avoid USB bandwidth issues.
#     """
#     images = {}
#     lock = threading.Lock()

#     def capture_task(camera_name, device_path):
#         """The function that will be executed by each thread."""
#         logger.info(f"Starting capture for '{camera_name}' on new thread.")
#         cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
        
#         if not cap.isOpened():
#             logger.error(f"Cannot open camera {camera_name} at {device_path}.")
#             return

#         try:
#             _set_camera_properties(cap, config.PREFERRED_SIZES)
#             for _ in range(config.WARMUP_FRAMES):
#                 cap.read()
#             ret, frame = cap.read()

#             if ret and frame is not None:
#                 with lock:
#                     images[camera_name] = frame
#             else:
#                 logger.warning(f"Failed to retrieve frame from {camera_name}.")
#         finally:
#             cap.release()
#             logger.info(f"Released camera {camera_name}.")

#     # --- Capture in two batches ---
#     camera_list = list(config.CAMERA_DEVICE_PATHS.items())

#     # Batch 1: First two cameras
#     logger.info("--- Starting camera capture batch 1 (A & B) ---")
#     threads_batch1 = []
#     for camera_name, device_path in camera_list[:2]:
#         thread = threading.Thread(target=capture_task, args=(camera_name, device_path))
#         threads_batch1.append(thread)
#         thread.start()
#     for thread in threads_batch1:
#         thread.join()

#     # Batch 2: Last two cameras
#     logger.info("--- Starting camera capture batch 2 (C & D) ---")
#     threads_batch2 = []
#     for camera_name, device_path in camera_list[2:]:
#         thread = threading.Thread(target=capture_task, args=(camera_name, device_path))
#         threads_batch2.append(thread)
#         thread.start()
#     for thread in threads_batch2:
#         thread.join()

#     if len(images) != 4:
#         logger.error(f"Expected 4 images, but only captured {len(images)}.")
#         return {}
        
#     # Save the images after all are captured
#     for name, img in images.items():
#         save_path = os.path.join(config.CAPTURED_PATH, f'{name}_raw.png')
#         cv2.imwrite(save_path, img)
#         logger.info(f"Saved raw image from camera {name} to {save_path}")

#     return images



# def capture_from_all_cameras(): #Captures 4 images at once 
#     """
#     Captures a single frame from each camera concurrently using threads.
#     """
#     images = {}
#     threads = []
#     lock = threading.Lock() # To safely write to the shared `images` dictionary

#     def capture_task(camera_name, device_path):
#         logger.info(f"Starting capture for '{camera_name}' on new thread.")
#         cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
        
#         if not cap.isOpened():
#             logger.error(f"Cannot open camera {camera_name} at {device_path}.")
#             return

#         try:
#             _set_camera_properties(cap, config.PREFERRED_SIZES)
#             for _ in range(config.WARMUP_FRAMES):
#                 cap.read()
#             ret, frame = cap.read()

#             if ret and frame is not None:
#                 with lock:
#                     images[camera_name] = frame
#                 # Saving the raw image can be done here or later
#             else:
#                 logger.warning(f"Failed to retrieve frame from {camera_name}.")
#         finally:
#             cap.release()
#             logger.info(f"Released camera {camera_name}.")

#     for camera_name, device_path in config.CAMERA_DEVICE_PATHS.items():
#         thread = threading.Thread(target=capture_task, args=(camera_name, device_path))
#         threads.append(thread)
#         thread.start()

#     for thread in threads:
#         thread.join() # Wait for all capture threads to finish

#     if len(images) != 4:
#         logger.error(f"Expected 4 images, but only captured {len(images)}.")
#         return {}
        
#     # Now save the images after all are captured
#     for name, img in images.items():
#         save_path = os.path.join(config.CAPTURED_PATH, f'{name}_raw.png')
#         cv2.imwrite(save_path, img)
#         logger.info(f"Saved raw image from camera {name} to {save_path}")

#     return images

if __name__ == "__main__":
    """Standalone test for the master's cameras."""
    logger.info("Running master camera_utils.py standalone for testing...")
    
    if not os.path.exists(config.CAPTURED_PATH):
        os.makedirs(config.CAPTURED_PATH)

    captured_images = capture_from_all_cameras()

    if captured_images:
        logger.info(f"Successfully captured {len(captured_images)} images from master.")
    else:
        logger.error("Failed to capture images from master. Check logs.")

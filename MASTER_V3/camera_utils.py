import cv2
import os
import logging
import time
import config

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

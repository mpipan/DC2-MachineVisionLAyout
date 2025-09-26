import cv2
import logging
import time
import os

import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _set_camera_properties(cap, preferred_sizes):
    """Tries to set the camera to the highest possible resolution using MJPG format."""
    # Force MJPG format, which is necessary for high resolutions over USB 2.0
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    
    for w, h in preferred_sizes:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        time.sleep(0.1) # Allow time for the setting to apply
        
        # Verify if the setting was accepted
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if actual_w == w and actual_h == h:
            logger.info(f"Successfully set resolution to {w}x{h} (MJPG).")
            return True
            
    logger.warning(f"Could not set any preferred resolution. Using default: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    return False

def capture_image_from(camera_name):
    """
    Captures a single high-resolution frame from a specified USB camera.

    Args:
        camera_name (str): The logical name of the camera ('A', 'B', 'C', or 'D').

    Returns:
        numpy.ndarray: The captured image, or None if capture fails.
    """
    device_path = config.CAMERA_DEVICE_PATHS.get(camera_name)
    if not device_path:
        logger.error(f"Invalid camera name: {camera_name}. Not found in config.")
        return None

    logger.info(f"Opening camera '{camera_name}' at {device_path}...")
    cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
    if not cap.isOpened():
        logger.error(f"Could not open camera {device_path}")
        return None

    try:
        # Set the best possible resolution
        _set_camera_properties(cap, config.PREFERRED_SIZES)

        # "Warm up" the camera to allow auto-exposure and auto-white-balance to adjust
        for _ in range(config.WARMUP_FRAMES):
            cap.read()
            time.sleep(0.05)

        # Read the final, adjusted frame
        ret, frame = cap.read()

        if ret and frame is not None:
            save_path = os.path.join(config.OUTPUT_PATH, f'{camera_name}_raw.png')
            cv2.imwrite(save_path, frame)
            logger.info(f"Successfully captured frame from {camera_name} and saved to {save_path}.")
            return frame
        else:
            logger.error(f"Failed to capture a valid frame from {camera_name}.")
            return None

    finally:
        # Always release the camera
        cap.release()
        logger.info(f"Released camera {camera_name}.")

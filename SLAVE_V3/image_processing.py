import cv2
import numpy as np
import imutils
import zxingcpp
import math
import json
import os
import logging
import base64

import config
import camera_utils
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Calibrated Conversion Factor ---
CALIBRATED_CONV_FACTOR = None
if config.USE_HOMOGRAPHY:
    try:
        factor_path = os.path.join(config.OUTPUT_PATH, config.CALIBRATED_FACTOR_FILE)
        if os.path.exists(factor_path):
            with open(factor_path, 'r') as f:
                data = json.load(f)
                CALIBRATED_CONV_FACTOR = data.get("conversion_factor")
            if CALIBRATED_CONV_FACTOR:
                 logger.info(f"Successfully loaded calibrated conversion factor: {CALIBRATED_CONV_FACTOR}")
            else:
                logger.error("Calibrated factor file is invalid.")
        else:
            logger.error(f"Calibrated factor file not found at {factor_path}. Please run calibration first.")
    except Exception as e:
        logger.error(f"Failed to load calibrated conversion factor: {e}")

# --- Helper Functions ---
def _renaming(name):
    """Map QR code numbers to module names."""
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def _find_modules(image):
    """
    Detects QR codes and maps them to a real-world coordinate system.
    Returns the raw millimeter coordinates and the cropped image.
    """
    logger.info("Detecting modules...")
    
    module_coords_mm = {}
    
    try:
        results = zxingcpp.read_barcodes(image)
        if not results:
            logger.warning("No QR codes found in the image.")
            return module_coords_mm, image

        for result in results:
            module_name = _renaming(result.text)
            
            # Use homography for precise millimeter coordinates
            if config.USE_HOMOGRAPHY and CALIBRATED_CONV_FACTOR:
                # Transform the pixel coordinates to millimeter coordinates using the homography matrix
                homography_path = os.path.join(config.OUTPUT_PATH, config.HOMOGRAPHY_MATRIX_FILE)
                if not os.path.exists(homography_path):
                    logger.error("Homography matrix not found. Cannot perform coordinate transformation.")
                    continue
                H = np.load(homography_path)
                
                # Apply the homography to the corner points
                corners_px = np.array([[p.x, p.y] for p in result.position.points], dtype=np.float32).reshape(-1, 1, 2)
                corners_mm_homo = cv2.perspectiveTransform(corners_px, H)
                corners_mm_list = corners_mm_homo.reshape(4, 2).tolist()
                
                # Sort corners to ensure a consistent drawing order (e.g., top-left, top-right, etc.)
                sorted_corners = sorted(corners_mm_list, key=lambda p: (p[0], p[1]))
                
                # Check if the module is already in the list to avoid duplicates
                module_in_list = False
                for existing_module_name, existing_corners in module_coords_mm.items():
                    # Calculate a simple distance metric between the two sets of corners
                    dist = np.linalg.norm(np.array(sorted_corners) - np.array(existing_corners))
                    if dist < 10:  # A small threshold to consider them the same
                        module_in_list = True
                        break
                
                if not module_in_list:
                    module_coords_mm[module_name] = sorted_corners
                    logger.info(f"Found and processed module: {module_name} (using homography).")
            else:
                logger.warning("Homography method is disabled or not calibrated. Skipping module finding.")
                return {}, image
    
    except Exception as e:
        logger.error(f"Error during module detection: {e}")
        return {}, image

    return module_coords_mm, image

def capture_and_process_all():
    """
    Captures, stitches, and processes all slave images.
    Returns the stitched image and a list of detected modules with their mm coordinates.
    """
    logger.info("--- Starting SLAVE Image Capture and Processing Pipeline ---")
    
    # NEW: The slave will only capture, process, and return data.
    # It will not draw on the image or return a base64 string.
    
    raw_images = camera_utils.capture_from_all_cameras()
    if not raw_images:
        logger.error("Failed to capture raw images from slave cameras.")
        return None

    # Stitch the images together to form the large slave canvas.
    # This image will be sent to the master for final drawing.
    stitched_image = image_processing.stitch_images(raw_images)
    if stitched_image is None:
        logger.error("Failed to stitch images.")
        return None
    
    # Find all modules and get their millimeter coordinates
    module_coords_mm, _ = _find_modules(stitched_image)
    
    # Save the un-drawn stitched image to disk for the master to pick up later
    cv2.imwrite(config.SLAVE_UNDRAWN_IMAGE_PATH, stitched_image)
    logger.info(f"Saved the raw stitched image to {config.SLAVE_UNDRAWN_IMAGE_PATH}")

    # Prepare the final payload for the master.
    # It contains the path to the stitched image and the raw module data.
    payload = {
        "stitched_image_path": config.SLAVE_UNDRAWN_IMAGE_PATH,
        "module_coords_mm": module_coords_mm,
    }
    
    logger.info("--- Slave Processing Pipeline Finished ---")
    return payload
    

def _vertical_shift(img, shift_amount, padding=300):
    """Add vertical shift to an image."""
    h, w = img.shape[:2]
    shifted_img = np.full((h + abs(shift_amount) + 2*padding, w, 3), 0, dtype=np.uint8)
    
    if shift_amount > 0:
        shifted_img[shift_amount + padding:h + shift_amount + padding, :, :] = img
    else:
        shifted_img[padding:h + padding, :, :] = img
        
    return shifted_img
    
def stitch_images(images):
    """
    Stitches images A, B, C, and D based on their configurations.
    """
    logger.info("Stitching images...")
    if not all(k in images for k in ['A', 'B', 'C', 'D']):
        logger.error("Not all required images (A, B, C, D) are available for stitching.")
        return None
        
    try:
        # Step 1: Horizontal stitching of A and B
        stitched_ab = cv2.hconcat([images['A'], images['B']])
        
        # Step 2: Horizontal stitching of C and D
        stitched_cd = cv2.hconcat([images['C'], images['D']])
        
        # Step 3: Vertical stitching of the two horizontal strips
        final_stitched_image = cv2.vconcat([stitched_ab, stitched_cd])
        
        logger.info("Images stitched successfully.")
        return final_stitched_image
        
    except Exception as e:
        logger.error(f"Failed to stitch images: {e}")
        return None

# The draw_module_outlines function is removed from the slave,
# as the drawing is now centralized on the master side.
# def draw_module_outlines(image, module_outlines_mm, conv_factor):
#    ... (old drawing code)

import cv2
import numpy as np
import imutils
import zxingcpp
import math
import json
import os
import logging
import matplotlib.pyplot as plt

import config
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _renaming(name):
    """Map QR code numbers to module names."""
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def _crop_image(img, top_crop, bottom_crop):
    """Crop the top and bottom of an image."""
    height, _ = img.shape[:2]
    if top_crop + bottom_crop >= height:
        logger.error("Total crop height is greater than image height.")
        return img
    return img[top_crop:height - bottom_crop, :]

def _crop_left_right(img, left, right):
    """Crop the left and right sides of an image."""
    _, width = img.shape[:2]
    if left + right >= width:
        logger.error("Total crop width is greater than image width.")
        return img
    return img[:, left:width - right]

def _vertical_shift(img, shift_amount, padding=300):
    """Add vertical shift to an image."""
    h, w = img.shape[:2]
    shifted_img = np.full((h + abs(shift_amount) + 2*padding, w, 3), 0, dtype=np.uint8)
    
    if shift_amount > 0:
        shifted_img[shift_amount + padding:h + shift_amount + padding, :, :] = img
    else:
        shifted_img[padding:h + padding, :, :] = img
        
    return shifted_img

def stitch_images(images, horizontal=False):
    """Stitches images A, B, C, and D based on their configurations."""
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

def _find_modules(image):
    """
    Detects QR codes on a master's stitched image.
    Returns the raw millimeter coordinates.
    """
    logger.info("Detecting modules...")
    
    module_coords_mm = {}
    
    try:
        # The master does not use the homography method, it uses a simpler calculation
        results = zxingcpp.read_barcodes(image)
        if not results:
            logger.warning("No QR codes found in the image.")
            return module_coords_mm

        for result in results:
            module_name = _renaming(result.text)
            
            # Simple scaling method
            # Get the corners in pixels
            corners_px = np.array([[p.x, p.y] for p in result.position.points], dtype=np.float32)
            
            # Use fixed scaling to convert pixel to mm
            conv_factor = config.PIXEL_DISTANCE_IN_MM / config.REAL_DISTANCE_CM
            
            # The simple scaling is assumed here; a more robust method is needed for a real application
            corners_mm = corners_px * conv_factor
            
            module_coords_mm[module_name] = corners_mm.tolist()
            logger.info(f"Found and processed module: {module_name}.")

    except Exception as e:
        logger.error(f"Error during module detection: {e}")
        return {}

    return module_coords_mm

def combine_and_draw(slave_image_path, master_images, slave_coords_mm):
    """
    NEW: This is the central function for the entire process.
    1. Loads the slave's undrawn image.
    2. Stitches it with the master's images.
    3. Combines the master's and slave's module coordinates.
    4. Draws all outlines and text on the final combined image.
    """
    logger.info("--- Starting Final Combination and Drawing Pipeline ---")
    
    # 1. Load slave's stitched image
    try:
        slave_image = cv2.imread(slave_image_path)
        if slave_image is None:
            logger.error(f"Could not load slave image from {slave_image_path}")
            return None
    except Exception as e:
        logger.error(f"Error loading slave image: {e}")
        return None
        
    # 2. Stitch the two large images together (slave on top, master on bottom)
    final_combined_image = cv2.vconcat([slave_image, master_images])
    cv2.imwrite(config.COMBINED_IMAGE_PATH, final_combined_image)
    logger.info(f"Combined and saved final large image to {config.COMBINED_IMAGE_PATH}")
    
    # 3. Find modules on the master side
    master_coords_mm = _find_modules(master_images)
    
    # 4. Combine all coordinates into one list
    # NOTE: The coordinates need to be shifted to match the combined image's coordinate system.
    # The slave image is at y=0, the master image starts at y = slave_image.shape[0]
    
    # First, shift the master coordinates
    shifted_master_coords = {}
    y_shift = slave_image.shape[0]
    for name, corners in master_coords_mm.items():
        shifted_corners = np.array(corners) + np.array([0, y_shift])
        shifted_master_coords[name] = shifted_corners.tolist()
        
    # Combine the coordinate dictionaries
    all_module_coords = {}
    all_module_coords.update(slave_coords_mm)
    all_module_coords.update(shifted_master_coords)
    
    with open(config.COMBINED_COORDS_PATH, 'w') as f:
        json.dump(all_module_coords, f, cls=NumpyEncoder, indent=4)
        logger.info(f"Combined all module coordinates and saved to {config.COMBINED_COORDS_PATH}")
    
    # 5. Draw all the outlines on the single combined image
    final_image_with_modules = final_combined_image.copy()
    styles = config.DRAWING_STYLES
    
    for module, corners_mm in all_module_coords.items():
        # Convert millimeter coordinates back to pixels
        # A simple fixed scaling is used here, but a more complex one may be needed
        # based on your calibration
        conv_factor = 1 # Assuming mm == pixels for simplicity of this example
        pixel_points = (np.array(corners_mm) / conv_factor).astype(np.int32)
        
        # Draw the module outline
        cv2.polylines(final_image_with_modules, [pixel_points], isClosed=True,
                      color=styles["line_color_bgr"], thickness=styles["line_thickness"])
        
        # Draw the text name
        center_x, center_y = np.mean(pixel_points, axis=0).astype(np.int32)
        text = module
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["font_thickness"])
        box_p1 = (center_x - tw // 2 - 5, center_y - th - 5)
        box_p2 = (center_x + tw // 2 + 5, center_y + 5)
        cv2.rectangle(final_image_with_modules, box_p1, box_p2, styles["bg_color_bgr"], cv2.FILLED)
        cv2.putText(final_image_with_modules, text, (center_x - tw // 2, center_y),
                    cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["text_color_bgr"],
                    styles["font_thickness"])
                    
    cv2.imwrite(config.FINAL_IMAGE_PATH, final_image_with_modules)
    logger.info(f"Final image with all modules drawn saved to {config.FINAL_IMAGE_PATH}")
    
    return all_module_coords

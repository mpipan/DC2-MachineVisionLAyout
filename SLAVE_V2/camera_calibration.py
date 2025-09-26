import cv2
import numpy as np
import os
import logging
import json

import config
import camera_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_camera_calibration():
    """
    Performs camera calibration. It finds a checkerboard to calculate a homography
    matrix and then uses that matrix to derive and save a highly accurate
    pixel-to-millimeter conversion factor.
    """
    camera_name = config.CALIBRATION_CAMERA_NAME
    logger.info(f"--- Starting Camera Calibration Process for Camera '{camera_name}' ---")
    
    input_image = camera_utils.capture_image_from(camera_name)
    if input_image is None:
        logger.error("Failed to capture image for calibration. Aborting.")
        return

    gray_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    ret, corners = cv2.findChessboardCorners(gray_image, config.CHECKERBOARD_DIMENSIONS, None)
    
    if ret:
        logger.info("Checkerboard corners found successfully!")
        corners_subpix = cv2.cornerSubPix(gray_image, corners, (11, 11), (-1, -1), criteria)
        
        objp = np.zeros((config.CHECKERBOARD_DIMENSIONS[0] * config.CHECKERBOARD_DIMENSIONS[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:config.CHECKERBOARD_DIMENSIONS[1], 0:config.CHECKERBOARD_DIMENSIONS[0]].T.reshape(-1, 2)
        objp *= config.SQUARE_SIZE_MM
        
        H, _ = cv2.findHomography(corners_subpix, objp[:, :2], cv2.RANSAC, 5.0)
        if H is None:
            logger.error("Failed to calculate homography matrix. Aborting.")
            return

        logger.info(f"Calculated Homography Matrix (H):\n{H}")
        
        # --- NEW: Calculate and save the conversion factor ---
        logger.info("Deriving conversion factor using the homography matrix for accuracy...")

        # Define two adjacent corners in the source pixel space (e.g., the first two corners found)
        # Note the required shape for perspectiveTransform: (1, N, 2) and float32 type
        p1_px = np.array([[corners_subpix[0].ravel()]], dtype=np.float32)
        p2_px = np.array([[corners_subpix[1].ravel()]], dtype=np.float32)

        # Use the homography matrix H to transform these pixel points to real-world mm points
        p1_mm = cv2.perspectiveTransform(p1_px, H)
        p2_mm = cv2.perspectiveTransform(p2_px, H)

        # Calculate the distance between the two points in both coordinate systems
        dist_in_pixels = np.linalg.norm(p1_px - p2_px)
        dist_in_mm = np.linalg.norm(p1_mm - p2_mm)

        # The conversion factor is the ratio of these two distances (mm / pixel)
        if dist_in_pixels == 0:
            logger.error("Pixel distance is zero, cannot calculate conversion factor. Aborting.")
            return

        conversion_factor = float(dist_in_mm / dist_in_pixels)
        logger.info(f"Derived accurate conversion factor: {conversion_factor:.6f} mm/pixel")
        
        factor_data = {"conversion_factor": conversion_factor}
        factor_path = os.path.join(config.OUTPUT_PATH, config.CALIBRATED_FACTOR_FILE)
        with open(factor_path, 'w') as f:
            json.dump(factor_data, f, indent=4)
        logger.info(f"Accurate conversion factor saved to {factor_path}")

        # Save the homography matrix and check image as before
        homography_path = os.path.join(config.OUTPUT_PATH, config.HOMOGRAPHY_MATRIX_FILE)
        np.save(homography_path, H)
        logger.info(f"Homography matrix saved to {homography_path}")
        
        image_with_corners = cv2.drawChessboardCorners(input_image.copy(), config.CHECKERBOARD_DIMENSIONS, corners_subpix, ret)
        output_path = os.path.join(config.OUTPUT_PATH, 'calibration_corners_check.jpg')
        cv2.imwrite(output_path, image_with_corners)
        logger.info(f"Image with drawn corners saved to {output_path} for verification.")

    else:
        logger.error("Failed to find checkerboard corners.")

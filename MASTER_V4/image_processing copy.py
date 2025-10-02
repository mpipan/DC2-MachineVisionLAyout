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
from utils import NumpyEncoder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Calibrated Conversion Factor (from master's calibration) ---
CALIBRATED_CONV_FACTOR = None
if config.USE_HOMOGRAPHY:
    try:
        factor_path = os.path.join(config.CAPTURED_PATH, config.CALIBRATED_FACTOR_FILE)
        if os.path.exists(factor_path):
            with open(factor_path, 'r') as f:
                data = json.load(f)
                CALIBRATED_CONV_FACTOR = data.get("conversion_factor")
            if CALIBRATED_CONV_FACTOR:
                 logger.info(f"Successfully loaded master's calibrated conversion factor: {CALIBRATED_CONV_FACTOR}")
            else:
                logger.error("Master's calibrated factor file is invalid.")
        else:
            logger.error(f"Master's calibrated factor file not found at {factor_path}. Please run calibration on master first.")
    except Exception as e:
        logger.error(f"Failed to load master's calibrated conversion factor: {e}")

# --- Internal Helper Functions (Mirrored from Slave) ---
def _renaming(name):
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# --- Core Processing Functions for Master (Adapted from Slave) ---
def process_master_images(raw_images):
    """
    Main function to process the 4 raw images from the master cameras.
    This logic is now standardized with the slave's processing pipeline.
    """
    logger.info("--- Starting master image processing stage ---")
    prepared_images = {}
    
    # 1. Rotate, angle, shift, and crop each raw image
    for name, raw_img in raw_images.items():
        rotated = cv2.rotate(raw_img, config.CAMERA_ROTATIONS[name])
        angled = imutils.rotate(rotated, angle=config.ADJUSTMENTS[name]['angle'])
        vp = config.ADJUSTMENTS[name]['vp']
        padding = 300
        height, width = angled.shape[:2]
        total_height = 2 * padding + height
        canvas = np.ones((total_height, width, 3), dtype=np.uint8) * 255
        canvas[padding:padding + height, :] = angled
        shifted = np.roll(canvas, -int(vp), axis=0)
        prepared_images[name] = shifted[config.MASTER_TOP_CROP : shifted.shape[0] - config.MASTER_BOTTOM_CROP, :]

    # 2. Stitch the prepared images into a single plain image
    stitched_image_plain = _stitch_images(prepared_images)
    cv2.imwrite(config.MASTER_IMAGE_PATH, stitched_image_plain)
    logger.info("Step 1/5: Master images stitched together.")

    # 3. Detect QR codes and get their pixel coordinates in the stitched image
    pixel_coords = _get_adjusted_coordinates(prepared_images)
    with open(config.MASTER_COORDS_PIXEL_PATH, "w") as f: json.dump(pixel_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 2/5: Pixel coordinates of QR codes extracted.")

    # 4. Calculate module outlines using the conversion factor
    module_outline_coords, conv_factor = _scale_module_outlines(pixel_coords)
    if not module_outline_coords:
        logger.error("Failed to calculate module outlines for master. Aborting.")
        return False
    with open(config.MASTER_COORDS_SCALED_PATH, "w") as f: json.dump(module_outline_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 3/5: Module outline coordinates calculated in mm.")

    # 5. Draw the calculated modules on the stitched image
    stitched_image_with_modules = _draw_modules_on_image(stitched_image_plain, module_outline_coords, conv_factor, config.MASTER_IMAGE_WITH_MODULES_PATH)
    if stitched_image_with_modules is None: return False
    logger.info("Step 4/5: Visualization image created for master.")

    # 6. Apply final positional shifts for the coordinate system
    final_shifted_coords = {
        name: [[p[0] + config.FINAL_X_SHIFT, p[1] + config.FINAL_Y_SHIFT] for p in coords]
        for name, coords in module_outline_coords.items()
    }
    with open(config.MASTER_COORDS_FINAL_SHIFTED_PATH, "w") as f: json.dump(final_shifted_coords, f, indent=4, cls=NumpyEncoder)
    
    logger.info("Step 5/5: Master processing stage complete. All files saved.")
    return True

# --- Helper Functions for Processing (Mirrored from Slave) ---
def _stitch_images(images):
    cropped_parts = []
    for name, img in images.items():
        left_crop = config.ADJUSTMENTS[name]['l']
        right_crop = config.ADJUSTMENTS[name]['d']
        cropped_parts.append(img[:, left_crop : img.shape[1] - right_crop])
    return cv2.hconcat(cropped_parts)

def _decode_qr_codes(image):
    if image is None: return {}
    barcodes = zxingcpp.read_barcodes(image)
    positions = {}
    for barcode in barcodes:
        text = _renaming(str(barcode.text))
        if text != 'Unknown':
            pos_str = str(barcode.position).strip('\x00')
            pairs = pos_str.split()
            positions[text] = [np.array([int(p.split('x')[0]), int(p.split('x')[1])]) for p in pairs]
    return positions

def _get_adjusted_coordinates(images):
    w1 = images['A'].shape[1] - config.ADJUSTMENTS['A']['l'] - config.ADJUSTMENTS['A']['d']
    w2 = images['B'].shape[1] - config.ADJUSTMENTS['B']['l'] - config.ADJUSTMENTS['B']['d']
    w3 = images['C'].shape[1] - config.ADJUSTMENTS['C']['l'] - config.ADJUSTMENTS['C']['d']
    codes = {name: _decode_qr_codes(img) for name, img in images.items()}
    output = {}
    h = images['A'].shape[0] # Assume all images have the same height after processing
    if codes.get('A'):
        output.update({k: [np.array([p[0] - config.ADJUSTMENTS['A']['l'], h - p[1]]) for p in v] for k, v in codes['A'].items()})
    if codes.get('B'):
        offset = w1
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['B']['l'], h - p[1]]) for p in v] for k, v in codes['B'].items()})
    if codes.get('C'):
        offset = w1 + w2
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['C']['l'], h - p[1]]) for p in v] for k, v in codes['C'].items()})
    if codes.get('D'):
        offset = w1 + w2 + w3
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['D']['l'], h - p[1]]) for p in v] for k, v in codes['D'].items()})
    return output

def _scale_module_outlines(qr_coords_pixels):
    conv_factor = None
    if config.USE_HOMOGRAPHY and CALIBRATED_CONV_FACTOR is not None:
        logger.info("Using master's calibrated conversion factor for scaling.")
        conv_factor = CALIBRATED_CONV_FACTOR
    else:
        logger.warning("Using QR-based conversion factor for scaling on master.")
        lengths = [_calculate_distance(c[i], c[(i + 1) % 4]) for c in qr_coords_pixels.values() for i in range(4)]
        conv_factor = config.QR_CODE_REAL_SIZE_MM / (sum(lengths) / len(lengths)) if lengths else 0.065

    module_outlines_mm = {}
    for module, qr_corners in qr_coords_pixels.items():
        if module not in config.MODULE_DIMENSIONS: continue
        mod_height_mm, mod_width_mm = config.MODULE_DIMENSIONS[module]
        t1, t2, _, t4 = qr_corners
        v_top_px, v_left_px = t2 - t1, t4 - t1
        norm_top, norm_left = np.linalg.norm(v_top_px), np.linalg.norm(v_left_px)
        if norm_top == 0 or norm_left == 0: continue
        u_top, u_left = v_top_px / norm_top, v_left_px / norm_left
        v_module_width, v_module_height = u_top * (mod_width_mm / conv_factor), u_left * (mod_height_mm / conv_factor)
        c1, c2, c4, c3 = t1, t1 + v_module_width, t1 + v_module_height, t1 + v_module_width + v_module_height
        module_outlines_mm[module] = [c * conv_factor for c in [c1, c2, c3, c4]]
        
    return module_outlines_mm, conv_factor

def _draw_modules_on_image(image, module_outlines_mm, conv_factor, output_path):
    try:
        canvas = image.copy()
        styles = config.DRAWING_STYLES
        for module, corners_mm in module_outlines_mm.items():
            pixel_points = (np.array(corners_mm) / conv_factor).astype(np.int32)
            pixel_points[:, 1] = canvas.shape[0] - pixel_points[:, 1]
            cv2.polylines(canvas, [pixel_points], isClosed=True, color=styles["line_color_bgr"], thickness=styles["line_thickness"])
            center_x, center_y = np.mean(pixel_points, axis=0).astype(np.int32)
            (tw, th), _ = cv2.getTextSize(module, cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["font_thickness"])
            box_p1 = (center_x - tw // 2 - 5, center_y - th - 5)
            box_p2 = (center_x + tw // 2 + 5, center_y + 5)
            cv2.rectangle(canvas, box_p1, box_p2, styles["bg_color_bgr"], cv2.FILLED)
            cv2.putText(canvas, module, (center_x - tw // 2, center_y), cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["text_color_bgr"], styles["font_thickness"], cv2.LINE_AA)
        cv2.imwrite(output_path, canvas)
        logger.info(f"High-quality visualization saved to {output_path}")
        return canvas
    except Exception as e:
        logger.error(f"An error occurred in _draw_modules_on_image: {e}")
        return None

# --- Combination and Finalization Functions ---

def combine_master_slave_coordinates():
    logger.info("Combining master and slave coordinates...")
    combined_data = {}
    try:
        if os.path.exists(config.SLAVE_COORDS_PATH):
            with open(config.SLAVE_COORDS_PATH, "r") as f: combined_data.update(json.load(f))
        
        if os.path.exists(config.MASTER_COORDS_FINAL_SHIFTED_PATH):
            with open(config.MASTER_COORDS_FINAL_SHIFTED_PATH, "r") as f: combined_data.update(json.load(f))

        with open(config.COMBINED_COORDS_PATH, "w") as f: json.dump(combined_data, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved combined coordinates to {config.COMBINED_COORDS_PATH}")

        converted_data = {name: [sum(p[0] for p in c) / 4, sum(p[1] for p in c) / 4, math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0]))] for name, c in combined_data.items() if isinstance(c, list) and len(c) == 4}
        with open(config.COMBINED_CONVERTED_COORDS_PATH, "w") as f: json.dump(converted_data, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved converted center+rotation data to {config.COMBINED_CONVERTED_COORDS_PATH}")

    except Exception as e:
        logger.error(f"Failed to combine coordinates: {e}")

def join_master_slave_images():
    logger.info("Joining master and slave images...")
    try:
        top_img = cv2.imread(config.SLAVE_IMAGE_WITH_MODULES_PATH)
        bottom_img = cv2.imread(config.MASTER_IMAGE_WITH_MODULES_PATH)

        if top_img is None or bottom_img is None:
            logger.error("Could not load one or both images for joining. Check paths.")
            return

        p = config.JOIN
        
        # Determine the final canvas size without pre-cropping the images
        common_width = max(top_img.shape[1] + p['top_horizontal_shift'], bottom_img.shape[1] + p['bottom_horizontal_shift'])
        
        top_canvas = np.full((top_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)
        bottom_canvas = np.full((bottom_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)

        # Place images on their respective canvases with horizontal shifts
        top_canvas[:, p['top_horizontal_shift']:p['top_horizontal_shift'] + top_img.shape[1]] = top_img
        bottom_canvas[:, p['bottom_horizontal_shift']:p['bottom_horizontal_shift'] + bottom_img.shape[1]] = bottom_img
        
        # NOW apply vertical cropping to the canvases
        top_canvas_cropped = top_canvas[p['top_top_crop'] : top_canvas.shape[0] - p['top_bottom_crop'], :]
        bottom_canvas_cropped = bottom_canvas[p['bottom_top_crop'] : bottom_canvas.shape[0] - p['bottom_bottom_crop'], :]
        
        # Vertically stack the final, prepared canvases
        combined_image = np.vstack((top_canvas_cropped, bottom_canvas_cropped))
        cv2.imwrite(config.COMBINED_IMAGE_PATH, combined_image)
        logger.info(f"Saved final combined image to {config.COMBINED_IMAGE_PATH}")

        # Resize for upload
        h, w = combined_image.shape[:2]
        resized_image = cv2.resize(combined_image, (800, int(h * (800 / w))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(config.COMBINED_IMAGE_RESIZED_PATH, resized_image)
        logger.info(f"Saved resized image for upload to {config.COMBINED_IMAGE_RESIZED_PATH}")

    except Exception as e:
        logger.error(f"Failed to join images: {e}")

def convert_final_coords_to_cm():
    logger.info("Converting final coordinates to cm...")
    try:
        with open(config.COMBINED_CONVERTED_COORDS_PATH, 'r') as f: data = json.load(f)
        pixel_dist = abs(config.PIXEL_POINT_1 - config.PIXEL_POINT_2)
        if pixel_dist == 0:
            logger.error("Pixel distance for scaling cannot be zero.")
            return
        cm_per_pixel = config.REAL_DISTANCE_CM / pixel_dist
        converted_data = {k: [v[0] * cm_per_pixel, v[1] * cm_per_pixel, v[2]] for k, v in data.items()}
        with open(config.COORDS_IN_CM_PATH, 'w') as f: json.dump(converted_data, f, indent=4)
        logger.info(f"Converted coordinates to cm and saved to {config.COORDS_IN_CM_PATH}")
    except Exception as e:
        logger.error(f"Failed to convert coordinates to cm: {e}")

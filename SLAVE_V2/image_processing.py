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

# --- Load Calibrated Conversion Factor (only if needed) ---
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

# --- Internal Helper Functions ---
def _renaming(name):
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# --- Core Processing Functions ---

def capture_and_prepare_images():
    """STAGE 1: Captures and prepares raw images from all 4 cameras."""
    images = {}
    for name in config.CAMERA_DEVICE_PATHS.keys():
        raw_img = camera_utils.capture_image_from(name)
        if raw_img is None:
            logger.error(f"Failed to get raw image from camera {name}. Aborting.")
            return None
        images[name] = raw_img
    return images

def process_and_save_images(raw_images):
    """STAGE 2: Takes raw images, processes them, and saves all final outputs."""
    logger.info("--- Starting image processing stage ---")
    prepared_images = {}
    
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
        prepared_images[name] = shifted[config.TOP_CROP : shifted.shape[0] - config.BOTTOM_CROP, :]

    stitched_image_plain = _stitch_images(prepared_images)
    cv2.imwrite(os.path.join(config.OUTPUT_PATH, 'stitched_plain.jpg'), stitched_image_plain)
    logger.info("Step 2/6: Images stitched together.")

    pixel_coords = _get_adjusted_coordinates(prepared_images)
    with open(os.path.join(config.OUTPUT_PATH, 'coords_pixel.json'), "w") as f: json.dump(pixel_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 3/6: Pixel coordinates of QR codes extracted.")

    module_outline_coords, conv_factor = _scale_module_outlines(pixel_coords)
    if not module_outline_coords:
        logger.error("Failed to calculate module outlines. Aborting.")
        return False

    with open(os.path.join(config.OUTPUT_PATH, 'coords_scaled.json'), "w") as f: json.dump(module_outline_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 4/6: Module outline coordinates calculated in mm.")

    viz_path = os.path.join(config.OUTPUT_PATH, 'stitched_with_modules.jpg')
    stitched_image_with_modules = _draw_modules_on_image(stitched_image_plain, module_outline_coords, conv_factor, viz_path)
    if stitched_image_with_modules is None: return False
    logger.info("Step 5/6: Visualization image created.")

    final_shifted_coords = {
        name: [[p[0] + config.FINAL_X_SHIFT, p[1] + config.FINAL_Y_SHIFT] for p in coords]
        for name, coords in module_outline_coords.items()
    }
    with open(os.path.join(config.OUTPUT_PATH, 'coords_final_shifted.json'), "w") as f: json.dump(final_shifted_coords, f, indent=4, cls=NumpyEncoder)
    
    logger.info("Processing stage complete. All files saved.")
    return True

def capture_and_process_all():
    """The main orchestrator function that runs both stages."""
    logger.info("--- Starting full capture and processing sequence ---")
    raw_images = capture_and_prepare_images()
    if not raw_images: return None
    logger.info("Step 1/6: All images captured.")

    if not process_and_save_images(raw_images): return None

    stitched_image_plain = cv2.imread(os.path.join(config.OUTPUT_PATH, 'stitched_plain.jpg'))
    stitched_image_with_modules = cv2.imread(os.path.join(config.OUTPUT_PATH, 'stitched_with_modules.jpg'))
    with open(os.path.join(config.OUTPUT_PATH, 'coords_pixel.json'), "r") as f: pixel_coords = json.load(f)
    with open(os.path.join(config.OUTPUT_PATH, 'coords_scaled.json'), "r") as f: scaled_coords = json.load(f)
    with open(os.path.join(config.OUTPUT_PATH, 'coords_final_shifted.json'), "r") as f: final_shifted_coords = json.load(f)

    _, plain_buf = cv2.imencode('.jpg', stitched_image_plain)
    _, modules_buf = cv2.imencode('.jpg', stitched_image_with_modules)
    
    payload = {
        'koordinate': pixel_coords, 'koordinate_skalirane': scaled_coords,
        'koordinate_skalirane_dvignjene': final_shifted_coords,
        'zdruzena_brez_nic': base64.b64encode(plain_buf).decode('utf-8'),
        'rezultat_z_moduli': base64.b64encode(modules_buf).decode('utf-8')
    }
    logger.info("Step 6/6: Final payload prepared.")
    return payload

# --- Helper functions for processing ---

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
    if codes.get('A'):
        h = images['A'].shape[0]
        output.update({k: [np.array([p[0] - config.ADJUSTMENTS['A']['l'], h - p[1]]) for p in v] for k, v in codes['A'].items()})
    if codes.get('B'):
        h = images['B'].shape[0]
        offset = w1
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['B']['l'], h - p[1]]) for p in v] for k, v in codes['B'].items()})
    if codes.get('C'):
        h = images['C'].shape[0]
        offset = w1 + w2
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['C']['l'], h - p[1]]) for p in v] for k, v in codes['C'].items()})
    if codes.get('D'):
        h = images['D'].shape[0]
        offset = w1 + w2 + w3
        output.update({k: [np.array([p[0] + offset - config.ADJUSTMENTS['D']['l'], h - p[1]]) for p in v] for k, v in codes['D'].items()})
    return output

def _scale_module_outlines(qr_coords_pixels):
    """
    Calculates module outlines. It uses the highly accurate calibrated conversion
    factor if available, otherwise it falls back to calculating it from the QR codes.
    """
    conv_factor = None
    if config.USE_HOMOGRAPHY and CALIBRATED_CONV_FACTOR is not None:
        logger.info("Using calibrated conversion factor for scaling.")
        conv_factor = CALIBRATED_CONV_FACTOR
    else:
        logger.info("Using QR-based conversion factor for scaling.")
        lengths = []
        for corners in qr_coords_pixels.values():
            lengths.extend([_calculate_distance(corners[i], corners[(i + 1) % 4]) for i in range(4)])
        if not lengths: conv_factor = 0.065
        else: conv_factor = config.QR_CODE_REAL_SIZE_MM / (sum(lengths) / len(lengths))

    module_outlines_mm = {}
    for module, qr_corners in qr_coords_pixels.items():
        if module not in config.MODULE_DIMENSIONS: continue
        mod_height_mm, mod_width_mm = config.MODULE_DIMENSIONS[module]
        t1, t2, _, t4 = qr_corners
        v_top_px = t2 - t1
        v_left_px = t4 - t1
        norm_top = np.linalg.norm(v_top_px)
        norm_left = np.linalg.norm(v_left_px)
        if norm_top == 0 or norm_left == 0: continue
        u_top = v_top_px / norm_top
        u_left = v_left_px / norm_left
        v_module_width = u_top * (mod_width_mm / conv_factor)
        v_module_height = u_left * (mod_height_mm / conv_factor)
        c1, c2, c4, c3 = t1, t1 + v_module_width, t1 + v_module_height, t1 + v_module_width + v_module_height
        module_outlines_mm[module] = [c * conv_factor for c in [c1, c2, c3, c4]]
        
    return module_outlines_mm, conv_factor

def _draw_modules_on_image(image, module_outlines_mm, conv_factor, output_path):
    """
    Draws module outlines and text on the image using styles from the config file.
    """
    try:
        canvas = image.copy()
        styles = config.DRAWING_STYLES

        for module, corners_mm in module_outlines_mm.items():
            pixel_points = (np.array(corners_mm) / conv_factor).astype(np.int32)
            pixel_points[:, 1] = canvas.shape[0] - pixel_points[:, 1] # Final flip for drawing

            cv2.polylines(canvas, [pixel_points], isClosed=True, color=styles["line_color_bgr"], thickness=styles["line_thickness"])
            
            center_x, center_y = np.mean(pixel_points, axis=0).astype(np.int32)
            text = module
            
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["font_thickness"])
            box_p1 = (center_x - tw // 2 - 5, center_y - th - 5)
            box_p2 = (center_x + tw // 2 + 5, center_y + 5)
            
            cv2.rectangle(canvas, box_p1, box_p2, styles["bg_color_bgr"], cv2.FILLED)
            cv2.putText(canvas, text, (center_x - tw // 2, center_y), cv2.FONT_HERSHEY_SIMPLEX, 
                        styles["font_scale"], styles["text_color_bgr"], styles["font_thickness"], cv2.LINE_AA)

        cv2.imwrite(output_path, canvas)
        logger.info(f"High-quality visualization with module outlines saved to {output_path}")
        return canvas
    except Exception as e:
        logger.error(f"An error occurred in _draw_modules_on_image: {e}")
        return None

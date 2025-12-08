import cv2
import numpy as np
import imutils
import zxingcpp
import math
import json
import os
import logging

import config
from utils import NumpyEncoder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Calibrated Conversion Factor (from master's calibration) ---
CALIBRATED_CONV_FACTOR_MASTER = None
if config.USE_HOMOGRAPHY:
    try:
        factor_path = os.path.join(config.CAPTURED_PATH, config.CALIBRATED_FACTOR_FILE)
        if os.path.exists(factor_path):
            with open(factor_path, 'r') as f:
                data = json.load(f)
                CALIBRATED_CONV_FACTOR_MASTER = data.get("conversion_factor")
            if CALIBRATED_CONV_FACTOR_MASTER:
                 logger.info(f"Successfully loaded master's calibrated conversion factor: {CALIBRATED_CONV_FACTOR_MASTER}")
            else:
                logger.error("Master's calibrated factor file is invalid.")
        else:
            logger.error(f"Master's calibrated factor file not found at {factor_path}. Please run calibration on master first.")
    except Exception as e:
        logger.error(f"Failed to load master's calibrated conversion factor: {e}")

# --- Internal Helper Functions ---
def _renaming(name):
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# --- Core Processing Functions for Master ---
def process_master_images(raw_images):
    logger.info("--- Starting master image processing stage ---")
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
        prepared_images[name] = shifted[config.MASTER_TOP_CROP : shifted.shape[0] - config.MASTER_BOTTOM_CROP, :]

    stitched_image_plain = _stitch_images(prepared_images)
    cv2.imwrite(config.MASTER_IMAGE_PATH, stitched_image_plain)
    logger.info("Step 1/4: Master images stitched together.")

    pixel_coords = _get_adjusted_coordinates(prepared_images)
    with open(config.MASTER_COORDS_PIXEL_PATH, "w") as f: json.dump(pixel_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 2/4: Pixel coordinates of QR codes extracted.")

    module_outline_coords, conv_factor = _scale_module_outlines(pixel_coords)
    if not module_outline_coords:
        logger.error("Failed to calculate module outlines for master. Aborting.")
        return False
    with open(config.MASTER_COORDS_SCALED_PATH, "w") as f: json.dump(module_outline_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 3/4: Module outline coordinates calculated in mm.")

    stitched_image_with_modules = _draw_modules_on_image(stitched_image_plain, module_outline_coords, conv_factor, config.MASTER_IMAGE_WITH_MODULES_PATH)
    if stitched_image_with_modules is None: return False
    logger.info("Step 4/4: Visualization image created for master.")
    return True

def _stitch_images(images):
    cropped_parts = [img[:, config.ADJUSTMENTS[name]['l'] : img.shape[1] - config.ADJUSTMENTS[name]['d']] for name, img in images.items()]
    return cv2.hconcat(cropped_parts)

def _decode_qr_codes(image):
    if image is None: return {}
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    barcodes = zxingcpp.read_barcodes(gray_image)
    positions = { _renaming(str(b.text)): [np.array([int(p.split('x')[0]), int(p.split('x')[1])]) for p in str(b.position).strip('\x00').split()] for b in barcodes if _renaming(str(b.text)) != 'Unknown' }
    return positions

def _get_adjusted_coordinates(images):
    widths = [img.shape[1] - config.ADJUSTMENTS[name]['l'] - config.ADJUSTMENTS[name]['d'] for name, img in images.items()]
    offsets = [0, widths[0], widths[0]+widths[1], widths[0]+widths[1]+widths[2]]
    codes = {name: _decode_qr_codes(img) for name, img in images.items()}
    output = {}
    h = images['A'].shape[0] 
    for i, name in enumerate(images.keys()):
        if codes.get(name):
            output.update({k: [np.array([p[0] + offsets[i] - config.ADJUSTMENTS[name]['l'], h - p[1]]) for p in v] for k, v in codes[name].items()})
    return output

def _scale_module_outlines(qr_coords_pixels):
    conv_factor = CALIBRATED_CONV_FACTOR_MASTER if config.USE_HOMOGRAPHY and CALIBRATED_CONV_FACTOR_MASTER else None
    if not conv_factor:
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
        v_module_width = u_top * (mod_width_mm / conv_factor)
        v_module_height = u_left * (mod_height_mm / conv_factor)
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
            box_p1, box_p2 = (center_x - tw//2-5, center_y-th-5), (center_x+tw//2+5, center_y+5)
            cv2.rectangle(canvas, box_p1, box_p2, styles["bg_color_bgr"], cv2.FILLED)
            cv2.putText(canvas, module, (center_x-tw//2, center_y), cv2.FONT_HERSHEY_SIMPLEX, styles["font_scale"], styles["text_color_bgr"], styles["font_thickness"], cv2.LINE_AA)
        cv2.imwrite(output_path, canvas)
        logger.info(f"High-quality visualization saved to {output_path}")
        return canvas
    except Exception as e:
        logger.error(f"An error occurred in _draw_modules_on_image: {e}")
        return None

def combine_master_slave_coordinates():
    logger.info("Combining master and slave coordinates...")
    combined_data = {}
    try:
        if os.path.exists(config.SLAVE_COORDS_PATH):
            with open(config.SLAVE_COORDS_PATH, "r") as f: 
                slave_data = json.load(f)
                combined_data.update({f"{k}_slave": v for k, v in slave_data.items()})
        if os.path.exists(config.MASTER_COORDS_SCALED_PATH):
            with open(config.MASTER_COORDS_SCALED_PATH, "r") as f: 
                master_data = json.load(f)
                combined_data.update({f"{k}_master": v for k, v in master_data.items()})
        with open(config.COMBINED_COORDS_PATH, "w") as f: json.dump(combined_data, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved combined coordinates to {config.COMBINED_COORDS_PATH}")
    except Exception as e:
        logger.error(f"Failed to combine coordinates: {e}")

def _join_images_generic(top_img_path, bottom_img_path, output_path):
    try:
        top_img = cv2.imread(top_img_path)
        bottom_img = cv2.imread(bottom_img_path)
        if top_img is None or bottom_img is None:
            logger.error(f"Could not load one or both images for joining: {top_img_path}, {bottom_img_path}")
            return False
        p = config.JOIN
        common_width = max(top_img.shape[1] + abs(p['top_horizontal_shift']), bottom_img.shape[1] + abs(p['bottom_horizontal_shift']))
        top_canvas = np.full((top_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)
        bottom_canvas = np.full((bottom_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)
        top_x = max(0, p['top_horizontal_shift'])
        bottom_x = max(0, p['bottom_horizontal_shift'])
        top_canvas[:, top_x:top_x + top_img.shape[1]] = top_img
        bottom_canvas[:, bottom_x:bottom_x + bottom_img.shape[1]] = bottom_img
        top_canvas_cropped = top_canvas[p['top_top_crop'] : top_canvas.shape[0] - p['top_bottom_crop'], :]
        bottom_canvas_cropped = bottom_canvas[p['bottom_top_crop'] : bottom_canvas.shape[0] - p['bottom_bottom_crop'], :]
        combined_image = np.vstack((top_canvas_cropped, bottom_canvas_cropped))
        cv2.imwrite(output_path, combined_image)
        logger.info(f"Saved combined image to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed during generic image joining: {e}")
        return False

def join_master_slave_plain_images():
    logger.info("Joining master and slave plain images (without modules)...")
    _join_images_generic(config.SLAVE_IMAGE_PATH, config.MASTER_IMAGE_PATH, config.COMBINED_IMAGE_PLAIN_PATH)

def redraw_modules_on_final_image():
    logger.info("Redrawing all modules on fresh combined image with accurate coordinates...")
    try:
        conv_factor_slave = None
        slave_factor_path = os.path.join(config.RECEIVED_PATH, "slave_conv_factor.json")
        if os.path.exists(slave_factor_path):
            with open(slave_factor_path, 'r') as f:
                data = json.load(f)
                conv_factor_slave = data.get("conv_factor_slave")
                logger.info(f"Successfully loaded slave's conversion factor: {conv_factor_slave}")
        
        if not conv_factor_slave:
            logger.warning("Could not load slave conversion factor. Slave modules may be inaccurate.")
            conv_factor_slave = CALIBRATED_CONV_FACTOR_MASTER

        image = cv2.imread(config.COMBINED_IMAGE_PLAIN_PATH)
        if image is None:
            logger.error(f"Could not load plain combined image at {config.COMBINED_IMAGE_PLAIN_PATH}")
            return
        with open(config.COMBINED_COORDS_PATH, 'r') as f: all_coords_mm = json.load(f)
        
        slave_stitched_img = cv2.imread(config.SLAVE_IMAGE_PATH)
        master_stitched_img = cv2.imread(config.MASTER_IMAGE_PATH)
        
        slave_h, _ = slave_stitched_img.shape[:2]
        master_h, _ = master_stitched_img.shape[:2]

        slave_final_h = slave_h - config.JOIN['top_top_crop'] - config.JOIN['top_bottom_crop']

        for module_key, corners_mm in all_coords_mm.items():
            # FIXED: Correctly extract full module name
            if "_slave" in module_key:
                module_name = module_key.replace("_slave", "")
                corners_px_raw = (np.array(corners_mm) / conv_factor_slave).astype(np.int32)
                corners_px_raw[:, 1] = slave_h - corners_px_raw[:, 1]
                corners_px_raw[:, 0] += config.JOIN['top_horizontal_shift']
                corners_px_raw[:, 1] -= config.JOIN['top_top_crop']

            elif "_master" in module_key:
                module_name = module_key.replace("_master", "")
                corners_px_raw = (np.array(corners_mm) / CALIBRATED_CONV_FACTOR_MASTER).astype(np.int32)
                corners_px_raw[:, 1] = master_h - corners_px_raw[:, 1]
                corners_px_raw[:, 0] += config.JOIN['bottom_horizontal_shift']
                corners_px_raw[:, 1] += slave_final_h - config.JOIN['bottom_top_crop']
            else:
                continue
            
            cv2.polylines(image, [corners_px_raw], isClosed=True, color=config.DRAWING_STYLES["line_color_bgr"], thickness=config.DRAWING_STYLES["line_thickness"])

            styles = config.DRAWING_STYLES
            
            module_width_px = np.linalg.norm(corners_px_raw[0] - corners_px_raw[1])
            target_text_width = module_width_px * 0.9
            
            font_scale = 3.0
            font_thickness = styles["font_thickness"]
            
            while True:
                (text_width, _), _ = cv2.getTextSize(module_name, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
                if text_width < target_text_width or font_scale <= 0.5:
                    break
                font_scale -= 0.1

            center_x, center_y = np.mean(corners_px_raw, axis=0).astype(np.int32)
            (tw, th), _ = cv2.getTextSize(module_name, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
            box_p1 = (center_x - tw // 2 - 5, center_y - th - 5)
            box_p2 = (center_x + tw // 2 + 5, center_y + 5)
            cv2.rectangle(image, box_p1, box_p2, styles["bg_color_bgr"], cv2.FILLED)
            cv2.putText(image, module_name, (center_x - tw // 2, center_y), cv2.FONT_HERSHEY_SIMPLEX, 
                        font_scale, styles["text_color_bgr"], font_thickness, cv2.LINE_AA)

        cv2.imwrite(config.COMBINED_IMAGE_FINAL_PATH, image)
        logger.info(f"Saved final retouched image to {config.COMBINED_IMAGE_FINAL_PATH}")

    except Exception as e:
        logger.error(f"Failed to redraw modules on final image: {e}", exc_info=True)

def convert_final_coords_to_cm():
    logger.info("Converting final coordinates to cm...")
    try:
        conv_factor_slave = None
        slave_factor_path = os.path.join(config.RECEIVED_PATH, "slave_conv_factor.json")
        if os.path.exists(slave_factor_path):
            with open(slave_factor_path, 'r') as f:
                data = json.load(f)
                conv_factor_slave = data.get("conv_factor_slave")
        
        if not conv_factor_slave:
            logger.warning("Could not load slave conversion factor for cm conversion.")
            conv_factor_slave = CALIBRATED_CONV_FACTOR_MASTER

        with open(config.COMBINED_COORDS_PATH, 'r') as f: data = json.load(f)
        
        slave_stitched_img = cv2.imread(config.SLAVE_IMAGE_PATH)
        master_stitched_img = cv2.imread(config.MASTER_IMAGE_PATH)
        
        slave_h, _ = slave_stitched_img.shape[:2]
        master_h, _ = master_stitched_img.shape[:2]
        
        slave_final_h = slave_h - config.JOIN['top_top_crop'] - config.JOIN['top_bottom_crop']

        final_pixel_coords = {}
        for module_key, corners_mm in data.items():
            # FIXED: Correctly extract full module name
            if "_slave" in module_key:
                module_name = module_key.replace("_slave", "")
                corners_px_raw = (np.array(corners_mm) / conv_factor_slave)
                corners_px_raw[:, 1] = slave_h - corners_px_raw[:, 1]
                corners_px_raw[:, 0] += config.JOIN['top_horizontal_shift']
                corners_px_raw[:, 1] -= config.JOIN['top_top_crop']

            elif "_master" in module_key:
                module_name = module_key.replace("_master", "")
                corners_px_raw = (np.array(corners_mm) / CALIBRATED_CONV_FACTOR_MASTER)
                corners_px_raw[:, 1] = master_h - corners_px_raw[:, 1]
                corners_px_raw[:, 0] += config.JOIN['bottom_horizontal_shift']
                corners_px_raw[:, 1] += slave_final_h - config.JOIN['bottom_top_crop']
            else:
                continue

            final_pixel_coords[module_name] = corners_px_raw.tolist()

        cm_per_pixel = (config.REAL_DISTANCE_CM) / abs(config.PIXEL_POINT_1 - config.PIXEL_POINT_2)

        final_cm_data = {}
        for name, corners in final_pixel_coords.items():
            center_x_px = sum(p[0] for p in corners) / 4
            center_y_px = sum(p[1] for p in corners) / 4
            angle = math.degrees(math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0]))
            
            # This now correctly saves data with full names, e.g., "Quality_control"
            final_cm_data[name] = {
                "center_cm": [round(center_x_px * cm_per_pixel, 2), round(center_y_px * cm_per_pixel, 2)],
                "angle": round(angle, 2)
            }

        with open(config.COORDS_IN_CM_PATH, 'w') as f: json.dump(final_cm_data, f, indent=4)
        logger.info(f"Converted final coordinates to cm and saved to {config.COORDS_IN_CM_PATH}")
    except Exception as e:
        logger.error(f"Failed to convert coordinates to cm: {e}", exc_info=True)

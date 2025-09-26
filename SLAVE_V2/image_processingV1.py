import cv2
import numpy as np
import imutils
import zxingcpp
import math
import json
import os
import logging
import matplotlib.pyplot as plt
import base64

import config
import camera_utils
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Internal Helper Functions (remain the same) ---
def _renaming(name):
    return config.MODULE_NAMES.get(name, 'Unknown')

def _calculate_distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

# --- Core Processing Functions ---

def capture_and_prepare_images():
    """
    STAGE 1: Captures, rotates, shifts, and crops images from all 4 cameras.
    This function is now separate to allow for independent testing of the hardware.
    """
    images = {}
    for name in config.CAMERA_DEVICE_PATHS.keys():
        raw_img = camera_utils.capture_image_from(name)
        if raw_img is None:
            logger.error(f"Failed to get raw image from camera {name}. Aborting.")
            return None
        
        # This function now returns the prepared images for the next stage
        images[name] = raw_img
        
    return images

def process_and_save_images(raw_images):
    """
    STAGE 2: Takes raw images, processes them, and saves all final outputs.
    This allows for re-processing without re-capturing.
    """
    logger.info("--- Starting image processing stage ---")
    prepared_images = {}
    
    # Perform the preparation steps on the provided raw images
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

    # The rest of the pipeline continues from here...
    stitched_image_plain = _stitch_images(prepared_images)
    cv2.imwrite(os.path.join(config.OUTPUT_PATH, 'stitched_plain.jpg'), stitched_image_plain)
    logger.info("Step 2/6: Images stitched together.")

    pixel_coords = _get_adjusted_coordinates(prepared_images)
    with open(os.path.join(config.OUTPUT_PATH, 'coords_pixel.json'), "w") as f: json.dump(pixel_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 3/6: Pixel coordinates extracted.")

    scaled_coords, conv_factor = _scale_coordinates(pixel_coords)
    with open(os.path.join(config.OUTPUT_PATH, 'coords_scaled.json'), "w") as f: json.dump(scaled_coords, f, indent=4, cls=NumpyEncoder)
    logger.info("Step 4/6: Coordinates scaled to mm.")

    viz_path = os.path.join(config.OUTPUT_PATH, 'stitched_with_modules.jpg')
    stitched_image_with_modules = _draw_modules_on_image(stitched_image_plain, scaled_coords, conv_factor, viz_path)
    if stitched_image_with_modules is None: return None
    logger.info("Step 5/6: Visualization image created.")

    final_shifted_coords = {
        name: [[p[0] + config.FINAL_X_SHIFT, p[1] + config.FINAL_Y_SHIFT] for p in coords]
        for name, coords in scaled_coords.items()
    }
    with open(os.path.join(config.OUTPUT_PATH, 'coords_final_shifted.json'), "w") as f: json.dump(final_shifted_coords, f, indent=4, cls=NumpyEncoder)
    
    logger.info("Processing stage complete. All files saved.")
    return True # Indicate success

def capture_and_process_all():
    """The main orchestrator function that runs both stages."""
    logger.info("--- Starting full capture and processing sequence ---")
    
    # STAGE 1
    raw_images = capture_and_prepare_images()
    if not raw_images:
        return None
    logger.info("Step 1/6: All images captured.")

    # STAGE 2
    if not process_and_save_images(raw_images):
        return None

    # After processing, prepare the final payload for MQTT
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

# --- Helper functions for processing (stitch, decode, scale, draw) ---
# These are unchanged from the previous version. I'm including them here
# for completeness of the file.

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

def _scale_coordinates(qr_coords_pixels):
    lengths = []
    for corners in qr_coords_pixels.values():
        lengths.extend([_calculate_distance(corners[i], corners[(i + 1) % 4]) for i in range(4)])
    if not lengths: conv_factor = 0.065
    else: conv_factor = config.QR_CODE_REAL_SIZE_MM / (sum(lengths) / len(lengths))
    scaled_coords = {
        module: [c * conv_factor for c in corners]
        for module, corners in qr_coords_pixels.items()
    }
    return scaled_coords, conv_factor

def _draw_modules_on_image(image, scaled_coords, conv_factor, output_path):
    img_flipped = cv2.flip(image, 0)
    img_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)
    plt.figure()
    plt.imshow(img_rgb)
    ax = plt.gca()
    ax.set_aspect('equal', adjustable='box')
    ax.invert_yaxis()
    ax.axis('off')
    for module, corners in scaled_coords.items():
        pixel_points = np.array(corners) / conv_factor
        kontx = np.append(pixel_points[:, 0], pixel_points[0, 0])
        konty = np.append(pixel_points[:, 1], pixel_points[0, 1])
        plt.plot(kontx, konty, color='blue')
        center_x, center_y = np.mean(pixel_points, axis=0)
        plt.text(center_x, center_y, module, ha='center', va='center', backgroundcolor='w', color='red', fontsize=7)
    plt.savefig(output_path, dpi=1000, bbox_inches='tight', pad_inches=0)
    plt.close()
    return cv2.imread(output_path)

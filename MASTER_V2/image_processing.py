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
    """Add vertical padding and shift the image within the new canvas."""
    height, width = img.shape[:2]
    total_height = 2 * padding + height
    white_canvas = np.ones((total_height, width, 3), dtype=np.uint8) * 255
    top_padding = padding
    white_canvas[top_padding:top_padding + height, :] = img
    return np.roll(white_canvas, -int(shift_amount), axis=0)

# --- Core Processing Functions ---

def decode_qr_codes(image):
    """Decode QR codes from an image and return their positions."""
    if image is None:
        logger.error("Cannot decode QR codes from a None image.")
        return {}
    
    barcodes = zxingcpp.read_barcodes(image)
    positions = {}
    for barcode in barcodes:
        text = _renaming(str(barcode.text))
        if text != 'Unknown':
            pos_str = str(barcode.position).strip('\x00')
            pairs = pos_str.split()
            corners = [np.array([int(p.split('x')[0]), int(p.split('x')[1])]) for p in pairs]
            positions[text] = corners
    
    if not barcodes:
        logger.warning("Could not find any barcodes in the provided image.")
    
    return positions

def get_conversion_factor(codes, qr_real_size):
    """Calculate the mm-per-pixel conversion factor from QR code sizes."""
    if not codes:
        return 0.065  # Return a default factor if no codes are found
    
    lengths = []
    for corners in codes.values():
        lengths.append(_calculate_distance(corners[0], corners[1]))
        lengths.append(_calculate_distance(corners[1], corners[2]))
        lengths.append(_calculate_distance(corners[2], corners[3]))
        lengths.append(_calculate_distance(corners[3], corners[0]))
    
    if not lengths:
        return 0.065

    avg_pixel_length = sum(lengths) / len(lengths)
    return qr_real_size / avg_pixel_length

def scale_coordinates(qr_corners, conversion_factor):
    """Scale QR corner coordinates from pixels to real-world units (mm)."""
    scaled_coords = {}
    for module, corners in qr_corners.items():
        if module not in config.MODULE_DIMENSIONS:
            logger.warning(f"Module {module} not in MODULE_DIMENSIONS. Skipping.")
            continue
        
        t1, t2, t3, t4 = corners
        mod_width_mm, mod_height_mm = config.MODULE_DIMENSIONS[module]

        # Vectors from top-left corner
        v_top = t2 - t1
        v_left = t4 - t1

        # Scale vectors to real-world size
        # Note: This assumes a relatively square-on view.
        # A more robust method would use homography.
        v_top_scaled = v_top * (mod_width_mm / _calculate_distance(t1, t2))
        v_left_scaled = v_left * (mod_height_mm / _calculate_distance(t1, t4))

        # Reconstruct corners from scaled vectors
        tt1 = t1 * conversion_factor
        tt2 = tt1 + v_top_scaled * conversion_factor
        tt4 = tt1 + v_left_scaled * conversion_factor
        tt3 = tt2 + v_left_scaled * conversion_factor # Perpendicular assumption

        scaled_coords[module] = [tt1.tolist(), tt2.tolist(), tt3.tolist(), tt4.tolist()]
        
    return scaled_coords

def adjust_master_coordinates(img_a, img_b, img_c, img_d):
    """Find QR codes in each master image and adjust their coordinates for the final stitched image."""
    w1, h1 = _crop_left_right(img_a, config.ADJUSTMENTS['A']['l'], config.ADJUSTMENTS['A']['d']).shape[1::-1]
    w2, h2 = _crop_left_right(img_b, config.ADJUSTMENTS['B']['l'], config.ADJUSTMENTS['B']['d']).shape[1::-1]
    w3, h3 = _crop_left_right(img_c, config.ADJUSTMENTS['C']['l'], config.ADJUSTMENTS['C']['d']).shape[1::-1]

    codes = {
        'A': decode_qr_codes(img_a), 'B': decode_qr_codes(img_b),
        'C': decode_qr_codes(img_c), 'D': decode_qr_codes(img_d)
    }
    
    output = {}
    if codes['A']:
        output.update({k: [np.array([x - config.ADJUSTMENTS['A']['l'], h1 - y]) for [x, y] in v] for k, v in codes['A'].items()})
    if codes['B']:
        offset = w1
        output.update({k: [np.array([x + offset - config.ADJUSTMENTS['B']['l'], h2 - y]) for [x, y] in v] for k, v in codes['B'].items()})
    if codes['C']:
        offset = w1 + w2
        output.update({k: [np.array([x + offset - config.ADJUSTMENTS['C']['l'], h3 - y]) for [x, y] in v] for k, v in codes['C'].items()})
    if codes['D']:
        offset = w1 + w2 + w3
        output.update({k: [np.array([x + offset - config.ADJUSTMENTS['D']['l'], h1 - y]) for [x, y] in v] for k, v in codes['D'].items()})

    return output

def draw_modules_on_image(image, coordinates, output_path, dpi=1200):
    """Draw module outlines and names on an image."""
    img_flipped = cv2.flip(image, 0)
    img_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)

    plt.imshow(img_rgb)
    ax = plt.gca()
    ax.set_aspect('equal', adjustable='box')
    ax.invert_yaxis()
    ax.axis('off')
    ax.set_position([0, 0, 1, 1])

    for module, corners in coordinates.items():
        points = np.array(corners)
        kontx = np.append(points[:, 0], points[0, 0])
        konty = np.append(points[:, 1], points[0, 1])
        plt.plot(kontx, konty, color='blue')
        
        center_x = np.mean(points[:, 0])
        center_y = np.mean(points[:, 1])
        plt.text(center_x, center_y, module, ha='center', va='center', backgroundcolor='w', color='red', fontsize=7)

    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0)
    plt.close()
    logger.info(f"Drew modules and saved to {output_path}")

def process_master_images(images):
    """
    Main function to process the 4 raw images from the master cameras.
    - Rotates and adjusts images.
    - Stitches them horizontally.
    - Finds QR codes and calculates their coordinates.
    - Scales coordinates to real-world values.
    - Draws modules on the stitched image.
    """
    logger.info("Processing master images...")

    # 1. Rotate, shift, and crop each image
    processed_imgs = {}

    for name, img in images.items():
        angle = config.ADJUSTMENTS[name]['angle']
        vp = config.ADJUSTMENTS[name]['vp']
            
        # --- THIS IS THE NEW, BETTER LINE ---
        rotation_setting = config.CAMERA_ROTATIONS.get(name) # Get the rotation value from config
        rotated = cv2.rotate(img, rotation_setting)
        angled = imutils.rotate(rotated, angle=angle)
        shifted = _vertical_shift(angled, vp)
        cropped = _crop_image(shifted, config.MASTER_TOP_CROP, config.MASTER_BOTTOM_CROP)
        processed_imgs[name] = cropped

    # 2. Stitch images horizontally
    stitched_image = cv2.hconcat([
        _crop_left_right(processed_imgs['A'], config.ADJUSTMENTS['A']['l'], config.ADJUSTMENTS['A']['d']),
        _crop_left_right(processed_imgs['B'], config.ADJUSTMENTS['B']['l'], config.ADJUSTMENTS['B']['d']),
        _crop_left_right(processed_imgs['C'], config.ADJUSTMENTS['C']['l'], config.ADJUSTMENTS['C']['d']),
        _crop_left_right(processed_imgs['D'], config.ADJUSTMENTS['D']['l'], config.ADJUSTMENTS['D']['d'])
    ])
    cv2.imwrite(config.MASTER_IMAGE_PATH, stitched_image)
    logger.info(f"Saved stitched master image to {config.MASTER_IMAGE_PATH}")

    # 3. Get QR code coordinates from the pre-stitched images
    qr_coords_pixels = adjust_master_coordinates(
        processed_imgs['A'], processed_imgs['B'], processed_imgs['C'], processed_imgs['D']
    )
    with open(config.MASTER_COORDS_PATH, "w") as f:
        json.dump(qr_coords_pixels, f, indent=4, cls=NumpyEncoder)
    logger.info(f"Saved master pixel coordinates to {config.MASTER_COORDS_PATH}")

    # 4. Scale coordinates
    conv_factor = get_conversion_factor(qr_coords_pixels, config.QR_CODE_REAL_SIZE_MM)
    scaled_coords = scale_coordinates(qr_coords_pixels, conv_factor)
    with open(config.MASTER_COORDS_SCALED_PATH, "w") as f:
        json.dump(scaled_coords, f, indent=4, cls=NumpyEncoder)
    logger.info(f"Saved master scaled coordinates to {config.MASTER_COORDS_SCALED_PATH}")

    # 5. Draw modules on the stitched image
    draw_modules_on_image(stitched_image, scaled_coords, config.MASTER_IMAGE_WITH_MODULES_PATH)

def combine_master_slave_coordinates():
    """Merge master and slave coordinate files with specified offsets."""
    logger.info("Combining master and slave coordinates...")
    combined_data = {}

    def apply_offset(data, x_off, y_off):
        return {name: [[p[0] + x_off, p[1] + y_off] for p in coords] for name, coords in data.items()}

    try:
        if os.path.exists(config.SLAVE_COORDS_PATH):
            with open(config.SLAVE_COORDS_PATH, "r") as f:
                slave_data = json.load(f)
            combined_data.update(apply_offset(slave_data, config.COORDS_COMBINE_OFFSETS['x_offset_slave'], config.COORDS_COMBINE_OFFSETS['y_offset_slave']))
        
        if os.path.exists(config.MASTER_COORDS_SCALED_PATH):
            with open(config.MASTER_COORDS_SCALED_PATH, "r") as f:
                master_data = json.load(f)
            combined_data.update(apply_offset(master_data, config.COORDS_COMBINE_OFFSETS['x_offset_master'], config.COORDS_COMBINE_OFFSETS['y_offset_master']))

        with open(config.COMBINED_COORDS_PATH, "w") as f:
            json.dump(combined_data, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved combined coordinates to {config.COMBINED_COORDS_PATH}")

        # Convert to center + rotation format
        converted_data = {}
        for name, corners in combined_data.items():
            if isinstance(corners, list) and len(corners) == 4:
                center_x = sum(p[0] for p in corners) / 4
                center_y = sum(p[1] for p in corners) / 4
                angle = math.degrees(math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0]))
                converted_data[name] = [center_x, center_y, angle]
        
        with open(config.COMBINED_CONVERTED_COORDS_PATH, "w") as f:
            json.dump(converted_data, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved converted center+rotation data to {config.COMBINED_CONVERTED_COORDS_PATH}")

    except Exception as e:
        logger.error(f"Failed to combine coordinates: {e}")

def join_master_slave_images():
    """Joins the final processed images from master and slave vertically."""
    logger.info("Joining master and slave images...")
    try:
        top_img = cv2.imread(config.SLAVE_IMAGE_WITH_MODULES_PATH)
        bottom_img = cv2.imread(config.MASTER_IMAGE_WITH_MODULES_PATH)

        if top_img is None or bottom_img is None:
            logger.error("Could not load one or both images for joining.")
            return

        # Apply transformations from config
        p = config.JOIN
        top_img = _crop_image(top_img, p['top_top_crop'], p['top_bottom_crop'])
        bottom_img = _crop_image(bottom_img, p['bottom_top_crop'], p['bottom_bottom_crop'])
        
        # Determine common width and create canvases
        common_width = max(top_img.shape[1], bottom_img.shape[1]) + abs(p['top_horizontal_shift']) + abs(p['bottom_horizontal_shift'])
        top_canvas = np.full((top_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)
        bottom_canvas = np.full((bottom_img.shape[0], common_width, 3), p['padding_color'], dtype=np.uint8)

        # Place images on canvases with horizontal shift
        top_x = p['top_horizontal_shift']
        top_canvas[:, top_x:top_x + top_img.shape[1]] = top_img
        bottom_x = p['bottom_horizontal_shift']
        bottom_canvas[:, bottom_x:bottom_x + bottom_img.shape[1]] = bottom_img

        # Stack canvases
        combined_image = np.vstack((top_canvas, bottom_canvas))
        cv2.imwrite(config.COMBINED_IMAGE_PATH, combined_image)
        logger.info(f"Saved final combined image to {config.COMBINED_IMAGE_PATH}")

        # Resize for upload
        base_width = 800
        h, w = combined_image.shape[:2]
        w_percent = base_width / float(w)
        h_size = int(float(h) * w_percent)
        resized_image = cv2.resize(combined_image, (base_width, h_size), interpolation=cv2.INTER_AREA)
        cv2.imwrite(config.COMBINED_IMAGE_RESIZED_PATH, resized_image)
        logger.info(f"Saved resized image for upload to {config.COMBINED_IMAGE_RESIZED_PATH}")

    except Exception as e:
        logger.error(f"Failed to join images: {e}")

def convert_final_coords_to_cm():
    """Converts the final combined coordinates from pixels to cm."""
    logger.info("Converting final coordinates to cm...")
    try:
        with open(config.COMBINED_CONVERTED_COORDS_PATH, 'r') as f:
            data = json.load(f)

        pixel_distance = abs(config.PIXEL_POINT_1 - config.PIXEL_POINT_2)
        if pixel_distance == 0:
            logger.error("Pixel distance for scaling cannot be zero.")
            return

        cm_per_pixel = config.REAL_DISTANCE_CM / pixel_distance
        
        converted_data = {}
        for key, value in data.items():
            x_pixel, y_pixel, angle = value
            converted_data[key] = [x_pixel * cm_per_pixel, y_pixel * cm_per_pixel, angle]
        
        with open(config.COORDS_IN_CM_PATH, 'w') as f:
            json.dump(converted_data, f, indent=4)
        logger.info(f"Converted coordinates to cm and saved to {config.COORDS_IN_CM_PATH}")

    except FileNotFoundError:
        logger.error(f"Could not find coordinate file: {config.COMBINED_CONVERTED_COORDS_PATH}")
    except Exception as e:
        logger.error(f"Failed to convert coordinates to cm: {e}")

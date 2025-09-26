import cv2
import numpy as np

# --- General Settings ---
LOG_LEVEL = "INFO"

# --- File and Directory Paths ---
# Use an absolute path for BASE_PATH to avoid permission issues
BASE_PATH = "/home/slave/SLAVE_V2"
OUTPUT_PATH = f"{BASE_PATH}/output"
HOMOGRAPHY_MATRIX_FILE = "homography_matrix.npy"
# NEW: File to store the accurate conversion factor from calibration
CALIBRATED_FACTOR_FILE = "calibrated_factor.json"
# NEW: File path for the undrawn stitched image that is sent to master
SLAVE_UNDRAWN_IMAGE_PATH = f"{OUTPUT_PATH}/zdruzena_slika_slave.jpg"


# --- Network Settings ---
MASTER_IP = '192.168.9.118'
MQTT_PORT = 1883
MQTT_COMMAND_TOPIC = "camera/command"
MQTT_IMAGES_TOPIC = "camera/images"
# NEW: Topic for sending module coordinates
MQTT_COORDINATES_TOPIC = "camera/coordinates"

# --- Calibration Settings ---
USE_HOMOGRAPHY = True # SET TO `True` to use the new, precise method. SET TO `False` to use the old, reliable method.
CALIBRATION_CAMERA_NAME = 'B' # Which camera to use for calibration
CHECKERBOARD_DIMENSIONS = (3, 3) # Inner corners of the checkerboard (e.g., a 4x4 grid has 3x3 inner corners)
SQUARE_SIZE_MM = 2.5 #25.0 # The size of one square on your checkerboard in millimeters - now WRONG!!! because the MODULE_DIMENSIONS are in cm!! to compensate

# --- Hardware Settings for USB Cameras ---
CAMERA_DEVICE_PATHS = {
    'A': "/dev/video4", 
    'B': "/dev/video2",
    'C': "/dev/video0", 
    'D': "/dev/video6"
}
# Preferred camera resolutions (width, height)
PREFERRED_SIZES = [(3840, 3104), (3840, 2160), (3264, 2448), (2592, 1944), (2048, 1536), (1920, 1080), (1600, 1200), (1280, 960), (1280, 720)]
WARMUP_FRAMES = 8

# --- Image Processing Settings ---
# These are only used for testing the stitching, not for the main pipeline anymore
IMAGE_CROP_TOP = 200
IMAGE_CROP_BOTTOM = 0
IMAGE_CROP_LEFT = 0
IMAGE_CROP_RIGHT = 0
STITCHING_SHIFT_X = 0
STITCHING_SHIFT_Y = 0
ADJUSTMENTS = {\
    'A': {'vp': 50,    'l': 0,   'd': 0, 'angle': 0.0},\
    'B': {'vp': 0,     'l': 250, 'd': 0, 'angle': 0.0},\
    'C': {'vp': 40,    'l': 500, 'd': 0, 'angle': 0.0},\
    'D': {'vp': 0,     'l': 700, 'd': 0, 'angle': 0.0}\
}
TOP_CROP = 200
BOTTOM_CROP = 0
FINAL_X_SHIFT = 270
FINAL_Y_SHIFT = -2120

# --- NEW: Drawing Style Configuration ---
# This is now only used on the MASTER side.
# Colors are in (Blue, Green, Red) format for OpenCV
DRAWING_STYLES = {
    "line_color_bgr": (255, 0, 0),      # Blue
    "text_color_bgr": (0, 0, 255),      # Red
    "bg_color_bgr":   (255, 255, 255),  # White
    "line_thickness": 6,
    "font_scale":     3,
    "font_thickness": 2
}

# --- Module Definitions ---
MODULE_DIMENSIONS = {
    'Sorting': [80, 71.2], 'Standard5': [71, 80], 'Standard6': [71.2, 80], 'Robot_arm1': [71.2, 140],
    'Standard7': [71.2, 80], 'Warehouse_kocke': [140, 71], 'Engraving': [75, 71], 'Extended_conveyor': [71, 135],
    'Quality_control': [71.5, 75], 'Robot_arm2': [71.5, 80], 'Standard1': [75, 71], 'Warehouse_gravirne': [71.5, 80],
    'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [75, 71], 'Standard4': [71.2, 75]
}

MODULE_NAMES = {
    '00': 'Sorting', '01': 'Standard5', '02': 'Standard6', '03': 'Robot_arm1',
    '04': 'Standard7', '06': 'Warehouse_kocke', '05': 'Engraving', '07': 'Extended_conveyor',
    '08': 'Quality_control', '09': 'Robot_arm2', '10': 'Standard1', '11': 'Warehouse_gravirne',
    '12': 'Standard2', '13': 'AGV', '14': 'Standard3', '15': 'Standard4'
}

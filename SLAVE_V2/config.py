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

# --- Network Settings ---
MASTER_IP = '192.168.9.118'
MQTT_PORT = 1883
MQTT_COMMAND_TOPIC = "camera/command"
MQTT_IMAGES_TOPIC = "camera/images"

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
PREFERRED_SIZES = [(3840, 2160), (1920, 1080), (1280, 720)]
WARMUP_FRAMES = 5

# --- Image Processing Parameters ---
CAMERA_ROTATIONS = {
    'A': cv2.ROTATE_90_CLOCKWISE, 
    'B': cv2.ROTATE_90_CLOCKWISE,
    'C': cv2.ROTATE_90_CLOCKWISE, 
    'D': cv2.ROTATE_90_CLOCKWISE,
}
QR_CODE_REAL_SIZE_MM = 10.0
ADJUSTMENTS = {
    'A': {'vp': 50,    'l': 0,   'd': 0, 'angle': 0.0},
    'B': {'vp': 0,     'l': 250, 'd': 0, 'angle': 0.0},
    'C': {'vp': 40,    'l': 500, 'd': 0, 'angle': 0.0},
    'D': {'vp': 0,     'l': 700, 'd': 0, 'angle': 0.0}
}
TOP_CROP = 200
BOTTOM_CROP = 0
FINAL_X_SHIFT = 270
FINAL_Y_SHIFT = -2120

# --- NEW: Drawing Style Configuration ---
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
    'Sorting': [80, 71.2], 'Standard5': [71, 80], 'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 140], 'Standard7': [71.2, 80], 'Warehouse_kocke': [140, 71],
    'Engraving': [71, 80], 'Extended_conveyor': [71, 135], 'Quality_control': [80, 71.5],
    'Robot_arm2': [71.5, 80], 'Standard1': [75, 71], 'Warehouse_gravirne': [71.5, 80],
    'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [75, 71], 'Standard4': [71.2, 75]
}
MODULE_NAMES = {
    '00': 'Sorting', '01': 'Standard5', '09': 'Standard6', '02': 'Robot_arm1',
    '04': 'Standard7', '06': 'Warehouse_kocke', '05': 'Engraving', '07': 'Extended_conveyor',
    '08': 'Quality_control', '03': 'Robot_arm2', '10': 'Standard1', '14': 'Warehouse_gravirne',
    '12': 'Standard2', '13': 'AGV', '11': 'Standard3', '15': 'Standard4'
}

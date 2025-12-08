import numpy as np
import cv2

# --- General Settings ---
LOG_LEVEL = "INFO"

# --- File and Directory Paths ---
BASE_PATH = "/home/cameramodule/Desktop"
CAPTURED_PATH = f"{BASE_PATH}/captured"
RECEIVED_PATH = f"{BASE_PATH}/received"
COMBINED_PATH = f"{BASE_PATH}/combined"

# --- Slave file names ---
SLAVE_IMAGE_PATH = f"{RECEIVED_PATH}/zdruzena_slika_slave.jpg" 
SLAVE_IMAGE_WITH_MODULES_PATH = f"{RECEIVED_PATH}/rezultat_z_moduli.jpg"
SLAVE_COORDS_PATH = f"{RECEIVED_PATH}/koordinate_skalirane.json"

# --- Master file names ---
MASTER_IMAGE_PATH = f"{CAPTURED_PATH}/stitched_plain_master.jpg"
MASTER_IMAGE_WITH_MODULES_PATH = f"{CAPTURED_PATH}/stitched_with_modules_master.jpg"
MASTER_COORDS_PIXEL_PATH = f"{CAPTURED_PATH}/coords_pixel_master.json"
MASTER_COORDS_SCALED_PATH = f"{CAPTURED_PATH}/coords_scaled_master.json"

# --- Combined file names ---
COMBINED_IMAGE_PLAIN_PATH = f"{COMBINED_PATH}/combined_plain.jpg"
COMBINED_IMAGE_FINAL_PATH = f"{COMBINED_PATH}/combined_final.jpg"
COMBINED_IMAGE_WEB_PATH = f"{COMBINED_PATH}/combined_web_optimized.jpg"
COMBINED_COORDS_PATH = f"{COMBINED_PATH}/combined_koordinate.json"
COORDS_IN_CM_PATH = f"{COMBINED_PATH}/coordinates_in_cm.json"

# --- Network & Server Settings ---
MASTER_IP = '192.168.9.118' # NEW: IP of this master device
WEB_SERVER_PORT = 8000 # NEW: Port for the local image server

# --- MQTT Broker Settings (for slave communication) ---
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_TOPIC_COMMAND = 'camera/command'
MQTT_TOPIC_IMAGES = 'camera/images'

# --- ThingsBoard Settings ---
THINGSBOARD_HOST = '192.168.9.108'
THINGSBOARD_PORT = 1883
THINGSBOARD_USERNAME = "Module10_MQTT"
THINGSBOARD_PASSWORD = "Module10MQTT"
WEB_IMAGE_MAX_WIDTH = 1920
THINGSBOARD_RPC_SUBSCRIBE_TOPIC = 'v1/devices/me/rpc/request/+' # For RPC commands

# --- Calibration Settings ---
USE_HOMOGRAPHY = True 
CALIBRATION_CAMERA_NAME = 'A'
CHECKERBOARD_DIMENSIONS = (3, 3) 
SQUARE_SIZE_MM = 2.5
CALIBRATED_FACTOR_FILE = "calibrated_factor_master.json"

# --- Master Camera Settings ---
CAMERA_DEVICE_PATHS = {
    'A': "/dev/video2",
    'B': "/dev/video0",
    'C': "/dev/video4",
    'D': "/dev/video6"
}

PREFERRED_SIZES = [(3840, 2160), (1920, 1080), (1280, 720)]
#PREFERRED_SIZES = [(1280, 720), (1920, 1080), (3840, 2160)]
#PREFERRED_SIZES = [(1920, 1080), (3840, 2160), (1280, 720)]
WARMUP_FRAMES = 5

# --- Image Processing Parameters ---
CAMERA_ROTATIONS = {
    'A': cv2.ROTATE_90_CLOCKWISE, 
    'B': cv2.ROTATE_90_CLOCKWISE,
    'C': cv2.ROTATE_90_CLOCKWISE, 
    'D': cv2.ROTATE_90_CLOCKWISE,
}
QR_CODE_REAL_SIZE_MM = 10.0

# NEW: Defines the physical rotation of the QR code on the module.
# Most are 0 (standard), but some may be placed upside down (180).
QR_CODE_ORIENTATION = {
    'Standard1': 180,
    'Extended_conveyor': 180,
    # Add other modules here if they also have rotated QR codes
}

ADJUSTMENTS = {
    'A': {'vp': 0,   'l': 100, 'd': 50, 'angle': -2},
    'B': {'vp': -40,  'l': 0, 'd': 230, 'angle': 1},
    'C': {'vp': -30,  'l': 200, 'd': 430, 'angle': 3},
    'D': {'vp': 0, 'l': 500, 'd': 0,   'angle': 2}
}

MASTER_TOP_CROP = 700
MASTER_BOTTOM_CROP = 200
FINAL_X_SHIFT = -50
FINAL_Y_SHIFT = 200

# --- Drawing Style Configuration (Copied from Slave) ---
DRAWING_STYLES = {
    "line_color_bgr": (255, 0, 0), "text_color_bgr": (0, 0, 255), "bg_color_bgr": (255, 255, 255),
    "line_thickness": 30, "font_scale": 3, "font_thickness": 5
}

# --- Image Joining Parameters ---
JOIN = {
    'top_horizontal_shift': 110, 'top_top_crop': 10, 'top_bottom_crop': 370,
    'bottom_horizontal_shift': 0, 'bottom_top_crop': 50, 'bottom_bottom_crop': 10,
    'padding_color': (255, 255, 255) # White padding
}

# --- Final Coordinate Transformation ---
REAL_DISTANCE_CM = 105
PIXEL_POINT_1 = 4611.25
PIXEL_POINT_2 = 3456.75

# # --- Module Definitions ---
# MODULE_DIMENSIONS = {
#     'Sorting': [71, 80], 'Standard5': [71, 80], 'Standard6': [71.2, 75],
#     'Robot_arm1': [71, 140], 'Standard7': [71.2, 80], 'Warehouse_kocke': [71, 140],
#     'Engraving': [75, 71], 'Extended_conveyor': [71, 140], 'Quality_control': [71.5, 75],
#     'Robot_arm2': [80, 71], 'Standard1': [75, 71], 'Warehouse_gravirne': [71.5, 80],
#     'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [71, 80], 'Standard4': [71.2, 75]
# }

MODULE_DIMENSIONS = {
    'Sorting': [71, 80], 'Standard5': [71, 80], 'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 80], 'Standard7': [71.2, 80], 'Warehouse_kocke': [71, 140],
    'Engraving': [71, 80], 'Extended_conveyor': [71, 135], 'Quality_control': [80, 71.5],
    'Robot_arm2': [71.5, 80], 'Standard1': [71, 75], 'Warehouse_gravirne': [71.2, 140],
    'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [71, 80], 'Standard4': [71.2, 80]
}

# MODULE_NAMES = {
#     '00': 'Sorting', '02': 'Standard6', 
#     '04': 'Robot_arm1', '03': 'Warehouse_gravirne', '01': 'Standard4', 
#     #'04': 'Standard7', '03': 'Robot_arm1', '14': 'Warehouse_gravirne', '01': 'Standard5', '15': 'Standard4' 
#     '06': 'Warehouse_kocke', '05': 'Engraving', '07': 'Extended_conveyor',
#     '08': 'Quality_control', '09': 'Robot_arm2', '10': 'Standard1',  
#     '12': 'Standard2', '13': 'AGV', '11': 'Standard3', 
# }

MODULE_NAMES = {
    '00': 'Sorting', 
    '01': 'Standard4', 
    '02': 'Warehouse_gravirne',
    '03': 'Robot_arm2',
    '04': 'Robot_arm1', 
    '05': 'Engraving',
    '06': 'Warehouse_kocke',  
    '07': 'Extended_conveyor',
    '08': 'Quality_control',  
    '09': 'Standard6', 
    '10': 'Standard1', 
    '11': 'Standard3',
    '12': 'Standard2', 
    '13': 'AGV',  
    '14': 'Standard7',
    '15': 'Standard5'
}

DEFAULT_MODULE_VALUES = {
    'Standard1': ["/", "/", "/"], 'Standard2': ["/", "/", "/"], 'Standard3': ["/", "/", "/"],
    'Robot_arm2': ["/", "/", "/"], 'Warehouse_kocke': ["/", "/", "/"], 'Engraving': ["/", "/", "/"],
    'Extended_conveyor': ["/", "/", "/"], 'Quality_control': ["/", "/", "/"], 'Sorting': ["/", "/", "/"],
    'AGV': ["/", "/", "/"], 'Standard4': ["/", "/", "/"], 'Standard5': ["/", "/", "/"],
    'Standard6': ["/", "/", "/"], 'Standard7': ["/", "/", "/"], 'Robot_arm1': ["/", "/", "/"],
    'Warehouse_gravirne': ["/", "/", "/"]
}
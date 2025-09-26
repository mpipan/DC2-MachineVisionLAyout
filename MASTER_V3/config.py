import numpy as np
import cv2

# --- General Settings ---
LOG_LEVEL = "INFO"

# --- File and Directory Paths ---
BASE_PATH = "/home/cameramodule/Desktop"
CAPTURED_PATH = f"{BASE_PATH}/captured"
RECEIVED_PATH = f"{BASE_PATH}/received"
COMBINED_PATH = f"{BASE_PATH}/combined"

# File path for the undrawn stitched image received from the slave
SLAVE_UNDRAWN_IMAGE_PATH = f"{RECEIVED_PATH}/zdruzena_slika_slave.jpg"

# Slave file names (now only used for incoming data)
# NOTE: The slave now only sends coordinates, not pre-drawn images.
# These variables are kept for historical context.
SLAVE_IMAGE_WITH_MODULES_PATH = f"{RECEIVED_PATH}/zdruzena_slika_slave_z_moduli.jpg"
SLAVE_COORDS_PATH = f"{RECEIVED_PATH}/koordinate.json"

# Master file names
MASTER_IMAGE_PATH = f"{CAPTURED_PATH}/zdruzena_slika_master.jpg"
MASTER_IMAGE_WITH_MODULES_PATH = f"{CAPTURED_PATH}/rezultat.jpg"
MASTER_COORDS_PATH = f"{CAPTURED_PATH}/koordinate_master.json"
MASTER_COORDS_SCALED_PATH = f"{CAPTURED_PATH}/koordinate_master_skalirane.json"

# Combined file names
COMBINED_IMAGE_PATH = f"{COMBINED_PATH}/combined.jpg"
COMBINED_IMAGE_RESIZED_PATH = f"{COMBINED_PATH}/combined_resized.jpg"
COMBINED_COORDS_PATH = f"{COMBINED_PATH}/combined_koordinate.json"
COMBINED_CONVERTED_COORDS_PATH = f"{COMBINED_PATH}/combined_converted_coordinates.json"

# Final output for ThingsBoard
FINAL_IMAGE_PATH = f"{COMBINED_PATH}/final_result.jpg"
FINAL_COORDS_IN_CM_PATH = f"{COMBINED_PATH}/final_coords_cm.json"

# --- MQTT & ThingsBoard Settings ---
# The master is a client to the slave's MQTT broker
SLAVE_IP = '192.168.9.117'
MQTT_PORT = 1883
MQTT_COMMAND_TOPIC = "camera/command"
# NEW: The master now expects raw coordinates on this topic
MQTT_IMAGES_TOPIC = "camera/coordinates" 
THINGSBOARD_IP = '192.168.9.108'
THINGSBOARD_ACCESS_TOKEN = 'your_thingsboard_access_token'
THINGSBOARD_IMAGE_ATTRIBUTE = 'camera_image'
THINGSBOARD_INITIAL_BACKOFF = 1 # seconds
THINGSBOARD_MAX_RETRIES = 5

# --- Hardware Settings for Master USB Cameras ---
CAMERA_DEVICE_PATHS = {
    'A': "/dev/video6",
    'B': "/dev/video4",
    'C': "/dev/video2",
    'D': "/dev/video0"
}
PREFERRED_SIZES = [(3840, 3104), (3840, 2160), (3264, 2448)]
WARMUP_FRAMES = 8

# --- Image Stitching Settings ---
# Master images are now processed and stitched on the master side
MASTER_ADJUSTMENTS = {
    'A': {'vp': 250, 'l': 0, 'd': 0, 'angle': 0.0},
    'B': {'vp': 0, 'l': 0, 'd': 0, 'angle': 0.0},
    'C': {'vp': 220, 'l': 0, 'd': 0, 'angle': 0.0},
    'D': {'vp': 0, 'l': 0, 'd': 0, 'angle': 0.0}
}
MASTER_CROP_TOP = 200
MASTER_CROP_BOTTOM = 0
MASTER_FINAL_X_SHIFT = -50
MASTER_FINAL_Y_SHIFT = -2120

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
    'Sorting': [71.2, 75], 'Standard5': [70, 65], 'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 140], 'Standard7': [71.2, 80], 'Warehouse_kocke': [140, 71],
    'Engraving': [75, 71], 'Extended_conveyor': [71, 135], 'Quality_control': [71.5, 75],
    'Robot_arm2': [71.5, 80], 'Standard1': [75, 71], 'Warehouse_gravirne': [71.5, 80],
    'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [75, 71], 'Standard4': [71.2, 75]
}

MODULE_NAMES = {
    '00': 'Sorting', '01': 'Standard5', '02': 'Standard6', '03': 'Robot_arm1',
    '04': 'Standard7', '06': 'Warehouse_kocke', '05': 'Engraving', '07': 'Extended_conveyor',
    '08': 'Quality_control', '09': 'Robot_arm2', '10': 'Standard1', '11': 'Warehouse_gravirne',
    '12': 'Standard2', '13': 'AGV', '14': 'Standard3', '15': 'Standard4'
}

# --- Calibration Settings ---
REAL_DISTANCE_CM = 105
PIXEL_POINT_1 = 4611.25
PIXEL_POINT_2 = 3456.75

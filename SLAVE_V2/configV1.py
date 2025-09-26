import cv2
import numpy as np

# --- General Settings ---
LOG_LEVEL = "INFO"

# --- File and Directory Paths ---
BASE_PATH = "home/slave/SLAVE_V2"
OUTPUT_PATH = f"{BASE_PATH}/output"

# --- Network Settings ---
MASTER_IP = '192.168.9.118'
MQTT_PORT = 1883
MQTT_COMMAND_TOPIC = "camera/command"
MQTT_IMAGES_TOPIC = "camera/images"

# --- Hardware Settings for USB Cameras ---
# Map a logical name to a system device path.
# Use 'ls /dev/video*' to see your cameras.
CAMERA_DEVICE_PATHS = {
    'A': "/dev/video4",
    'B': "/dev/video2",
    'C': "/dev/video0",
    'D': "/dev/video6"
}

# Preferred resolutions to try in order.
# The code will use the highest one that the camera supports.
PREFERRED_SIZES = [(3840, 2160), (1920, 1080), (1280, 720)]
WARMUP_FRAMES = 5 # Number of frames to discard to allow camera to adjust exposure.

# --- Image Processing Parameters ---
# Define the rotation for each camera after capture.
CAMERA_ROTATIONS = {
    'A': cv2.ROTATE_90_CLOCKWISE,
    'B': cv2.ROTATE_90_CLOCKWISE,
    'C': cv2.ROTATE_90_CLOCKWISE,
    'D': cv2.ROTATE_90_CLOCKWISE,
}

QR_CODE_REAL_SIZE_MM = 10.0

# Vertical and horizontal adjustments for each camera image before stitching
# vp = vertical shift, l = left crop, d = right crop, angle = fine rotation
# ADJUSTMENTS = {
#     'A': {'vp': 0,    'l': 0,   'd': 320, 'angle': 3.0},
#     'B': {'vp': 0,    'l': 420, 'd': 130, 'angle': 0.0},
#     'C': {'vp': 90,   'l': 130, 'd': 370, 'angle': -1.0},
#     'D': {'vp': 10,   'l': 570, 'd': 0,   'angle': 0.0}
# }

ADJUSTMENTS = {
    'A': {'vp': 50,    'l': 0,   'd': 0, 'angle': 0.0},
    'B': {'vp': 0,    'l': 250, 'd': 0, 'angle': 0.0},
    'C': {'vp': 40,   'l': 500, 'd': 0, 'angle': 0.0},
    'D': {'vp': 0,   'l': 700, 'd': 0,   'angle': 0.0}
}

# Initial vertical cropping applied to all images
TOP_CROP = 300
BOTTOM_CROP = 0

# Final coordinate adjustments for aligning with the master image
FINAL_X_SHIFT = 270
FINAL_Y_SHIFT = -2120

# --- Module Definitions ---
MODULE_DIMENSIONS = {
    'Sorting': [71.2, 75], 'Standard5': [70, 65], 'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 140], 'Standard7': [71.2, 80], 'Warehouse_kocke': [140, 71],
    'Engraving': [75, 71], 'Extended_conveyor': [71, 135], 'Quality_control': [71.5, 75],
    'Robot_arm2': [71.5, 80], 'Standard1': [75, 71], 'Warehouse_gravirne': [71.5, 80],
    'Standard2': [71, 75], 'AGV': [71.2, 80], 'Standard3': [75, 71], 'Standard4': [71.2, 75]
}

MODULE_NAMES = {
    '00': 'Sorting', '01': 'Standard5', '09': 'Standard6', '02': 'Robot_arm1',
    '04': 'Standard7', '06': 'Warehouse_kocke', '05': 'Engraving', '07': 'Extended_conveyor',
    '08': 'Quality_control', '03': 'Robot_arm2', '10': 'Standard1', '14': 'Warehouse_gravirne',
    '12': 'Standard2', '13': 'AGV', '11': 'Standard3', '15': 'Standard4'
}

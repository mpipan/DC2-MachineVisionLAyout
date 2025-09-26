import logging
import RPi.GPIO as gp
import os
import cv2

# --- General Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- GPIO Setup ---
# A helper function to initialize GPIO pins
def setup_gpio():
    """Initializes GPIO pins."""
    try:
        gp.setwarnings(False)
        gp.setmode(gp.BOARD)
        gp.setup(7, gp.OUT)
        gp.setup(11, gp.OUT)
        gp.setup(12, gp.OUT)
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, False)
        logger.info("GPIO pins initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize GPIO pins: {e}")

# A helper function to select the camera using I2C and GPIO multiplexer
def setup_camera_mux(camera_name):
    """Select a specific camera using I2C and GPIO settings."""
    if camera_name not in camera_settings:
        logger.error(f"Invalid camera name: {camera_name}")
        return False
    
    settings = camera_settings[camera_name]
    if os.system(settings['i2c']) != 0:
        logger.error(f"Failed to set I2C for camera {camera_name}")
        return False

    gp.output(7, settings['gpio'][0])
    gp.output(11, settings['gpio'][1])
    gp.output(12, settings['gpio'][2])
    time.sleep(0.5)  # Delay to allow the hardware to settle
    return True

# --- Network Settings ---
MASTER_IP = '192.168.9.118'
SLAVE_IP = '192.168.9.131'
PORT = 1883
USERNAME = "Module10_MQTT"
PASSWORD = "Module10MQTT"
RETRY_LIMIT = 5

# --- Camera & Image Processing Parameters ---
camera_settings = {
    'B': {'i2c': "i2cset -y 1 0x70 0x00 0x04", 'gpio': (False, False, True), 'rotation': cv2.ROTATE_90_COUNTERCLOCKWISE},
    'D': {'i2c': "i2cset -y 1 0x70 0x00 0x05", 'gpio': (True, False, True), 'rotation': cv2.ROTATE_90_CLOCKWISE},
    'A': {'i2c': "i2cset -y 1 0x70 0x00 0x06", 'gpio': (False, True, False), 'rotation': cv2.ROTATE_90_CLOCKWISE},
    'C': {'i2c': "i2cset -y 1 0x70 0x00 0x07", 'gpio': (True, True, False), 'rotation': cv2.ROTATE_90_CLOCKWISE},
}

SHUTTER_SPEED = 50000
GAIN = 1.5
LENS_POSITION = 0.0

crop_top = 100
crop_bottom = 200

# --- Module Dimensions and Mapping ---
moduli_dim = {
    'Sorting': [71.2, 75],
    'Standard5': [70, 65],
    'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 140],
    'Standard7': [71.2, 75],
    'Warehouse_kocke': [140, 71],
    'Engraving': [75,  71],
    'Extended_conveyor': [71, 135],
    'Quality_control': [71.5, 75],
    'Robot_arm2': [71.5, 80],
    'Standard1': [75, 71],
    'Warehouse_gravirne': [71.5, 80],
    'Standard2': [71, 75],
    'AGV': [71.2, 80],
    'Standard3': [75, 71],
    'Standard4': [71.2, 75]
}

names = {
    '00': 'Sorting',
    '01': 'Standard5',
    '09': 'Standard6',
    '02': 'Robot_arm1',
    '04': 'Standard7',
    '06': 'Warehouse_kocke',
    '05': 'Engraving',
    '07': 'Extended_conveyor',
    '08': 'Quality_control',
    '03': 'Robot_arm2',
    '10': 'Standard1',
    '14': 'Warehouse_gravirne',
    '12': 'Standard2',
    '13': 'AGV',
    '11': 'Standard3',
    '15': 'Standard4'
}


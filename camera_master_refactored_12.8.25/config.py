import logging
import RPi.GPIO as gp
import os

# --- General Configuration ---
# Use an explicit logger for better control over log levels and output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MQTT Settings ---
MQTT_BROKER = "localhost"  
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# --- Network Settings ---
# Note: You may need to replace this with the slave's actual IP
SLAVE_IP = "192.168.1.100" 

# --- Retry Logic ---
RETRY_LIMIT = 5

# --- Camera & Image Processing Parameters ---
image_px = 2000
crop_top = 100
crop_bottom = 200

# Camera-specific vertical pixel shifts (Vp)
Avp = 0
Bvp = 4
Cvp = 0
Dvp = 0

# Camera-specific rotation angles
A_rotation = 0
B_rotation = -1.3
C_rotation = 0
D_rotation = -0.8

# Camera capture settings
SHUTTER_SPEED = 50000
GAIN = 1.5
LENS_POSITION = 0.0

# --- Module Dimensions and Mapping ---
moduli_dim = {
    'Sorting': [71.2, 75],
    'Standard4': [70, 65],
    'Standard6': [71.2, 75],
    'Warehouse_gravirne': [71.2, 140],
    'Robot_arm1': [71.2, 80],
    'Warehouse_kocke': [140, 71],
    'Engraving': [75, 71],
    'Extended_conveyor': [71, 135],
    'Quality_control': [71.5, 75],
    'Robot_arm2': [71.5, 80],
    'Standard1': [75, 71],
    'Standard7': [71.5, 80],
    'Standard2': [71, 75],
    'AGV': [71.2, 80],
    'Standard3': [75, 71],
    'Standard5': [71.2, 75]
}

names = {
    '00': 'Sorting',
    '01': 'Standard4',
    '02': 'Standard6',
    '03': 'Warehouse_gravirne',
    '04': 'Robot_arm1',
    '06': 'Warehouse_kocke',
    '05': 'Engraving',
    '07': 'Extended_conveyor',
    '08': 'Quality_control',
    '09': 'Robot_arm2',
    '10': 'Standard1',
    '14': 'Standard7',
    '12': 'Standard2',
    '13': 'AGV',
    '11': 'Standard3',
    '15': 'Standard4'
}

# --- QR Code Calibration Parameters ---
# The known side length of the square QR codes in millimeters
QR_CODE_SIZE_MM = 20.0
# The default conversion factor from pixels to centimeters, used if QR codes are not found
DEFAULT_CONVERSION_FACTOR = 0.065 
# Coordinates of QR codes on each of the 4 cameras in pixels.
Al = [178, 147]
Ad = [178, 1693]
Bl = [1831, 193]
Bd = [1831, 1698]
Cl = [1776, 178]
Cd = [1776, 1700]
Dl = [182, 187]
Dd = [182, 1686]

# --- Plotting Parameters (for matplotlib) ---
dpi = 100
tick_step_cm = 50

# --- GPIO and Camera Configuration ---
# GPIO Pin Configuration
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Camera I2C and GPIO settings
camera_settings = {
    'A': {'i2c': 'i2cset -y 1 0x70 0x00 0x01', 'gpio': [True, False, True]},
    'B': {'i2c': 'i2cset -y 1 0x70 0x00 0x02', 'gpio': [False, True, True]},
    'C': {'i2c': 'i2cset -y 1 0x70 0x00 0x04', 'gpio': [True, True, False]},
    'D': {'i2c': 'i2cset -y 1 0x70 0x00 0x08', 'gpio': [True, True, True]}
}

def setup_gpio():
    """Initializes GPIO pins."""
    try:
        gp.output(7, False)
        gp.output(11, False)
        gp.output(12, False)
    except Exception as e:
        logger.error(f"Failed to initialize GPIO pins: {e}")

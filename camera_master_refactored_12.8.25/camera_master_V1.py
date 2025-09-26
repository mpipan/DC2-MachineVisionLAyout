import itertools
import numpy as np
import matplotlib.pyplot as plt
import cv2
import zxingcpp
from PIL import Image
import time
import os
import imutils
import paho.mqtt.client as mqtt
import json
import logging
import RPi.GPIO as gp
import base64
import math
import imutils
from scipy.optimize import minimize
import socket
import pickle
import struct
import threading
from threading import Lock
from queue import Queue
import io
from matplotlib.ticker import FixedLocator

# Nastavitev logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# cameraslave
# CMbullet5282CM

#Omogoči Mosquitto service pred zagonom
#sudo systemctl enable mosquitto
#sudo systemctl start mosquitto

# Preveri status
#sudo systemctl status mosquitto


print("Script has been started!!!")

# MQTT nastavitve
#MQTT_BROKER = "localhost"  
MQTT_BROKER = "192.168.9.118"  
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

class ImageManager:
    def __init__(self):
        self.remote_images = {}
        self.lock = Lock()
        
    # def store_remote_image(self, camera_name, image):
        # with self.lock:
            # self.remote_images[camera_name] = image
    
    def store_remote_image(self, key, data):
        with self.lock:
            self.remote_images[key] = data
            
    def get_remote_image(self, camera_name):
        with self.lock:
            return self.remote_images.get(camera_name)

class MQTTHandler:
    def __init__(self, image_manager):
        self.client = mqtt.Client()
        self.image_manager = image_manager
        self.setup_client()
        
    def setup_client(self):
        # self.client.username_pw_set(USERNAME, PASSWORD)  # Zakomentiraj to vrstico
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
    def on_connect(self, client, userdata, flags, rc):
        logger.info("Connected to MQTT broker with result code: " + str(rc))
        self.client.subscribe('camera/images')
        
    def start(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            logger.info("MQTT handler started successfully")
        except Exception as e:
            logger.error(f"Failed to start MQTT handler: {e}")
            raise
        
    def request_images(self):
        self.client.publish('camera/command', 'capture')
        logger.info("Sent capture command to slave")
               
    def on_message(self, client, userdata, msg):
        """Handles incoming MQTT messages."""
        logger.info(f"Message received on topic {msg.topic}")
        
        if msg.topic == 'camera/images':
            try:
                payload = json.loads(msg.payload)
                logger.debug(f"Received payload: {payload}")  # Debugging
                
                # Decode the base64 image
                image_bytes = base64.b64decode(payload['zdruzena_brez_nic'])
                nparr = np.frombuffer(image_bytes, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Decode the base64 image
                image_bytes = base64.b64decode(payload['rezultat_z_moduli'])
                nparr = np.frombuffer(image_bytes, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
     
                if image is not None:
                    # Store the image and metadata
                    self.image_manager.store_remote_image('zdruzena_brez_nic', image)
                    self.image_manager.store_remote_image('rezultat_z_moduli', image)
                    self.image_manager.store_remote_image('koordinate', payload.get('koordinate', {}))
                    self.image_manager.store_remote_image('koordinate_skalirane', payload.get('koordinate_skalirane', {}))
                    self.image_manager.store_remote_image('koordinate_skalirane_dvignjene', payload.get('koordinate_skalirane_dvignjene', {}))
                    
                    logger.info("Successfully processed and stored remote image and metadata")
                else:
                    logger.warning("Failed to decode image")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                logger.exception("Full traceback:")
                

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection with code {rc}. Will attempt to reconnect.")


# Omrežne nastavitve
MASTER_IP = '192.168.9.118'  
SLAVE_IP = '192.168.9.131'  
USERNAME = "Module10_MQTT"
PASSWORD = "Module10MQTT"
PORT = 1883

# Add a custom JSON encoder to handle NumPy arrays and other non-serializable types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # Convert ndarray to lists
        if isinstance(obj, np.integer):
            return int(obj)  # Convert numpy integers to Python integers
        if isinstance(obj, np.floating):
            return float(obj)  # Convert numpy floats to Python floats
        if isinstance(obj, np.bool_):
            return bool(obj)  # Convert numpy booleans to Python booleans
        return super().default(obj)  # Let the base class handle anything else

def recieve_photos():
    logger.info("Starting master camera service...")

    # Initialize handlers
    image_manager = ImageManager()
    mqtt_handler = MQTTHandler(image_manager)

    try:
        mqtt_handler.start()
        logger.info("MQTT handler started")

        attempt_success = False
        attempt = 0
        max_attempts = 20  # Prevent infinite loops

        while attempt < max_attempts and not attempt_success:
            try:
                # Request images from slave
                mqtt_handler.request_images()
                
                # Wait briefly for images to arrive
                time.sleep(5)  

                # Get received images
                remote_images = image_manager.remote_images 

                # More robust image validation
                required_images = [
                    'zdruzena_brez_nic', 
                    'rezultat_z_moduli', 
                    'koordinate', 
                    'koordinate_skalirane', 
                    'koordinate_skalirane_dvignjene'
                ]

                # Check if all required images are present and not None/empty
                if all(
                    key in remote_images and 
                    remote_images[key] is not None and 
                    (not isinstance(remote_images[key], (np.ndarray, list)) or len(remote_images[key]) > 0)
                    for key in required_images
                ):
                    # Safely extract images
                    zdruzena_brez_nic = remote_images['zdruzena_brez_nic']
                    rezultat_z_moduli = remote_images['rezultat_z_moduli']
                    koordinate = remote_images.get('koordinate', {})
                    koordinate_skalirane = remote_images.get('koordinate_skalirane', {})
                    koordinate_skalirane_dvignjene = remote_images.get('koordinate_skalirane_dvignjene', {})

                    # Save the images (rest of the code remains the same)
                    save_path = "/home/cameramodule/Desktop/received/zdruzena_slika_slave.jpg"
                    cv2.imwrite(save_path, zdruzena_brez_nic)
                    logger.info(f"Saved zdruzena slika to {save_path}")
                      
                    # Save the stitched image from slave
                    save_path_moduli = '/home/cameramodule/Desktop/received/zdruzena_slika_slave_z_moduli.jpg'
                    cv2.imwrite(save_path_moduli, rezultat_z_moduli)
                    logger.info(f"Saved zdruzena slika to {save_path_moduli}")
                    
                    
                    koordinate_save_path = "/home/cameramodule/Desktop/received/koordinate.json"
                    # Save the coordinates as a JSON file using our custom encoder
                    with open(koordinate_save_path, "w") as f:
                        json.dump(koordinate, f, indent=4, cls=NumpyEncoder)
                    logger.info(f"Saved coordinates to {koordinate_save_path}")
                    
                    koordinate_skalirane_save_path = "/home/cameramodule/Desktop/received/koordinate_skalirane.json"
                    # Save the coordinates as a JSON file using our custom encoder
                    with open(koordinate_skalirane_save_path, "w") as f:
                        json.dump(koordinate_skalirane, f, indent=4, cls=NumpyEncoder)
                    logger.info(f"Saved coordinates to {koordinate_skalirane_save_path}")       
                    
                    koordinate_skalirane_dvignjene_save_path = "/home/cameramodule/Desktop/received/koordinate_skalirane_dvignjene.json"
                    # Save the coordinates as a JSON file using our custom encoder
                    with open(koordinate_skalirane_dvignjene_save_path, "w") as f:
                        json.dump(koordinate_skalirane_dvignjene, f, indent=4, cls=NumpyEncoder)
                    logger.info(f"Saved coordinates to {koordinate_skalirane_dvignjene_save_path}")
                    
                    # Mark success
                    attempt_success = True

                else:
                    logger.warning("Some images are missing or invalid. Retrying...")
                    attempt += 1

            except Exception as e:
                logger.error(f"Error receiving photos: {e}")
                attempt += 1
                logger.info(f"Retrying... Attempt {attempt + 1}")
                time.sleep(5)  # Retry after a short delay

    except Exception as e:
        logger.error(f"Error in master camera service: {e}")
        logger.exception("Full traceback:")
                
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.exception("Full traceback:")
    finally:
        mqtt_handler.client.loop_stop()
        logger.info("MQTT handler stopped")

RETRY_LIMIT = 5  # Maximum number of retries
INITIAL_BACKOFF = 0.1  # Initial backoff time in seconds

logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.ERROR)


# GPIO Setup
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Camera settings mapping
camera_settings = {
    'A': {'i2c': "i2cset -y 1 0x70 0x00 0x04", 'gpio': (False, False, True)},
    'B': {'i2c': "i2cset -y 1 0x70 0x00 0x05", 'gpio': (True, False, True)},
    'C': {'i2c': "i2cset -y 1 0x70 0x00 0x06", 'gpio': (False, True, False)},
    'D': {'i2c': "i2cset -y 1 0x70 0x00 0x07", 'gpio': (True, True, False)},
}

def kamera(name, save=True):
    """Activate the specified camera and capture an image."""
    if name not in camera_settings:
        print('Wrong camera name')
        return None

    settings = camera_settings[name]
    print(f'Start getting image from the camera {name}')
    os.system(settings['i2c'])
    gp.output(7, settings['gpio'][0])
    gp.output(11, settings['gpio'][1])
    gp.output(12, settings['gpio'][2])

    return capture(name, save)

def capture(name, save):
    """Capture an image using the camera and return it."""
    filename = '1.jpg'
    cmd = f'libcamera-jpeg -o {filename} --nopreview --autofocus-mode=manual --lens-position=0.0 --shutter 50000 --gain 1.5'
    path = '/home/cameramodule/Desktop/captured'
    os.chdir(path)
    os.system(cmd)
    image = cv2.imread(os.path.join(path, filename))
    if save==True:
        cv2.imwrite(f'{name}.png',image)
    return image

def crop_left_right(slika, levo, desno):
    """Crop the image from the left and right sides."""
    height, width = slika.shape[:2]

    # Calculate the new width after cropping
    new_width = width - (levo + desno)
    left_crop = max(0, levo)
    right_crop = max(0, desno)

    # Perform horizontal cropping
    cropped_image = slika[:, left_crop:width - right_crop]

    return cropped_image

def load_and_rotate_images(crop_top, crop_bottom, unidstort=False):
    """Load, rotate, and crop images."""
    input_A = kamera('A')
    input_B = kamera('B')
    input_C = kamera('C')
    input_D = kamera('D')
    A_ud  = input_A
    B_ud  = input_B
    C_ud  = input_C
    D_ud  = input_D

    slikaA = cv2.rotate(A_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaB = cv2.rotate(B_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaC = cv2.rotate(C_ud, cv2.ROTATE_90_CLOCKWISE)
    slikaD = cv2.rotate(D_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)

    slikaAf = imutils.rotate(slikaA, angle=0)
    slikaBf = imutils.rotate(slikaB, angle=-1.3)
    slikaCf = imutils.rotate(slikaC, angle=0)
    slikaDf = imutils.rotate(slikaD, angle=-0.8)

    A = crop_img(premik(slikaAf,Avp), crop_top, crop_bottom)
    B = crop_img(premik(slikaBf, Bvp), crop_top, crop_bottom)
    C = crop_img(premik(slikaCf, Cvp), crop_top, crop_bottom)
    D = crop_img( premik(slikaDf, Dvp), crop_top, crop_bottom)

    return A, B, C, D

def background(slikaA, slikaB, slikaC, slikaD):
    """Load, rotate, and crop images."""
    A = crop_left_right(slikaA, Al, Ad)
    B = crop_left_right(slikaB, Bl, Bd)
    C = crop_left_right(slikaC, Cl, Cd)
    D = crop_left_right(slikaD, Dl, Dd)

    return cv2.hconcat([A, B, C, D])

def premik(slika, vp):
    padding = 300
    """Add white spaces to the top and bottom of the image, center the original image, and move it up or down within the new height."""
    height, width = slika.shape[:2]

    total_height = 2* padding + height
    # Calculate padding
    if total_height <= height:
        raise ValueError("Total height must be greater than the height of the original image.")

    # Total padding required
    total_padding = total_height - height

    # Calculate top and bottom padding
    top_padding = total_padding // 2
    bottom_padding = total_padding - top_padding

    # Create a white canvas of the total height and original width
    white_canvas = np.ones((total_height, width, 3), dtype=np.uint8) * 255

    # Place the original image in the center of the white canvas
    white_canvas[top_padding:top_padding + height, :] = slika

    # Calculate the shift amount
    shift_amount = int(vp)

    # Apply vertical shift (move the image up or down within the total height)
    result_image = np.roll(white_canvas, -shift_amount, axis=0)

    return result_image

moduli_dim = {
    'Sorting': [71.2, 75],
    'Standard5': [70, 65],
    'Standard6': [71.2, 75],
    'Robot_arm1': [71.2, 140],
    'Standard7': [71.2, 80],
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

default_values = {
    'Standard1': ["/", "/", "/"],
    'Standard2': ["/", "/", "/"],
    'Standard3': ["/", "/", "/"],
    'Robot_arm2': ["/", "/", "/"],
    'Warehouse_kocke': ["/", "/", "/"],
    'Engraving': ["/", "/", "/"],
    'Extended_conveyor': ["/", "/", "/"],
    'Quality_control': ["/", "/", "/"],
    'Sorting': ["/", "/", "/"],
    'AGV': ["/", "/", "/"],
    'Standard4': [210, 400, 0],
    'Standard5': [400, 300, 0],
    'Standard6': [290, 400, 0],
    'Standard7': [370, 400, 0],
    'Robot_arm1': [450, 400, 0],
    'Warehouse_gravirne': ["/", "/", "/"]
}

names = {
    '00': 'Sorting',
    '01': 'Standard5',
    '02': 'Standard6',
    '03': 'Robot_arm1',
    '04': 'Standard7',
    '06': 'Warehouse_kocke',
    '05': 'Engraving',
    '07': 'Extended_conveyor',
    '08': 'Quality_control',
    '09': 'Robot_arm2',
    '10': 'Standard1',
    '14': 'Warehouse_gravirne',
    '12': 'Standard2',
    '13': 'AGV',
    '11': 'Standard3',
    '15': 'Standard4'
}

def renaming(name):
    """Map QR code numbers to module names."""
    return names.get(name, 'Unknown')

def calculate_distance(point1, point2):
    """
    Parameters:
    point1 (tuple or list): Coordinates of the first point (x1, y1).
    point2 (tuple or list): Coordinates of the second point (x2, y2).: The distance between the two points.
    """
    x1, y1 = point1
    x2, y2 = point2
    distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return distance

def decode(image):
    """Decode barcodes from an image and return their positions."""
    if image is None:
        raise ValueError(f"Image not found or unable to read: {image}")

    print(image.shape[0])
    print(image.shape[1])
    print(type(image))
    #cv2.imshow("show image", image)
    #cv2.waitKey(0)

    barcodes = zxingcpp.read_barcodes(image)
    positions = {}

    for barcode in barcodes:
        text = renaming(str(barcode.text))
        position_str = str(barcode.position).strip('\x00')
        pairs = position_str.split()
        output = [np.array([int(x.split('x')[0]), int(x.split('x')[1])]) for x in pairs]

        if text != 'Unknown':
            positions[text] = output

    if not barcodes:
        print("Could not find any barcode.")
        return None
    else:
        return positions

def conversion_factor(codes,qr_code_size): # each pixel corresponds to X mm -> take the average of the four distances and divide qr_code_size by that average to return the conversion factor.
    if codes:
        lenghts = []
        for output in codes.values():
            s1 = calculate_distance(output[0], output[1]) # Top edge
            s2 = calculate_distance(output[1], output[2]) # Right edge
            s3 = calculate_distance(output[2], output[3]) # Bottom edge
            s4 = calculate_distance(output[3], output[0]) # Left edge
            # calculate_distance computes the Euclidean distance between two points
            lenghts.extend([s1, s2, s3, s4])

        return qr_code_size/(sum(lenghts) / len(lenghts)) # Computes the average side length in pixels.
    else:
        return 0.06504286264676926 # If codes is empty, return a default conversion factor

def skaliranje(oglisca_qr, moduli_dim, a_koda, conversion_factor):
    """Transform coordinates from QR code units to module dimensions in millimeters."""
    transformirane = {}
    for modul, oglisca in oglisca_qr.items(): # oglisca_qr: Dictionary containing QR code coordinates (corners of detected QR codes in the image)
        if modul not in moduli_dim: # moduli_dim: Dictionary mapping QR codes to their real-world dimensions [width, height] in millimeters
            print(f"Module {modul} not found in moduli_dim")
            continue

        t1, t2, t3, t4 = oglisca # t1 = Top-left    t2 = Top-right  t3 = Bottom-right   t4 = Bottom-left

        # Calculate the scaling factors in millimeters
        ky = moduli_dim[modul][0] / a_koda * conversion_factor # ky = Scaling factor for height (vertical distance) 
        kx = moduli_dim[modul][1] / a_koda * conversion_factor # kx = Scaling factor for width (horizontal distance)
        # a_koda: The real-world size of the QR code (a known reference measurement)
        # conversion_factor: A scaling factor used to convert pixel measurements into real-world dimensions

        # Perform the initial scaling of the QR code points
        ry = (t2 - t1) * ky
        rx = (t4 - t1) * kx

        tt1 = t1 * conversion_factor
        tt2 = tt1 + ry
        tt4 = tt1 + rx
        tt3 = tt4 + ry

        # To ensure perpendicularity, we need to correct tt3
        # Calculate the vector tt2 -> tt3 and ensure it's perpendicular to tt1 -> tt4
        v1 = tt2 - tt1  # Vector along one edge
        v2 = tt4 - tt1  # Vector along the adjacent edge

        # Calculate the perpendicular projection of v2 onto v1
        dot_product = np.dot(v1, v2)
        v1_magnitude_sq = np.dot(v1, v1)

        if v1_magnitude_sq != 0:
            projection_factor = dot_product / v1_magnitude_sq
            projection = projection_factor * v1

            # Correct the tt3 position by ensuring perpendicularity
            tt3_corrected = tt2 + (v2 - projection)
            
            # Update the transformed coordinates
            transformirane[modul] = [tt1, tt2, tt3_corrected, tt4]
        else:
            # If the magnitude is zero, we skip the correction and use the original transformation
            transformirane[modul] = [tt1, tt2, tt3, tt4]

    return transformirane
    
def calculate_module_properties(oglisca_real):
    """Calculate the center coordinates and absolute angles of modules."""
    module_properties = {}

    for modul, points in oglisca_real.items():
        tocke = np.array(points)

        S = np.round((tocke[0] + tocke[2]) / 2, decimals=0)
        center_coordinates = S.tolist()

        t1, t2 = points[:2]
        dx = t2[0] - t1[0]
        dy = t2[1] - t1[1]
        angle_rad = np.arctan2(dy, dx)
        angle_deg = np.round(np.degrees(angle_rad), decimals=0)
        rotation = angle_deg.item()

        module_properties[modul] = center_coordinates + [rotation]

    return module_properties

def premik_koordinat(slika1, slika2, slika3, slika4):

    """Adjust coordinates of QR codes based on image offsets and validate bounds."""
    w1 = slika1.shape[1]
    w2 = slika2.shape[1]
    w3 = slika3.shape[1]
    w4 = slika4.shape[1]
    # W = width
    
    h1 = slika1.shape[0]
    h2 = slika2.shape[0]
    h3 = slika3.shape[0]
    h4 = slika4.shape[0]
    # H = height

    kode1 = decode(slika1)
    kode2 = decode(slika2)
    kode3 = decode(slika3)
    kode4 = decode(slika4)
    # Calls the decode() function to detect QR codes in each of the four images.

    output = {}

    # Each detected QR code’s coordinates are adjusted relative to the final stitched image (kode1 - leftmost picture)
    if kode1:
        updated_dict1 = {k: [np.array([x - Al, h1-y]) for [x, y] in v] for k, v in kode1.items()}
        output.update(updated_dict1)

    if kode2:
        updated_dict2 = {k: [np.array([x + w1 -Al-Ad-Bl, h2-y ]) for [x, y] in v] for k, v in kode2.items()}
        output.update(updated_dict2)

    if kode3:
        updated_dict3 = {k: [np.array([x + w1 + w2 -Al-Ad-Bl-Bd-Cl, h3-y ]) for [x, y] in v] for k, v in kode3.items()}
        output.update(updated_dict3)

    if kode4:
        updated_dict4 = {k: [np.array([x + w1 + w2 + w3  -Al-Ad-Bl-Bd-Cl-Cd-Dl, h4-y]) for [x, y] in v] for k, v in kode4.items()}
        output.update(updated_dict4)

    max_width = w1 + w2 + w3 + w4
    max_height = max(h1, h2, h3, h4)

    # Validate That Coordinates Stay Within Bounds
    for module, coords in output.items():
        for coord in coords:
            if coord[0] < 0 or coord[0] > max_width or coord[1] < 0 or coord[1] > max_height:
                print(f"Warning: Coordinate {coord} for module {module} is out of bounds.")

    return output   # Returns a dictionary containing adjusted QR code coordinates, properly positioned in the final stitched image.


# ===========================================================================================
# ===========================================================================================

# def combine_coordinates(
    # x_offset_slave=0.0, y_offset_slave=0.0,
    # x_offset_master=0.0, y_offset_master=0.0
# ):
    # """Merge master and slave coordinate files into one, with separate offsets for each."""

    # slave_path = "/home/cameramodule/Desktop/received/koordinate.json"
    # master_path = "/home/cameramodule/Desktop/captured/koordinate_master.json"
    # output_path = "/home/cameramodule/Desktop/combined/combined_koordinate.json"

    # combined_data = {}

    # def apply_offset(data, x_off, y_off):
        # """Add offsets to all coordinates in the data."""
        # return {
            # name: [[x + x_off, y + y_off] for x, y in coords]
            # for name, coords in data.items()
        # }

    # try:
        # # Load and offset slave coordinates
        # if os.path.exists(slave_path):
            # with open(slave_path, "r") as f:
                # slave_data = json.load(f)
            # slave_data = apply_offset(slave_data, x_offset_slave, y_offset_slave)
            # combined_data.update(slave_data)
            # logger.info(f"Loaded and adjusted slave coordinates from {slave_path}")

        # # Load and offset master coordinates
        # if os.path.exists(master_path):
            # with open(master_path, "r") as f:
                # master_data = json.load(f)
            # master_data = apply_offset(master_data, x_offset_master, y_offset_master)
            # combined_data.update(master_data)
            # logger.info(f"Loaded and adjusted master coordinates from {master_path}")

        # # Save merged data
        # os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # with open(output_path, "w") as f:
            # json.dump(combined_data, f, indent=4)
        # logger.info(f"Combined coordinates saved to {output_path}")

    # except Exception as e:
        # logger.error(f"Failed to combine coordinates: {e}")



logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def combine_coordinates(
    x_offset_slave=0.0, y_offset_slave=0.0,
    x_offset_master=0.0, y_offset_master=0.0
):
    """Merge master and slave coordinate files into one, with separate offsets for each,
    and compute center + rotation angle from 4-point data.
    """

    slave_path = "/home/cameramodule/Desktop/received/koordinate.json"
    master_path = "/home/cameramodule/Desktop/captured/koordinate_master.json"
    output_path = "/home/cameramodule/Desktop/combined/combined_koordinate.json"
    converted_output_path = "/home/cameramodule/Desktop/combined/combined_converted_coordinates.json"

    combined_data = {}

    def apply_offset(data, x_off, y_off):
        """Add offsets to all coordinates in the data."""
        return {
            name: [[x + x_off, y + y_off] for x, y in coords]
            for name, coords in data.items()
        }

    def get_center_and_rotation(points):
        """Given 4 corner points, return center and approximate rotation."""
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        center_x = sum(x_coords) / len(points)
        center_y = sum(y_coords) / len(points)

        # Estimate rotation using the first two points
        dx = points[1][0] - points[0][0]
        dy = points[1][1] - points[0][1]
        angle_deg = math.degrees(math.atan2(dy, dx))

        return [center_x, center_y, angle_deg]

    try:
        # Load and offset slave coordinates
        if os.path.exists(slave_path):
            with open(slave_path, "r") as f:
                slave_data = json.load(f)
            slave_data = apply_offset(slave_data, x_offset_slave, y_offset_slave)
            combined_data.update(slave_data)
            logger.info(f"Loaded and adjusted slave coordinates from {slave_path}")

        # Load and offset master coordinates
        if os.path.exists(master_path):
            with open(master_path, "r") as f:
                master_data = json.load(f)
            master_data = apply_offset(master_data, x_offset_master, y_offset_master)
            combined_data.update(master_data)
            logger.info(f"Loaded and adjusted master coordinates from {master_path}")

        # Save original merged data
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(combined_data, f, indent=4)
        logger.info(f"Combined coordinates saved to {output_path}")

        # ---- NEW: Convert to center + rotation format ----
        converted_data = {}
        for name, corners in combined_data.items():
            if isinstance(corners, list) and len(corners) == 4:
                converted_data[name] = get_center_and_rotation(corners)
            else:
                logger.warning(f"Skipping {name}: unexpected corner format")

        # Save converted data for ThingsBoard
        with open(converted_output_path, "w") as f:
            json.dump(converted_data, f, indent=4)
        logger.info(f"Converted center+rotation data saved to {converted_output_path}")

    except Exception as e:
        logger.error(f"Failed to combine coordinates: {e}")

# ===========================================================================================
# ===========================================================================================



# izris stara 1
def izris(slika_BG, oglisca, scale_factor, output_image_name, dpi):
    """Draw the modules and their details on the image."""
    # Load the image using cv2 and flip it vertically
    img = slika_BG
    height, width = img.shape[:2]
    new_size = (int(width * scale_factor), int(height * scale_factor))
    scaled_image = cv2.resize(img, new_size, interpolation=cv2.INTER_LINEAR)

    img_flipped = cv2.flip(scaled_image, 0)

    # Convert the image from BGR to RGB format (cv2 loads in BGR by default)
    img_flipped_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)

    # Display the flipped image with inverted y-axis
    plt.imshow(img_flipped_rgb)
    ax = plt.gca()
    ax.set_aspect('equal', adjustable='box')
    ax.invert_yaxis()
    
    # izklopi skalo za x in y
    ax.axis('off')
    
    # Make the image fill the entire figure
    ax.set_position([0, 0, 1, 1])
    
    

    for modul, oglisca in oglisca.items():
        points = np.array(oglisca)
        kontx = np.append(points[:, 0], points[0, 0])
        konty = np.append(points[:, 1], points[0, 1])
        plt.plot(kontx, konty, color='blue')

        # Calculate the center of the rectangle
        center_x = np.mean(points[:, 0])
        center_y = np.mean(points[:, 1])

        # Plot the text at the center of the rectangle
        plt.text(center_x, center_y, modul, ha='center', va='center', backgroundcolor='w', color='red', fontsize=7)

    # # izklopi oznake za x in y
    # plt.xlabel('X [cm]')
    # plt.ylabel('Y [cm]')
    
    
    # Save with no border/padding
    plt.savefig(
        output_image_name,
        dpi=dpi,
        bbox_inches='tight',
        pad_inches=0
    )
    
    # this was replaced with the line above to remove all the borders
    # plt.savefig(output_image_name, dpi= dpi)
    
    plt.close()

def crop_img(img, top_crop_height, bottom_crop_height):
    height, width = img.shape[:2]

    if top_crop_height + bottom_crop_height >= height:
        print("Error: Total crop height is greater than or equal to image height.")
        return

    cropped_img = img[top_crop_height:height - bottom_crop_height, :]
    return cropped_img


#premiki slik vp = vertikalni premik, lobrezvoanje leve strani, d=obrezovanje desne strani
Avp, Al, Ad = 0, 100,130
Bvp, Bl, Bd = -64, 130, 530
Cvp, Cl, Cd = -75, 300, 658
Dvp, Dl, Dd = -130, 658, 0

# parmatetri za odstranitev distorzije, lahko se jih umeri, upoštevani če je
DIM_A=(4608, 2592)
K_A=np.array([[3438.8020055605534, 0.0, 2316.526388477198], [0.0, 3441.1085720228666, 1294.2730484632523], [0.0, 0.0, 1.0]])
D_A=np.array([[0.34055597085324346], [0.36217164784765504], [1.343430858032452], [-6.023347074564141]])

DIM_B = (4608, 2592)
K_B = np.array([[3428.697088742883, 0.0, 2320.4099976120683], [0.0, 3430.293559542795, 1278.7270751748433], [0.0, 0.0, 1.0]])
D_B = np.array([[0.352355418913848], [0.08718298216331657], [2.1071519847048172], [-5.912146159160642]])

DIM_C=(4608, 2592)
K_C=np.array([[3449.62178967297, 0.0, 2321.5227451196747], [0.0, 3450.9290338113265, 1298.1902286757636], [0.0, 0.0, 1.0]])
D_C=np.array([[0.3148648720055298], [0.7756798132781213], [-1.1492128178745855], [-1.0042523718010528]])

DIM_D=(4608, 2592)
K_D=np.array([[3456.756069032055, 0.0, 2300.4587106251483], [0.0, 3452.1114483108436, 1323.8867743126968], [0.0, 0.0, 1.0]])
D_D=np.array([[0.31515769770294283], [0.672454498621847], [-0.6633718378166686], [-1.3359630073140756]])


def take_photos():
    output_image_name = 'rezultat.jpg'
    qr_code_size = 10
    bottom_crop = 200
    top_crop = 700
    
    # Process images
    slikaA, slikaB, slikaC, slikaD = load_and_rotate_images(crop_top=top_crop, crop_bottom=bottom_crop, unidstort=False)
    zdruzena_slika_master = background(slikaA, slikaB, slikaC, slikaD)
    output_file = "/home/cameramodule/Desktop/captured/zdruzena_slika_master.jpg"  
    cv2.imwrite(output_file, zdruzena_slika_master) # V output_file shranimo zdruzena_slika_master
    logger.info(f"Zdruzena slika saved successfully as {output_file}")
        
    koordinate = premik_koordinat(slikaA, slikaB, slikaC, slikaD) # Premakne koordinate qr kod tako da so pravilno narisane na koncni sliki
    koordinate_save_path_master = "/home/cameramodule/Desktop/captured/koordinate_master.json"
    
    # Save the coordinates as a JSON file using our custom encoder
    with open(koordinate_save_path_master, "w") as f:
        json.dump(koordinate, f, indent=4, cls=NumpyEncoder)
    logger.info(f"Saved coordinates to {koordinate_save_path_master}")  # Fixed variable name here
    logger.info(f"Saved coordinates: {koordinate}")  # Te koordinate ki jih shranis so spremenjene glede na koncno master sliko  
    
    
    koordinate_save_path_master_skalirane = "/home/cameramodule/Desktop/captured/koordinate_master_skalirane.json"
    conversion_f = conversion_factor(koordinate, qr_code_size) # Izracuna razmerje med mm in pixli
    koordinate_skalirane = skaliranje(koordinate, moduli_dim, qr_code_size, conversion_f) # Vrne transformirane koordinate
    parametri_modulov = calculate_module_properties(koordinate_skalirane)
    
    # Save the adjusted coordinates as a JSON file using our custom encoder
    with open(koordinate_save_path_master_skalirane, "w") as f:
        json.dump(koordinate_skalirane, f, indent=4, cls=NumpyEncoder)
    logger.info(f"Saved coordinates to {koordinate_save_path_master_skalirane}")  # Fixed variable name here
    logger.info(f"Saved coordinates: {koordinate_skalirane}")  # Te koordinate ki jih shranis so spremenjene glede na koncno master sliko  
  
    izris(zdruzena_slika_master, koordinate_skalirane, conversion_f, output_image_name, dpi=1200) # tale dpi sm na oko spreminjal da sem dobil priblizno isto velikost kot pri sliki od slava


def join_images_vertically(
    top_image_path, 
    bottom_image_path, 
    output_path,
    # Top image controls
    top_horizontal_shift=0,  # Positive values shift right, negative values shift left
    top_top_crop=0,
    top_bottom_crop=0,
    top_horizontal_stretch=1.0,  # New parameter: 1.0 means no stretch, >1.0 stretches, <1.0 compresses
    # Bottom image controls
    bottom_horizontal_shift=0,  # Positive values shift right, negative values shift left
    bottom_top_crop=0,
    bottom_bottom_crop=0,
    bottom_horizontal_stretch=1.0,  # New parameter: 1.0 means no stretch, >1.0 stretches, <1.0 compresses
    # Optional padding
    padding_color=(255, 255, 255),  # Default: white padding
    overlap_blend=0  # Number of pixels to blend at the seam (0 for no blending)
):
 
    # Load images
    image_top = cv2.imread(top_image_path)
    image_bottom = cv2.imread(bottom_image_path)
    
    # Check if images loaded successfully
    if image_top is None:
        raise FileNotFoundError(f"Could not load top image from {top_image_path}")
    if image_bottom is None:
        raise FileNotFoundError(f"Could not load bottom image from {bottom_image_path}")
    
    # Apply vertical cropping to top image
    if top_top_crop > 0 or top_bottom_crop > 0:
        height, width = image_top.shape[:2]
        top_top_crop = min(max(top_top_crop, 0), height - 1)
        top_bottom_crop = min(max(top_bottom_crop, 0), height - top_top_crop - 1)
        image_top = image_top[top_top_crop:height-top_bottom_crop, :]
    
    # Apply vertical cropping to bottom image
    if bottom_top_crop > 0 or bottom_bottom_crop > 0:
        height, width = image_bottom.shape[:2]
        bottom_top_crop = min(max(bottom_top_crop, 0), height - 1)
        bottom_bottom_crop = min(max(bottom_bottom_crop, 0), height - bottom_top_crop - 1)
        image_bottom = image_bottom[bottom_top_crop:height-bottom_bottom_crop, :]
    
    # Apply horizontal stretching to top image if needed
    if top_horizontal_stretch != 1.0:
        top_height, top_width = image_top.shape[:2]
        new_width = int(top_width * top_horizontal_stretch)
        image_top = cv2.resize(image_top, (new_width, top_height), interpolation=cv2.INTER_LINEAR)
    
    # Apply horizontal stretching to bottom image if needed
    if bottom_horizontal_stretch != 1.0:
        bottom_height, bottom_width = image_bottom.shape[:2]
        new_width = int(bottom_width * bottom_horizontal_stretch)
        image_bottom = cv2.resize(image_bottom, (new_width, bottom_height), interpolation=cv2.INTER_LINEAR)
    
    # Get dimensions after cropping and stretching
    top_height, top_width = image_top.shape[:2]
    bottom_height, bottom_width = image_bottom.shape[:2]
    
    # Determine the common width (max of both images plus max absolute shift)
    max_shift = max(abs(top_horizontal_shift), abs(bottom_horizontal_shift))
    common_width = max(top_width, bottom_width) + max_shift
    
    # Create canvases for both images with the common width
    top_canvas = np.ones((top_height, common_width, 3), dtype=np.uint8)
    top_canvas[:] = padding_color
    
    bottom_canvas = np.ones((bottom_height, common_width, 3), dtype=np.uint8)
    bottom_canvas[:] = padding_color
    
    
  
    # Calculate padding positions for horizontal shifts
    if top_horizontal_shift >= 0:
        # Shift right
        top_x_start = top_horizontal_shift
        top_x_end = min(top_x_start + top_width, common_width)
        top_img_start = 0
        top_img_end = top_x_end - top_x_start
    else:
        # Shift left
        top_x_start = 0
        top_x_end = min(top_width + top_horizontal_shift, common_width)
        top_img_start = -top_horizontal_shift
        top_img_end = top_img_start + (top_x_end - top_x_start)
    
    if bottom_horizontal_shift >= 0:
        # Shift right
        bottom_x_start = bottom_horizontal_shift
        bottom_x_end = min(bottom_x_start + bottom_width, common_width)
        bottom_img_start = 0
        bottom_img_end = bottom_x_end - bottom_x_start
    else:
        # Shift left
        bottom_x_start = 0
        bottom_x_end = min(bottom_width + bottom_horizontal_shift, common_width)
        bottom_img_start = -bottom_horizontal_shift
        bottom_img_end = bottom_img_start + (bottom_x_end - bottom_x_start)
    
    # Place the images on their respective canvases
    top_canvas[:, top_x_start:top_x_end] = image_top[:, top_img_start:top_img_end]
    bottom_canvas[:, bottom_x_start:bottom_x_end] = image_bottom[:, bottom_img_start:bottom_img_end]
    
    # Combine the images vertically
    if overlap_blend > 0 and overlap_blend < min(top_height, bottom_height):
        # Create a combined image with blended overlap
        combined_height = top_height + bottom_height - overlap_blend
        combined_image = np.ones((combined_height, common_width, 3), dtype=np.uint8)
        combined_image[:] = padding_color
        
        # Copy the top image (excluding the overlap region)
        combined_image[:top_height-overlap_blend] = top_canvas[:top_height-overlap_blend]
        
        # Create the blended region
        for i in range(overlap_blend):
            alpha = i / overlap_blend
            overlap_line_top = top_canvas[top_height-overlap_blend+i]
            overlap_line_bottom = bottom_canvas[i]
            combined_image[top_height-overlap_blend+i] = cv2.addWeighted(
                overlap_line_top, 1-alpha, overlap_line_bottom, alpha, 0
            )
        
        # Copy the bottom image (excluding the already blended part)
        combined_image[top_height:] = bottom_canvas[overlap_blend:]
    else:
        # Simple stacking without blending
        combined_image = np.vstack((top_canvas, bottom_canvas))
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the final combined image
    cv2.imwrite(output_path, combined_image)
    print(f"Saved combined image to {output_path}")
    
    return combined_image


def join_joined():
    """
    Join the predefined images with default parameters.
    This is the main function that can be called directly.
    """
    # File paths
    # top_image_path = "/home/cameramodule/Desktop/received/zdruzena_slika_slave.jpg"
    top_image_path = "/home/cameramodule/Desktop/received/zdruzena_slika_slave_z_moduli.jpg"
    bottom_image_path = "/home/cameramodule/Desktop/captured/rezultat.jpg"
    output_path = "/home/cameramodule/Desktop/combined/combined.jpg"
    
    # Control parameters - adjust these to position the images as needed
    # Top image controls
    top_horizontal_shift = 270     # Shift the top image horizontally (positive = right, negative = left)
    top_top_crop = 10            # Crop from top of top image
    top_bottom_crop = 600        # Crop from bottom of top image
    top_horizontal_stretch = 1.0  # Compress top image width by 20% to match bottom image width better
    
    # Bottom image controls
    bottom_horizontal_shift = 0  # Shift the bottom image horizontally (positive = right, negative = left)
    bottom_top_crop = 300        # Crop from top of bottom image
    bottom_bottom_crop = 10     # Crop from bottom of bottom image
    bottom_horizontal_stretch = 1.0 #1.07  # No stretching for bottom image
    
    # Optional blending at the seam for smoother transition
    overlap_blend = 0            # Set to 0 for no blending or a positive value for pixel overlap blend
    
    # Join images with the specified parameters
    combined_image = join_images_vertically(
        top_image_path,
        bottom_image_path,
        output_path,
        top_horizontal_shift,
        top_top_crop,
        top_bottom_crop,
        top_horizontal_stretch,
        bottom_horizontal_shift,
        bottom_top_crop,
        bottom_bottom_crop,
        bottom_horizontal_stretch,
        padding_color=(255, 255, 255),  # White padding
        overlap_blend=overlap_blend
    )
    
    # Load the image
    image = Image.open("/home/cameramodule/Desktop/combined/combined.jpg")

    base_width = 800
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    resized_image = image.resize((base_width, h_size), Image.LANCZOS)

    # Save or show the resized image
    resized_image.save("/home/cameramodule/Desktop/combined/combined_resized.jpg")
    print("Done with resizing the combined image")


def flip_y_coordinates(input_json_path, image_height):
    """Flip Y coordinates based on image height."""
    with open(input_json_path, 'r') as f:
        data = json.load(f)

    flipped_data = {
        name: [[x, image_height - y] for x, y in points]
        for name, points in data.items()
    }

    return flipped_data


def draw_modules(image_path, coordinates, output_image_path):
    """Draw modules on the image and save the result."""
    image = cv2.imread(image_path)

    if image is None:
        raise FileNotFoundError(f"Image '{image_path}' not found.")

    green = (0, 0, 255)

    for name, points in coordinates.items():
        pts = np.array(points, np.int32).reshape((-1, 1, 2))
        cv2.polylines(image, [pts], isClosed=True, color=green, thickness=20)

        # Calculate center point
        cx = int(sum([p[0] for p in points]) / len(points))
        cy = int(sum([p[1] for p in points]) / len(points))
        cv2.putText(image, name, (cx - 40, cy - 100), cv2.FONT_HERSHEY_SIMPLEX, 5, green, 6)

    cv2.imwrite(output_image_path, image)


def narisi_module_na_koncno_sliko():
    # Paths
    image_path = '/home/cameramodule/Desktop/combined/combined.jpg'
    #original_coords_path = '/home/cameramodule/Desktop/combined/combined_koordinate.json'
    original_coords_path = '/home/cameramodule/Desktop/combined/combined_koordinate.json'
    flipped_coords_path = '/home/cameramodule/Desktop/combined/combined_koordinate_flipped.json'

    # Load image to get height
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError("Image 'combined.jpg' not found.")
    IMAGE_HEIGHT = image.shape[0]

    # --- Draw image with original coordinates ---
    with open(original_coords_path, 'r') as f:
        original_coords = json.load(f)
    draw_modules(image_path, original_coords, 'annotated_combined_original.jpg')

    # --- Generate flipped coordinates and save ---
    flipped_coords = flip_y_coordinates(original_coords_path, IMAGE_HEIGHT)
    with open(flipped_coords_path, 'w') as f:
        json.dump(flipped_coords, f, indent=4)

    # --- Draw image with flipped coordinates ---
    draw_modules(image_path, flipped_coords, 'annotated_combined_flipped.jpg')


def resize_and_encode(image_path, max_size=(800, 800), quality=30):
    """Resize and compress the image, return base64-encoded JPEG."""
    with Image.open(image_path) as img:
        img.thumbnail(max_size)  # Resize in-place while keeping aspect ratio
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
        
def upload_image_once(image_path, thingsboard_host, username, password):

    # Define the callback function for connection
    def on_connect(client, userdata, flags, rc):
        print(f"Connected with result code {rc}")

        if rc == 0:
            try:
                ## Convert the image to a base64 string
                with open(image_path, "rb") as image_file:
                    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                ## S tem dol smo zamenjali ta zgornji encoder ker je file prevelik 8000x8000 -> 10MB kar ne zmore mqtt - Encoded image size more bit tm nekje 60k
                # encoded_image = resize_and_encode(image_path)
                print(f"Encoded image size (base64 length): {len(encoded_image)}")

                # Prepare the payload with the base64 encoded image
                payload = {"DC2image": encoded_image}

                # Publish the image as a shared attribute
                result = client.publish('v1/devices/me/attributes', json.dumps(payload), qos=1)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    print("Image successfully published as a shared attribute.")
                else:
                    print(f"Failed to publish image, result code: {result.rc}")

            except FileNotFoundError:
                print(f"File not found: {image_path}")
                client.disconnect()
            except Exception as e:
                print(f"Error encoding or sending image: {e}")
                client.disconnect()
        else:
            print(f"Failed to connect, result code: {rc}")

    # Define the callback function for publish
    def on_publish(client, userdata, mid):
        print("Message Published with mid:", mid)
        # Disconnect the client after sending the image
        client.disconnect()

    # Create an MQTT client instance
    client = mqtt.Client()

    # Set the callback functions
    client.on_connect = on_connect
    client.on_publish = on_publish

    # Set the username and password
    client.username_pw_set(username, password)

    try:
        # Connect to ThingsBoard's MQTT broker
        client.connect(thingsboard_host, 1883, 60)
    except Exception as e:
        print(f"Failed to connect to ThingsBoard: {e}")
        return

    # Start the MQTT loop to process network traffic
    client.loop_start()

    # Wait for the message to be published and processed
    # time.sleep(0.1)
    time.sleep(2)

    # Stop the MQTT loop
    client.loop_stop()


def upload(input_data, THINGSBOARD_HOST, USERNAME, PASSWORD, PORT):
    """Upload data to ThingsBoard using MQTT username and password."""
    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)
    logging.basicConfig(level=logging.DEBUG)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.debug("Connected successfully to ThingsBoard")
        else:
            logging.error(f"Failed to connect with result code {rc}")

    def on_publish(client, userdata, mid):
        logging.debug(f"Message Published: {mid}")

    client.on_connect = on_connect
    client.on_publish = on_publish

    try:
        logging.debug(f"Attempting connection to {THINGSBOARD_HOST}:{PORT}")
        client.connect(THINGSBOARD_HOST, PORT, keepalive=60)
        client.loop_start()
        logging.debug("MQTT connection established")
    except Exception as e:
        logging.error(f"MQTT connection failed: {e}")
        return

    for key, value in input_data.items():
        if len(value) != 3:
            logging.error(f"Unexpected value format for key {key}: {value}")
            continue

        updated_data = {
            f'Lokacija_X_{key}': value[0],
            f'Lokacija_Y_{key}': value[1],
            f'Rotacija_{key}': value[2]
        }

        logging.debug(f"Data to be sent: {updated_data}")

        retry_count = 0
        backoff_time = INITIAL_BACKOFF

        while retry_count < RETRY_LIMIT:
            try:
                result = client.publish('v1/devices/me/attributes', json.dumps(updated_data), qos=1)
                status = result.rc
                if status == 0:
                    logging.debug(f"Sent `{json.dumps(updated_data)}` to topic `v1/devices/me/attributes`")
                    break  # Exit loop on success
                else:
                    logging.error(f"Failed to send message to topic. Status: {status}")

            except Exception as e:
                logging.error(f"Exception occurred during publish: {e}")

            retry_count += 1
            logging.info(f"Retrying in {backoff_time} seconds... (Attempt {retry_count}/{RETRY_LIMIT})")
            time.sleep(backoff_time)
            backoff_time *= 2  # Exponential backoff

        if retry_count == RETRY_LIMIT:
            logging.error(f"Failed to send data for key `{key}` after {RETRY_LIMIT} attempts.")

        time.sleep(INITIAL_BACKOFF)

    client.loop_stop()
    client.disconnect()

    
def publish():
    try:
        # Reset values
        print("Nastavljanje vrednosti modulov na 0 oz. default vrednosti")
        upload(default_values, THINGSBOARD_HOST, USERNAME, PASSWORD, PORT)

        # Load coordinates from combined_coordinates.json
        with open("/home/cameramodule/Desktop/combined/coordinates_in_cm.json", "r") as f:
            parametri_modulov = json.load(f) 

        # Upload new coordinates
        if parametri_modulov:
            print("POSILJAM LOKACIJE  NA THINGSBOARD")
            upload(parametri_modulov, THINGSBOARD_HOST, USERNAME, PASSWORD, PORT)
        else:
            print('NI ZAZNANIH MODULOV!')

        # Upload new image
        print("POSILJAM SLIKO  NA THINGSBOARD")
        upload_image_once("/home/cameramodule/Desktop/combined/combined_resized.jpg", THINGSBOARD_HOST, USERNAME, PASSWORD)

    except Exception as error:
        print('Napaka: ', error)        
    

THINGSBOARD_HOST = '192.168.9.108'
USERNAME = "Module10_MQTT"  # Device username from ThingsBoard
PASSWORD = "Module10MQTT"  # Device password from ThingsBoard
PORT = 1883        


# ===================================================================================================
# ===================================================================================================
# TO NE DELA DOBRO!!!!!!!
def coordinates_to_cm():
    # Step 1: Load the JSON data
    with open('/home/cameramodule/Desktop/combined/combined_converted_coordinates.json', 'r') as f:
        data = json.load(f)

    # Step 2: Calculate pixel distance between Standard7 and Sorting
    # x1 = data['Standard7'][0]
    # x2 = data['Sorting'][0]
    #x1 = 5629.25
    #x2 = 7645.25
    x1 = 4611.25
    x2 = 3456.75
    
    pixel_distance = abs(x1 - x2)

    # Real-world distance between Standard7 and Sorting in cm
    #real_distance_cm = 129 #storting in standard 7 129 cm
    real_distance_cm = 105 #standard 1 in werehouse kocke 105cm

    # Step 3: Compute scale (cm per pixel)
    cm_per_pixel = real_distance_cm / pixel_distance

    # Step 4: Convert all coordinates
    converted_data = {}
    for key, value in data.items():
        x_pixel, y_pixel, angle = value
        x_cm = x_pixel * cm_per_pixel
        y_cm = y_pixel * cm_per_pixel
        converted_data[key] = [x_cm, y_cm, angle]

    # Step 5: Save to a new JSON file
    with open('/home/cameramodule/Desktop/combined/coordinates_in_cm.json', 'w') as f:
        json.dump(converted_data, f, indent=4)

    print("Converted coordinates saved to 'coordinates_in_cm.json'")

# ===================================================================================================
# ===================================================================================================


def xy_axis():
    # CONFIGURATION
    image_path = '/home/cameramodule/Desktop/combined/combined_resized.jpg'  # Replace with your image path
    output_image_name = '/home/cameramodule/Desktop/combined/combined_with_axis.jpg'
    dpi = 100

    image_px = 800
    real_width_cm = 545
    cm_per_pixel = real_width_cm / image_px

    x_offset_cm = 50
    y_offset_cm = 20

    # --- Load Image ---
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError("Could not load image.")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # --- Set Up Plot ---
    fig, ax = plt.subplots(figsize=(image_px / dpi, image_px / dpi), dpi=dpi)
    ax.imshow(img)
    ax.set_xlim(0, image_px)
    ax.set_ylim(image_px, 0)  # invert Y

    # --- Create Tick Locations and Labels ---
    tick_step_cm = 50
    tick_step_px = tick_step_cm / cm_per_pixel

    # X-axis
    x_ticks_px = np.arange(0, image_px, tick_step_px)
    x_labels_cm = [f"{(x * cm_per_pixel - x_offset_cm):.0f}" for x in x_ticks_px]
    ax.xaxis.set_major_locator(FixedLocator(x_ticks_px))
    ax.set_xticklabels(x_labels_cm)

    # Y-axis
    y_ticks_px = np.arange(0, image_px, tick_step_px)
    y_labels_cm = [f"{(y * cm_per_pixel - y_offset_cm):.0f}" for y in y_ticks_px]
    ax.yaxis.set_major_locator(FixedLocator(y_ticks_px))
    ax.set_yticklabels(y_labels_cm)

    # --- Axis Labels ---
    ax.set_xlabel('X [cm]')
    ax.set_ylabel('Y [cm]')

    # --- Save Output ---
    plt.savefig(
        output_image_name,
        dpi=dpi,
        bbox_inches='tight',
        pad_inches=0
    )
    plt.close()



def main():
    recieve_photos()
    time.sleep(10)
    take_photos()
    combine_coordinates(x_offset_slave=-150, y_offset_slave=3250, x_offset_master=-50, y_offset_master=200)
    join_joined()
    ## narisi_module_na_koncno_sliko() #preverjanje ce so koordinate pravilne
    coordinates_to_cm()
    # xy_axis()
    
    #server()
    publish()

       
if __name__ == "__main__":
    main()


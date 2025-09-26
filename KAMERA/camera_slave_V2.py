import cv2
import paho.mqtt.client as mqtt
import base64
import numpy as np
import time
import RPi.GPIO as gp
import os
import json
import logging
import imutils
import itertools
import matplotlib.pyplot as plt
import zxingcpp
from PIL import Image
import math
from datetime import datetime


# cameraslave2
# password: cameraslave

# Tod je staro in dela fix!!!
# Nastavitev logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GPIO Setup
gp.setwarnings(False)
gp.setmode(gp.BOARD)
gp.setup(7, gp.OUT)
gp.setup(11, gp.OUT)
gp.setup(12, gp.OUT)

# Omrežne nastavitve
MASTER_IP = '192.168.9.118'  # Update with master RPi IP
SLAVE_IP = '192.168.9.131'  
PORT = 1883
USERNAME = "Module10_MQTT"
PASSWORD = "Module10MQTT"

# Camera settings and configuration remain the same as in original Slave_Final.py
camera_settings = {
    'B': {'i2c': "i2cset -y 1 0x70 0x00 0x04", 'gpio': (False, False, True), 'rotation': cv2.ROTATE_90_COUNTERCLOCKWISE},
    'D': {'i2c': "i2cset -y 1 0x70 0x00 0x05", 'gpio': (True, False, True), 'rotation': cv2.ROTATE_90_CLOCKWISE},
    'A': {'i2c': "i2cset -y 1 0x70 0x00 0x06", 'gpio': (False, True, False), 'rotation': cv2.ROTATE_90_CLOCKWISE},
    'C': {'i2c': "i2cset -y 1 0x70 0x00 0x07", 'gpio': (True, True, False), 'rotation': cv2.ROTATE_90_CLOCKWISE},
}

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


# Image processing and QR code detection functions from Slave_Thingsboard.py
def kamera(name):
    """Capture image from a specific camera"""
    settings = camera_settings[name]
    os.system(settings['i2c'])
    gp.output(7, settings['gpio'][0])
    gp.output(11, settings['gpio'][1])
    gp.output(12, settings['gpio'][2])
    return capture(name)

# #capture staro??
def capture(name):
    """Capture an image using libcamera"""
    # Ustvari mapo, če ne obstaja
    save_dir = '/home/cameramodule2/Desktop/original'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    filename = f'{save_dir}/{name}.jpg'
    cmd = f'libcamera-jpeg -o {filename} --nopreview --autofocus-mode=manual --lens-position=0.0 --shutter 50000 --gain 1.5'
    
    try:
        # Preveri, če je ukaz uspešen
        result = os.system(cmd)
        if result != 0:
            logger.error(f"Failed to capture image with command: {cmd}")
            return None
            
        # Preveri, če datoteka obstaja
        if not os.path.exists(filename):
            logger.error(f"Image file not created: {filename}")
            return None
            
        image = cv2.imread(filename)
        if image is None:
            logger.error(f"Failed to read image: {filename}")
            return None
            
        logger.info(f"Successfully saved and read image: {filename}")
        return image
        
    except Exception as e:
        logger.error(f"Error capturing image: {str(e)}")
        logger.exception("Full traceback:")
        return None
        

def load_and_rotate_images(crop_top, crop_bottom):
    """Load, rotate, and crop images"""
    # Vertical offsets and crops for each camera
    Avp, Al, Ad = 0, 0, 320
    Bvp, Bl, Bd = 0, 420, 130
    Cvp, Cl, Cd = 90, 130, 370
    Dvp, Dl, Dd = 10, 570, 0

    input_A = kamera('A')
    input_B = kamera('B')
    input_C = kamera('C')
    input_D = kamera('D')

    # Rotate images
    slikaA = cv2.rotate(input_A, cv2.ROTATE_90_CLOCKWISE)
    slikaB = cv2.rotate(input_B, cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaC = cv2.rotate(input_C, cv2.ROTATE_90_CLOCKWISE)
    slikaD = cv2.rotate(input_D, cv2.ROTATE_90_CLOCKWISE)

    # Fine rotate images
    slikaAf = imutils.rotate(slikaA, angle=3)
    slikaBf = imutils.rotate(slikaB, angle=0)
    slikaCf = imutils.rotate(slikaC, angle=-1)
    slikaDf = imutils.rotate(slikaD, angle=0)

    # Add vertical padding and cropping
    def premik(slika, vp):
        padding = 300
        height, width = slika.shape[:2]
        total_height = 2 * padding + height
        top_padding = (total_height - height) // 2
        white_canvas = np.ones((total_height, width, 3), dtype=np.uint8) * 255
        white_canvas[top_padding:top_padding + height, :] = slika
        result_image = np.roll(white_canvas, -int(vp), axis=0)
        return result_image

    def crop_img(img, top_crop_height, bottom_crop_height):
        height, width = img.shape[:2]
        if top_crop_height + bottom_crop_height >= height:
            return img
        return img[top_crop_height:height - bottom_crop_height, :]

    A = crop_img(premik(slikaAf, Avp), crop_top, crop_bottom)
    B = crop_img(premik(slikaBf, Bvp), crop_top, crop_bottom)
    C = crop_img(premik(slikaCf, Cvp), crop_top, crop_bottom)
    D = crop_img(premik(slikaDf, Dvp), crop_top, crop_bottom)

    return A, B, C, D


def crop_left_right(slika, levo, desno):
    """Crop the image from the left and right sides"""
    height, width = slika.shape[:2]
    new_width = width - (levo + desno)
    left_crop = max(0, levo)
    right_crop = max(0, desno)
    cropped_image = slika[:, left_crop:width - right_crop]
    return cropped_image


def background(slikaA, slikaB, slikaC, slikaD):
    """Create a background image by concatenating cropped images"""
    # Crop parameters for each image
    A = crop_left_right(slikaA, 0, 320)
    B = crop_left_right(slikaB, 420, 130)
    C = crop_left_right(slikaC, 130, 370)
    D = crop_left_right(slikaD, 570, 0)
    
    return cv2.hconcat([A, B, C, D])


def decode(image):
    """Decode QR codes in an image"""
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


    def renaming(name):
        return names.get(name, 'Unknown')

    barcodes = zxingcpp.read_barcodes(image)
    positions = {}

    for barcode in barcodes:
        text = renaming(str(barcode.text))
        position_str = str(barcode.position).strip('\x00')
        pairs = position_str.split()
        output = [np.array([int(x.split('x')[0]), int(x.split('x')[1])]) for x in pairs]

        if text != 'Unknown':
            positions[text] = output

    return positions if barcodes else None



def premik_koordinat(slika1, slika2, slika3, slika4):
    """Adjust coordinates of QR codes based on image offsets and validate bounds."""
    
    # Crop parameters for each image
    Al, Ad = 0, 320
    Bl, Bd = 420, 130
    Cl, Cd = 130, 370
    Dl, Dd = 570, 0
    
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

    # Each detected QR codes coordinates are adjusted relative to the final stitched image (kode1 - leftmost picture)
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

        

def conversion_factor(codes, qr_code_size): # each pixel corresponds to X mm -> take the average of the four distances and divide qr_code_size by that average to return the conversion factor.
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



def izris(slika_BG, oglisca, scale_factor, output_image_name, dpi):
    """Draw the modules and their details on the image."""
    try:
        # Load the image using cv2 and flip it vertically
        img = slika_BG
        height, width = img.shape[:2]
        new_size = (int(width * scale_factor), int(height * scale_factor))
        scaled_image = cv2.resize(img, new_size, interpolation=cv2.INTER_LINEAR)
        img_flipped = cv2.flip(scaled_image, 0)
        
        # Convert the image from BGR to RGB format (cv2 loads in BGR by default)
        img_flipped_rgb = cv2.cvtColor(img_flipped, cv2.COLOR_BGR2RGB)
        
        # Create the plot
        plt.figure(figsize=(10, 10))
        #to gor je staro, in narise tudi white borderje in mogoce zjebe dpi idk
        #ax.set_position([0, 0, 1, 1])
        plt.imshow(img_flipped_rgb)
        
        ax = plt.gca()
        ax.set_aspect('equal', adjustable='box')
        ax.invert_yaxis()
        
        # to izklopi skalo
        ax.axis('off')
        
        # Draw module outlines and labels
        for modul, oglisca_modul in oglisca.items():
            points = np.array(oglisca_modul)
            kontx = np.append(points[:, 0], points[0, 0])
            konty = np.append(points[:, 1], points[0, 1])
            plt.plot(kontx, konty, color='blue')
            
            # Calculate the center of the rectangle
            center_x = np.mean(points[:, 0])
            center_y = np.mean(points[:, 1])
            
            # Plot the text at the center of the rectangle
            plt.text(center_x, center_y, modul, ha='center', va='center', 
                     backgroundcolor='w', color='red', fontsize=7)
        
        # # to izklopi imena skale
        # plt.xlabel('X [cm]')
        # plt.ylabel('Y [cm]')
        
        
        # Save with no border/padding
        plt.savefig(
            output_image_name,
            dpi=dpi,
            bbox_inches='tight',
            pad_inches=0
        )
    
    
        # Save the figure
        # plt.savefig(output_image_name, dpi=dpi, bbox_inches='tight')
        plt.close()
        
        # Read the saved image back in with OpenCV
        result_image = cv2.imread(output_image_name)
        
        if result_image is None or result_image.size == 0:
            logger.error("Failed to generate visualization image")
            return slika_BG  # Fallback to original image
        
        return result_image
    
    except Exception as e:
        logger.error(f"Error in image visualization: {e}")
        return slika_BG  # Fallback to original image





def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {MASTER_IP} with result code: {rc}")
        # Naroči se na kanal za ukaze od master-ja
        client.subscribe("camera/command")
        logger.info("Subscribed to camera/command topic")
    else:
        logger.error(f"Failed to connect with result code {rc}")

capture_on = False




def on_message(client, userdata, msg):
    """MQTT message callback"""
    if msg.topic == "camera/command":
        command = msg.payload.decode()
        logger.info(f"Received command: {command}")
        if command == "capture":
            global capture_on
            if not capture_on:
                logger.info("Starting image capture sequence")
                capture_on = True
                capture_and_send_images(client)

        else:
            logger.warning(f"Unknown command received: {command}")


class NumpyEncoder(json.JSONEncoder):
    """ Custom encoder to convert NumPy data types to JSON serializable types """
    
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # Convert NumPy array to list
        if isinstance(obj, np.generic):
            return obj.item()  # Convert NumPy scalar to Python scalar
        return super().default(obj)        
      
      
      
def capture_and_send_images(client):
#def capture_and_send_images():    
    """Capture images, process, and send to master"""
        
    try:
        # Image processing parameters
        bottom_crop = 0
        top_crop = 300
        premik_horizontal = 270  # move 270 pixels to the right; use negative for left shift
        dvig_spust_koordinat = -300 -900 -310 -610
        logger.info(f"Stevilo za koliko pixlov odstejemo {dvig_spust_koordinat}")   # = -2120
        #300 - samo slave slika (v tej kodi), 900 = 700 top in 200 bottom samo master (v kodi za master)
        #610 = 600 bottom in 10 top - zdruzena za slave, 310 = 300 top in 10 bottom - zdruzena za master (v kodi join joined)

        # Capture and process images
        slikaA, slikaB, slikaC, slikaD = load_and_rotate_images(crop_top=top_crop, crop_bottom=bottom_crop)
        logger.info("Finished the load_and_rotate part")

        zdruzena_brez_nic = background(slikaA, slikaB, slikaC, slikaD)
        output_file = "/home/cameramodule2/Desktop/original/zdruzena_brez_nic.jpg"
        cv2.imwrite(output_file, zdruzena_brez_nic)
        logger.info(f"Zdruzena slika saved successfully as {output_file}")

        # Get raw coordinates (adjusted relative to the stitched image)
        koordinate = premik_koordinat(slikaA, slikaB, slikaC, slikaD)
        
        koordinate_save_path_slave = "/home/cameramodule2/Desktop/original/koordinate.json"
        with open(koordinate_save_path_slave, "w") as f:
            json.dump(koordinate, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved Basic coordinates to {koordinate_save_path_slave}")

        # Calculate scaling
        qr_code_size = 10
        conversion_f = conversion_factor(koordinate, qr_code_size)
        logger.info(f"Calculated conversion factor: {conversion_f}")

        koordinate_skalirane = skaliranje(koordinate, moduli_dim, qr_code_size, conversion_f)
        parametri_modulov = calculate_module_properties(koordinate_skalirane)
        logger.info(f"Finished the koordinate scaling part")

        koordinate_save_path_slave_skalirane = "/home/cameramodule2/Desktop/original/koordinate_skalirane.json"
        with open(koordinate_save_path_slave_skalirane, "w") as f:
            json.dump(koordinate_skalirane, f, indent=4, cls=NumpyEncoder)
        logger.info(f"Saved scaled coordinates to {koordinate_save_path_slave_skalirane}")

        # Generate visualization
        output_image_name = "/home/cameramodule2/Desktop/original/rezultat_z_moduli.jpg"
        rezultat_z_moduli = izris(zdruzena_brez_nic, koordinate_skalirane, conversion_f, output_image_name, dpi=1000)
        logger.info(f"Visualization image saved as {output_image_name}")
        logger.info(f"rezultat_z_moduli shape: {rezultat_z_moduli.shape}")
        logger.info(f"rezultat_z_moduli type: {type(rezultat_z_moduli)}")
        logger.info(f"rezultat_z_moduli is None: {rezultat_z_moduli is None}")

        if rezultat_z_moduli is None or rezultat_z_moduli.size == 0:
            logger.error("rezultat_z_moduli is empty or None")
            return
            
            
        
        # Adjust y-coordinates
        original_image_height = slikaA.shape[0]
        koordinate_skalirane_dvignjene = {
            key: [pos.copy() for pos in positions] for key, positions in koordinate_skalirane.items()
        }
        # stara samo za visinsko spremembo
        # for key, positions in koordinate_skalirane_dvignjene.items():
            # for i in range(len(positions)):
                # koordinate_skalirane_dvignjene[key][i][1] += original_image_height + dvig_spust_koordinat
        
        #nova ki tudi uposteva shift slave slike (tale) za top_horizontal_shift = 270 - positive = right, negative = left)
        for key, positions in koordinate_skalirane_dvignjene.items():
            for i in range(len(positions)):
                # Adjust the y-coordinate (vertical shift)
                koordinate_skalirane_dvignjene[key][i][1] += original_image_height + dvig_spust_koordinat
                # Adjust the x-coordinate (horizontal shift)
                koordinate_skalirane_dvignjene[key][i][0] += premik_horizontal
   
        


        koordinate_save_path_slave = "/home/cameramodule2/Desktop/original/koordinate_skalirane_dvignjene.json"
        with open(koordinate_save_path_slave, "w") as f:
            json.dump(koordinate_skalirane_dvignjene, f, indent=4, cls=NumpyEncoder)

        logger.info("Image Processing is completed")



        # Encode images
        success, buffer = cv2.imencode('.jpg', zdruzena_brez_nic)
        if not success:
            logger.error("Failed to encode zdruzena_brez_nic")
            return
        zdruzena_brez_nic_base64 = base64.b64encode(buffer).decode('utf-8')

        success, buffer = cv2.imencode('.jpg', rezultat_z_moduli)
        if not success:
            logger.error("Failed to encode rezultat_z_moduli")
            return
        rezultat_z_moduli_base64 = base64.b64encode(buffer).decode('utf-8')

        # Convert NumPy arrays in the dictionary to JSON serializable lists
        koordinate_json = {key: [arr.tolist() for arr in value] for key, value in koordinate.items()}
        koordinate_skalirane_json = {key: [arr.tolist() for arr in value] for key, value in koordinate_skalirane.items()}
        koordinate_skalirane_dvignjene_json = {key: [arr.tolist() for arr in value] for key, value in koordinate_skalirane_dvignjene.items()}

        # Prepare payload
        payload = {
            'koordinate': koordinate_json,
            'koordinate_skalirane': koordinate_skalirane_json,
            'koordinate_skalirane_dvignjene': koordinate_skalirane_dvignjene_json,
            'zdruzena_brez_nic': zdruzena_brez_nic_base64,
            'rezultat_z_moduli': rezultat_z_moduli_base64
        }
        
        # Publish payload
        client.publish('camera/images', json.dumps(payload))
        logger.info("Published module data and stitched image")

    except Exception as e:
        logger.error(f"Error in capture and send: {e}")
        
        

def on_disconnect(client, userdata, rc):
    logger.error(f"Disconnected with result code: {rc}")
    if rc != 0:
        logger.error("Unexpected disconnection. Will attempt to reconnect...")



def main():
    #capture_and_send_images()
    
    client = mqtt.Client() 
    #client.username_pw_set(USERNAME, PASSWORD)  
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    while True:
        try:
            logger.info(f"Attempting to connect to MQTT broker at {MASTER_IP}:{PORT}")
            client.connect(MASTER_IP, PORT, 60)
            logger.info("Connected successfully")
            client.loop_forever()
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            logger.exception("Full traceback:")
            time.sleep(5)
    


if __name__ == "__main__":
    logger.info("Starting slave camera service - waiting for master commands...")
    main() 

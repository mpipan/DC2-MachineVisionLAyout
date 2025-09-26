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

# Import all necessary configurations and functions from config
from config import logger, camera_settings, setup_camera_mux, SHUTTER_SPEED, GAIN, LENS_POSITION, \
                   crop_top, crop_bottom, names, moduli_dim

# --- Helper Functions from Original Code ---
def capture(name):
    """
    Capture an image using libcamera and return it.
    This is the most robust version from your commented-out code.
    """
    save_dir = '/home/cameramodule2/Desktop/original'
    os.makedirs(save_dir, exist_ok=True)
    filename = os.path.join(save_dir, f'{name}.jpg')
    
    if os.path.exists(filename):
        try:
            os.remove(filename)
        except Exception as e:
            logger.error(f"Failed to remove old file {filename}: {e}")
            
    cmd = f'libcamera-jpeg -o {filename} --nopreview --autofocus-mode=manual --lens-position={LENS_POSITION} --shutter {SHUTTER_SPEED} --gain {GAIN}'
    
    result = os.system(cmd)
    if result != 0:
        logger.error(f"Failed to capture image with command: {cmd}")
        return None

    if not os.path.exists(filename):
        logger.error(f"Image file not created: {filename}")
        return None

    image = cv2.imread(filename)
    if image is None or image.size == 0:
        logger.error(f"Failed to read image: {filename}")
        return None

    logger.info(f"Successfully saved and read image: {filename}")
    return image

def premik(slika, vp):
    """Add vertical padding and shift image"""
    padding = 300
    height, width = slika.shape[:2]
    total_height = 2 * padding + height
    top_padding = (total_height - height) // 2
    white_canvas = np.ones((total_height, width, 3), dtype=np.uint8) * 255
    white_canvas[top_padding:top_padding + height, :] = slika
    result_image = np.roll(white_canvas, -int(vp), axis=0)
    return result_image

def crop_img(img, top_crop_height, bottom_crop_height):
    """Crop image from top and bottom"""
    height, width = img.shape[:2]
    if top_crop_height + bottom_crop_height >= height:
        return img
    return img[top_crop_height:height - bottom_crop_height, :]

def crop_left_right(slika, levo, desno):
    """Crop the image from the left and right sides"""
    height, width = slika.shape[:2]
    new_width = width - (levo + desno)
    left_crop = max(0, levo)
    right_crop = max(0, desno)
    cropped_image = slika[:, left_crop:width - right_crop]
    return cropped_image

def decode(image):
    """Decode QR codes in an image"""
    def renaming(name):
        return names.get(name, 'Unknown')
    
    barcodes = zxingcpp.read_barcodes(image)
    positions = {}
    for barcode in barcodes:
        text = renaming(str(barcode.text))
        qr_corners = barcode.position
        if text != 'Unknown':
            positions[text] = [
                (qr_corners.top_left.x, qr_corners.top_left.y),
                (qr_corners.top_right.x, qr_corners.top_right.y),
                (qr_corners.bottom_right.x, qr_corners.bottom_right.y),
                (qr_corners.bottom_left.x, qr_corners.bottom_left.y)
            ]
    return positions if barcodes else None


# --- Main Processing Function ---
def capture_and_process_images(max_attempts=3):
    """
    The main processing function for the slave camera.
    This function orchestrates the entire image capture and processing workflow.
    """
    # Vertical offsets and crops for each camera from the original script
    Avp, Al, Ad = 0, 0, 320
    Bvp, Bl, Bd = 0, 420, 130
    Cvp, Cl, Cd = 90, 130, 370
    Dvp, Dl, Dd = 10, 570, 0
    
    # 1. Capture Images
    images = {}
    for name in camera_settings.keys():
        for attempt in range(max_attempts):
            if not setup_camera_mux(name):
                logger.error(f"Failed to select camera {name} on attempt {attempt + 1}")
                time.sleep(1)
                continue
            
            image = capture(name)
            if image is not None:
                logger.info(f"Successfully captured image for camera {name} on attempt {attempt + 1}")
                images[name] = image
                break
            else:
                logger.error(f"Capture failed for camera {name} on attempt {attempt + 1}")
                time.sleep(1)
    
    if len(images) != 4:
        logger.error("Failed to capture images from all 4 cameras.")
        return None

    # 2. Rotate and Fine-Rotate
    slikaA = cv2.rotate(images['A'], cv2.ROTATE_90_CLOCKWISE)
    slikaB = cv2.rotate(images['B'], cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaC = cv2.rotate(images['C'], cv2.ROTATE_90_CLOCKWISE)
    slikaD = cv2.rotate(images['D'], cv2.ROTATE_90_CLOCKWISE)
    
    slikaAf = imutils.rotate(slikaA, angle=3)
    slikaBf = imutils.rotate(slikaB, angle=0)
    slikaCf = imutils.rotate(slikaC, angle=-1)
    slikaDf = imutils.rotate(slikaD, angle=0)

    # 3. Apply Cropping and Padding
    A = crop_img(premik(slikaAf, Avp), crop_top, crop_bottom)
    B = crop_img(premik(slikaBf, Bvp), crop_top, crop_bottom)
    C = crop_img(premik(slikaCf, Cvp), crop_top, crop_bottom)
    D = crop_img(premik(slikaDf, Dvp), crop_top, crop_bottom)

    # 4. Process Images to find QR codes
    koordinate = {
        'A': decode(A),
        'B': decode(B),
        'C': decode(C),
        'D': decode(D),
    }

    # 5. Create a combined image
    zdruzena_brez_nic = cv2.hconcat([crop_left_right(A, Al, Ad), 
                                      crop_left_right(B, Bl, Bd), 
                                      crop_left_right(C, Cl, Cd), 
                                      crop_left_right(D, Dl, Dd)])
                                      
    rezultat_z_moduli = zdruzena_brez_nic.copy()
    
    # Draw QR code outlines on the combined image
    # Note: This drawing logic is simplified as the original `premik_koordinat`
    # function from the slave seems to be more about validation than drawing.
    # The master is responsible for the final drawing and visualization.
    
    # 6. Prepare data for TCP transmission
    data_to_send = {
        'koordinate': koordinate,
        # The master is responsible for further processing and scaling,
        # so we send the raw images and coordinates.
        'zdruzena_brez_nic': zdruzena_brez_nic,
        'rezultat_z_moduli': rezultat_z_moduli,
        # Placeholder for other data the master expects
        'koordinate_skalirane': {},
        'koordinate_skalirane_dvignjene': {},
    }
    
    return data_to_send

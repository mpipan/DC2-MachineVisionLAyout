import os
import cv2
import imutils
import RPi.GPIO as gp

# Import all configuration values
from config import logger, camera_settings, Avp, Bvp, Cvp, Dvp, \
                   A_rotation, B_rotation, C_rotation, D_rotation, \
                   crop_top, crop_bottom, \
                   SHUTTER_SPEED, GAIN, LENS_POSITION

# We will import these from image_processing.py to avoid circular dependencies
# from image_processing import crop_img, premik

def crop_img(slika, crop_top, crop_bottom):
    """
    (Placeholder) Crops an image from the top and bottom.
    """
    height, width, _ = slika.shape
    return slika[crop_top:height - crop_bottom, :]

def premik(slika, vp):
    """
    (Placeholder) Adds vertical padding to an image and shifts it.
    """
    height, width, _ = slika.shape
    shift_amount = int(vp)
    return slika[shift_amount:shift_amount + height, :]

def kamera(name, save=True):
    """
    Activates the specified camera and captures an image.

    Args:
        name (str): The name of the camera to use ('A', 'B', 'C', 'D').
        save (bool): If True, saves the captured image.

    Returns:
        np.ndarray: The captured image as a NumPy array, or None if the camera name is invalid.
    """
    if name not in camera_settings:
        logger.error(f"Invalid camera name: {name}")
        return None

    settings = camera_settings[name]
    logger.info(f"Activating camera {name}")
    
    # Execute I2C command
    os.system(settings['i2c'])
    
    # Set GPIO pins
    gp.output(7, settings['gpio'][0])
    gp.output(11, settings['gpio'][1])
    gp.output(12, settings['gpio'][2])

    return capture(name, save)

def capture(name, save):
    """
    Captures an image using the currently active camera with configurable settings.

    Args:
        name (str): The name of the camera (used for saving).
        save (bool): If True, saves the captured image.

    Returns:
        np.ndarray: The captured image.
    """
    filename = '1.jpg'
    # Define libcamera command with parameters from config.py
    cmd = f'libcamera-jpeg -o {filename} --nopreview --autofocus-mode=manual ' \
          f'--lens-position={LENS_POSITION} --shutter {SHUTTER_SPEED} --gain {GAIN}'
    path = '/home/cameramodule/Desktop/captured'
    
    # Change to the correct directory and execute the command
    os.chdir(path)
    os.system(cmd)
    
    # Read the captured image and save if requested
    image = cv2.imread(os.path.join(path, filename))
    if save:
        cv2.imwrite(f'{name}.png', image)
        
    return image

def load_and_rotate_images(undistort=False):
    """
    Loads, rotates, and crops images from all four cameras using values from config.py.
    
    Args:
        undistort (bool): Whether to perform undistortion.

    Returns:
        tuple: A tuple containing the four processed images (A, B, C, D).
    """
    input_A = kamera('A')
    input_B = kamera('B')
    input_C = kamera('C')
    input_D = kamera('D')
    
    # Undistortion placeholder - not in original code
    A_ud = input_A
    B_ud = input_B
    C_ud = input_C
    D_ud = input_D

    # Rotate images as per original script
    slikaA = cv2.rotate(A_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaB = cv2.rotate(B_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)
    slikaC = cv2.rotate(C_ud, cv2.ROTATE_90_CLOCKWISE)
    slikaD = cv2.rotate(D_ud, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # Apply small rotations using imutils with values from config
    slikaAf = imutils.rotate(slikaA, angle=A_rotation)
    slikaBf = imutils.rotate(slikaB, angle=B_rotation)
    slikaCf = imutils.rotate(slikaC, angle=C_rotation)
    slikaDf = imutils.rotate(slikaD, angle=D_rotation)

    # Apply vertical shift and crop with values from config
    A = crop_img(premik(slikaAf, Avp), crop_top, crop_bottom)
    B = crop_img(premik(slikaBf, Bvp), crop_top, crop_bottom)
    C = crop_img(premik(slikaCf, Cvp), crop_top, crop_bottom)
    D = crop_img(premik(slikaDf, Dvp), crop_top, crop_bottom)

    return A, B, C, D

# The main execution block for this module
if __name__ == "__main__":
    print("Running camera_utils.py as a script for testing.")
    
    # Initialize GPIO pins
    setup_gpio()

    # Capture an image from a specific camera and save it
    # This will test if the capture logic is working correctly
    test_image = kamera('A', save=True)

    if test_image is not None:
        print("Successfully captured and saved an image from camera A.")
    else:
        print("Failed to capture image from camera A.")

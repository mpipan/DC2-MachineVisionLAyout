import logging
import argparse
import os
import time
import cv2

# Import modules from the refactored project
import config
import mqtt_handler
import image_processing
import camera_calibration # NEW: Import the calibration module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_directories():
    """Ensure all necessary directories exist."""
    os.makedirs(config.OUTPUT_PATH, exist_ok=True)
    logger.info("All necessary directories are present.")

def run_capture_raw_test():
    """Tests only the camera capture stage."""
    logger.info("--- Running Standalone RAW CAPTURE Test ---")
    raw_images = image_processing.capture_and_prepare_images()
    if raw_images:
        logger.info("Raw capture test completed successfully. Check the output/ directory for raw images.")
    else:
        logger.error("Raw capture test failed.")

def run_process_only_test():
    """Tests only the image processing stage, using existing images."""
    logger.info("--- Running Standalone PROCESS ONLY Test ---")
    logger.warning("This test assumes A_raw.png, B_raw.png etc. already exist in the output/ folder.")
    
    raw_images = {}
    all_found = True
    for name in config.CAMERA_DEVICE_PATHS.keys():
        path = os.path.join(config.OUTPUT_PATH, f'{name}_raw.png')
        img = cv2.imread(path)
        if img is None:
            logger.error(f"Could not find or read image {path}. Please run a raw capture test first.")
            all_found = False
            break
        raw_images[name] = img

    if all_found and image_processing.process_and_save_images(raw_images):
        logger.info("Processing test completed successfully.")
    else:
        logger.error("Processing test failed.")

def run_full_test():
    """Runs the entire capture and processing pipeline once for testing."""
    logger.info("--- Running Standalone FULL Capture and Process Test ---")
    if image_processing.capture_and_process_all():
        logger.info("Full standalone test completed successfully.")
    else:
        logger.error("Full standalone test failed.")

def start_mqtt_listener():
    """Starts the MQTT client to listen for commands from the master."""
    logger.info("--- Starting MQTT Listener - Waiting for Master Commands ---")
    client = mqtt_handler.setup_mqtt_client()
    while True:
        try:
            client.connect(config.MASTER_IP, config.MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            logger.error(f"Connection to MQTT broker failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def main():
    """Main function to start the slave service."""
    parser = argparse.ArgumentParser(
        description="Run the slave camera service.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--listen', action='store_true', help='Run in normal listening mode, waiting for master commands.')
    parser.add_argument('--test-full', action='store_true', help='TEST: Run a single full capture-and-process sequence.')
    parser.add_argument('--test-capture-raw', action='store_true', help='TEST: Captures and saves only the raw images from cameras.')
    parser.add_argument('--test-process-only', action='store_true', help='TEST: Processes existing raw images without re-capturing.')
    parser.add_argument('--calibration', action='store_true', help='FIRST: Perform camera calibration using a checkerboard.')
    
    args = parser.parse_args()
    setup_directories()

    if args.listen:
        start_mqtt_listener()
    elif args.test_full:
        run_full_test()
    elif args.test_capture_raw:
        run_capture_raw_test()
    elif args.test_process_only:
        run_process_only_test()
    elif args.calibration:
        camera_calibration.run_camera_calibration()
    else:
        parser.print_help()
        logger.info("Please specify an execution mode, e.g., --listen to start the service.")

if __name__ == "__main__":
    logger.info("Starting slave camera service...")
    main()

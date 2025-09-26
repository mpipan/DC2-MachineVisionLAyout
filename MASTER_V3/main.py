import logging
import argparse
import time
import os
import cv2
import json

# Import modules from the refactored project
import config
import camera_utils
import image_processing
import mqtt_client
import thingsboard_client
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_directories():
    """Ensure all necessary directories exist."""
    os.makedirs(config.CAPTURED_PATH, exist_ok=True)
    os.makedirs(config.RECEIVED_PATH, exist_ok=True)
    os.makedirs(config.COMBINED_PATH, exist_ok=True)
    logger.info("All necessary directories are present.")

def run_full_pipeline():
    """
    Executes the entire centralized workflow:
    1. Requests data from the slave via MQTT.
    2. Captures images and processes modules on the master.
    3. Combines all data and images, draws all modules, and publishes the result.
    """
    logger.info("--- Starting Full Centralized Pipeline Execution ---")
    
    # Step 1: Request and receive slave data
    image_manager = mqtt_client.get_slave_data(timeout=30)
    if not image_manager:
        logger.error("Failed to get data from slave. Aborting full pipeline.")
        return False
        
    slave_coords = image_manager.get_slave_coords()
    slave_image_path = config.SLAVE_UNDRAWN_IMAGE_PATH
    
    if not os.path.exists(slave_image_path):
        logger.error(f"Slave image not found at {slave_image_path}. Did the slave process fail?")
        return False

    # Step 2: Capture and process master images
    master_images = camera_utils.capture_from_all_cameras()
    if not master_images:
        logger.error("Failed to capture images from all master cameras. Aborting.")
        return False
        
    master_stitched_image = image_processing.stitch_images(master_images)
    if master_stitched_image is None:
        logger.error("Master image stitching failed. Aborting.")
        return False
        
    # Step 3: Combine all data and perform final drawing
    all_module_coords = image_processing.combine_and_draw(
        slave_image_path,
        master_stitched_image,
        slave_coords
    )

    if not all_module_coords:
        logger.error("Final combination and drawing failed. Aborting.")
        return False
        
    # Step 4: Publish the final image and coordinates to ThingsBoard
    thingsboard_client.publish_to_thingsboard()
    
    logger.info("--- Full Pipeline Execution Finished Successfully ---")
    return True

def run_master_capture_only():
    """Captures and saves raw master images without processing."""
    logger.info("--- Starting Master Capture Only Test ---")
    master_images = camera_utils.capture_from_all_cameras()
    if master_images:
        logger.info(f"Successfully captured {len(master_images)} images. Check {config.CAPTURED_PATH}.")
    else:
        logger.error("Master capture test failed.")

def main():
    """Main function to start the master service."""
    parser = argparse.ArgumentParser(
        description="Run the master camera control system.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--full', action='store_true', help='Run the full pipeline.')
    parser.add_argument('--capture-only', action='store_true', help='Capture and save raw master images without processing.')
    
    args = parser.parse_args()
    setup_directories()

    if args.full:
        run_full_pipeline()
    elif args.capture_only:
        run_master_capture_only()
    else:
        # Default behavior if no arguments are given is to show help
        parser.print_help()
        logger.info("Please specify an execution mode, e.g., --full.")

if __name__ == "__main__":
    logger.info("Starting master camera service...")
    main()

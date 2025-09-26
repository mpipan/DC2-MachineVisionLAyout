import logging
import argparse
import time
import os

# Import modules from the refactored project
import config
import camera_utils
import image_processing
import mqtt_client
import thingsboard_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_directories():
    """Ensure all necessary directories exist."""
    os.makedirs(config.CAPTURED_PATH, exist_ok=True)
    os.makedirs(config.RECEIVED_PATH, exist_ok=True)
    os.makedirs(config.COMBINED_PATH, exist_ok=True)
    logger.info("All necessary directories are present.")

def run_slave_communication():
    """Handles communication with the slave Pi to get its data."""
    logger.info("--- Starting Slave Communication Step ---")
    success = mqtt_client.get_slave_data(timeout=30)
    if not success:
        logger.error("Failed to get data from slave. Exiting.")
        return False
    logger.info("--- Slave Communication Step Finished ---")
    return True

def run_master_capture_and_process():
    """Captures images from the 4 master cameras and processes them."""
    logger.info("--- Starting Master Capture and Process Step ---")
    
    # 1. Capture images from the 4 USB cameras
    master_images = camera_utils.capture_from_all_cameras()
    if len(master_images) < 4:
        logger.error("Failed to capture images from all master cameras. Exiting.")
        return False
    
    # 2. Process the captured images
    image_processing.process_master_images(master_images)
    
    logger.info("--- Master Capture and Process Step Finished ---")
    return True

def run_combination_and_publish():
    """Combines data from master and slave, and publishes to ThingsBoard."""
    logger.info("--- Starting Combination and Publish Step ---")

    # 1. Combine coordinates from master and slave JSON files
    image_processing.combine_master_slave_coordinates()

    # 2. Join the master and slave images vertically
    image_processing.join_master_slave_images()

    # 3. Convert final coordinates to cm
    image_processing.convert_final_coords_to_cm()

    # 4. Publish data and image to ThingsBoard
    thingsboard_client.publish_to_thingsboard()

    logger.info("--- Combination and Publish Step Finished ---")
    return True

def main():
    """Main function to orchestrate the camera system workflow."""
    parser = argparse.ArgumentParser(description="Run the master camera control system.")
    parser.add_argument('--full', action='store_true', help='Run the full pipeline.')
    parser.add_argument('--slave', action='store_true', help='Run only the slave communication part.')
    parser.add_argument('--master', action='store_true', help='Run only the master camera capture and processing.')
    parser.add_argument('--publish', action='store_true', help='Run only the combination and publishing part.')
    
    args = parser.parse_args()

    setup_directories()

    if args.slave:
        run_slave_communication()
    elif args.master:
        run_master_capture_and_process()
    elif args.publish:
        run_combination_and_publish()
    elif args.full:
        logger.info("Starting full pipeline execution...")
        if run_slave_communication():
            time.sleep(2) # Give a moment for files to be written
            if run_master_capture_and_process():
                time.sleep(2)
                run_combination_and_publish()
        logger.info("Full pipeline execution finished.")
    else:
        # Default behavior if no arguments are given is to show help
        parser.print_help()
        logger.info("Please specify an execution mode, e.g., --full.")

if __name__ == "__main__":
    logger.info("Starting master camera service...")
    main()

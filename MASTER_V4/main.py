import logging
import argparse
import time
import os
import threading

import config
import camera_utils
import image_processing
import mqtt_client
import thingsboard_client
import camera_calibration_master 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_directories():
    os.makedirs(config.CAPTURED_PATH, exist_ok=True)
    os.makedirs(config.RECEIVED_PATH, exist_ok=True)
    os.makedirs(config.COMBINED_PATH, exist_ok=True)
    logger.info("All necessary directories are present.")

def run_slave_communication():
    logger.info("--- Starting Slave Communication Step ---")
    success = mqtt_client.get_slave_data(timeout=30)
    if not success:
        logger.error("Failed to get data from slave. Exiting.")
        return False
    logger.info("--- Slave Communication Step Finished ---")
    return True

def run_master_capture_and_process():
    logger.info("--- Starting Master Capture and Process Step ---")
    master_images = camera_utils.capture_from_all_cameras()
    if len(master_images) < 4:
        logger.error("Failed to capture images from all master cameras. Exiting.")
        return False
    image_processing.process_master_images(master_images)
    logger.info("--- Master Capture and Process Step Finished ---")
    return True

def run_master_capture_only():
    logger.info("--- Starting Master Capture Only Step ---")
    master_images = camera_utils.capture_from_all_cameras()
    if len(master_images) < 4:
        logger.error("Failed to capture images from all master cameras.")
        return False
    logger.info(f"Successfully captured and saved {len(master_images)} raw images to '{config.CAPTURED_PATH}'.")
    logger.info("--- Master Capture Only Step Finished ---")
    return True

def run_combination_and_publish():
    logger.info("--- Starting Combination and Publish Step ---")
    image_processing.combine_master_slave_coordinates()
    # image_processing.join_master_slave_images()
    image_processing.join_master_slave_plain_images()
    image_processing.redraw_modules_on_final_image()
    image_processing.convert_final_coords_to_cm()
    thingsboard_client.publish_to_thingsboard()
    logger.info("--- Combination and Publish Step Finished ---")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Run the master camera control system.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--full', action='store_true', help='Run the full pipeline.')
    parser.add_argument('--slave', action='store_true', help='Run only the slave communication part.')
    parser.add_argument('--master', action='store_true', help='Run only the master camera capture and processing.')
    parser.add_argument('--publish', action='store_true', help='Run only the combination and publishing part.')
    parser.add_argument('--capture-only', action='store_true', help='Capture and save raw master images without processing.')
    parser.add_argument('--calibration', action='store_true', help='Perform camera calibration for the master.')
    
    args = parser.parse_args()
    setup_directories()

    if args.slave: run_slave_communication()
    elif args.master: run_master_capture_and_process()
    elif args.publish: run_combination_and_publish()
    elif args.capture_only: run_master_capture_only()
    elif args.calibration: camera_calibration_master.run_camera_calibration()
    elif args.full:
        logger.info("Starting full paralel pipeline execution...")

        # 1. Create a dictionary to hold the result from the slave thread
        slave_result = {'success': False}

        # Wrapper function for the slave thread to store its result
        def slave_task():
            logger.info("Slave communication thread started.")
            slave_result['success'] = run_slave_communication()
            logger.info("Slave communication thread finished.")

        # 2. Start the slave communication in a background thread
        slave_thread = threading.Thread(target=slave_task)
        slave_thread.start()

        # 3. Immediately start the master's work in the main thread
        master_success = run_master_capture_and_process()
        
        # 4. Wait for the slave thread to finish its work
        logger.info("Waiting for slave data...")
        slave_thread.join() # This blocks until the slave_thread is done
        
        # 5. Check results and proceed only if both were successful
        if master_success and slave_result['success']:
            run_combination_and_publish()
        else:
            logger.error("Pipeline failed. Master success: %s, Slave success: %s", 
                         master_success, slave_result['success'])

        logger.info("Full pipeline execution finished.")

    else:
        parser.print_help()
        logger.info("Please specify an execution mode, e.g., --full.")

if __name__ == "__main__":
    logger.info("Starting master camera service...")
    main()


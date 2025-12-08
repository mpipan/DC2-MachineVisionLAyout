
import logging
import time
import os
import threading
import json
import paho.mqtt.client as mqtt

import config
import camera_utils
import image_processing
import mqtt_client as slave_mqtt_client # Renamed to avoid confusion
import thingsboard_client



### How to Run the New System and Configure ThingsBoard

# On the Master Raspberry Pi:
# 1.  **Open a terminal** and start the image server (no changes here).
#     python web_server.py
#     
# 2.  **Open a *second* terminal** and start the new master service. **Note the new, simpler command without the --flags !**
#     python main.py
#
#     The script will now start and log that it's connected and listening. It will not do anything else until you press the button on the dashboard.



# --- Global State ---
is_processing = False
lock = threading.Lock()

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper functions to encapsulate parts of the pipeline for threading ---

def run_slave_communication_task(result_dict):
    """
    Wrapper function for slave communication to be run in a thread.
    Stores its success status in the provided dictionary.
    """
    logger.info("--- Starting Slave Communication Step (in parallel) ---")
    success = slave_mqtt_client.get_slave_data(timeout=30)
    if not success:
        logger.error("Failed to get data from slave.")
    result_dict['success'] = success
    logger.info("--- Slave Communication Step Finished ---")

def run_master_capture_and_process_task():
    """
    Encapsulates the master's camera capture and initial image processing.
    Returns True on success, False on failure.
    """
    logger.info("--- Starting Master Capture and Process Step (in parallel) ---")
    master_images = camera_utils.capture_from_all_cameras()
    if len(master_images) < 4:
        logger.error("Failed to capture images from all master cameras.")
        return False
    image_processing.process_master_images(master_images)
    logger.info("--- Master Capture and Process Step Finished ---")
    return True

# --- Core Pipeline Logic ---
def run_full_pipeline():
    """
    Encapsulates the entire end-to-end process, now with restored multithreading.
    """
    global is_processing
    with lock:
        if is_processing:
            logger.warning("Process is already running. Ignoring new request.")
            return
        is_processing = True
    
    try:
        logger.info(">>> Starting full pipeline execution triggered by RPC <<<")
        
        # --- Restored Parallel Execution from main-old.py ---
        # 1. Dictionary to hold the result from the slave thread
        slave_result = {'success': False}

        # 2. Start the slave communication in a background thread
        slave_thread = threading.Thread(target=run_slave_communication_task, args=(slave_result,))
        slave_thread.start()

        # 3. Immediately start the master's work in the main thread
        master_success = run_master_capture_and_process_task()
        
        # 4. Wait for the slave thread to finish its work
        logger.info("Waiting for slave data to finalize...")
        slave_thread.join() # This blocks until the slave_thread is done
        
        # 5. Check results and proceed only if both were successful
        if master_success and slave_result['success']:
            logger.info("--- Starting Final Combination and Publish Step ---")
            
            logger.info("Step 5.1: Combining master and slave coordinates...")
            image_processing.combine_master_slave_coordinates()

            logger.info("Step 5.2: Joining master and slave plain images...")
            image_processing.join_master_slave_plain_images()

            logger.info("Step 5.3: Redrawing modules on the final image...")
            image_processing.redraw_modules_on_final_image()

            logger.info("Step 5.4: Converting final coordinates to centimeters...")
            image_processing.convert_final_coords_to_cm()

            logger.info("Step 5.5: Publishing results to ThingsBoard...")
            thingsboard_client.publish_to_thingsboard()
            
            logger.info(">>> Full pipeline execution finished successfully. <<<")
        else:
            logger.error("Pipeline failed. Master success: %s, Slave success: %s", 
                         master_success, slave_result['success'])

    except Exception as e:
        logger.error(f"An unexpected error occurred during pipeline execution: {e}", exc_info=True)
    finally:
        with lock:
            is_processing = False
            logger.info("Process lock released.")


# --- ThingsBoard RPC Handling (No changes needed here) ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to ThingsBoard MQTT broker for RPC.")
        client.subscribe(config.THINGSBOARD_RPC_SUBSCRIBE_TOPIC)
        logger.info(f"Subscribed to RPC topic: {config.THINGSBOARD_RPC_SUBSCRIBE_TOPIC}")
    else:
        logger.error(f"Failed to connect to ThingsBoard, return code {rc}")

def on_message(client, userdata, msg):
    logger.info(f"Received message on topic {msg.topic}")
    try:
        data = json.loads(msg.payload)
        method = data.get("method")
        
        if method == "startFullProcess":
            logger.info("'startFullProcess' command received. Starting pipeline in a new thread.")
            pipeline_thread = threading.Thread(target=run_full_pipeline)
            pipeline_thread.start()
        else:
            logger.warning(f"Received unknown RPC method: {method}")
            
    except Exception as e:
        logger.error(f"Error processing RPC message: {e}")

# --- Main Service Execution ---
def main():
    """Main function to start the master service and listen for RPC commands."""
    setup_directories()
    
    rpc_client = mqtt.Client()
    #rpc_client = mqtt.Client(client_id=config.THINGSBOARD_USERNAME)
    rpc_client.username_pw_set(config.THINGSBOARD_USERNAME, config.THINGSBOARD_PASSWORD)
    rpc_client.on_connect = on_connect
    rpc_client.on_message = on_message
    
    logger.info("Master service starting. Connecting to ThingsBoard to listen for commands...")
    
    while True:
        try:
            rpc_client.connect(config.THINGSBOARD_HOST, config.THINGSBOARD_PORT, 60)
            rpc_client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

def setup_directories():
    os.makedirs(config.CAPTURED_PATH, exist_ok=True)
    os.makedirs(config.RECEIVED_PATH, exist_ok=True)
    os.makedirs(config.COMBINED_PATH, exist_ok=True)
    logger.info("All necessary directories are present.")


if __name__ == "__main__":
    main()


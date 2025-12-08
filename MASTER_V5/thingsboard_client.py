import paho.mqtt.client as mqtt
import json
import logging
import time
import os
import cv2
import numpy as np

import config
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ThingsBoardMQTT:
    # This class is unchanged
    def __init__(self, host, port, username, password):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.host = host
        self.port = port
        self.is_connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0: logger.info("Connected to ThingsBoard MQTT broker."); self.is_connected = True
        else: logger.error(f"Failed to connect to ThingsBoard, return code {rc}"); self.is_connected = False

    def _on_disconnect(self, client, userdata, rc):
        logger.info("Disconnected from ThingsBoard MQTT broker."); self.is_connected = False

    def connect(self):
        try:
            self.client.connect(self.host, self.port, 60); self.client.loop_start(); time.sleep(1)
        except Exception as e: logger.error(f"Error connecting to ThingsBoard: {e}")

    def disconnect(self):
        self.client.loop_stop(); self.client.disconnect()

    def publish(self, payload, topic):
        if not self.is_connected: logger.error("Not connected. Cannot publish."); return
        json_payload = json.dumps(payload, cls=NumpyEncoder)
        result = self.client.publish(topic, json_payload)
        if result.rc == 0: logger.info(f"Successfully published to topic '{topic}'")
        else: logger.error(f"Failed to publish to topic '{topic}'. MQTT Error Code: {result.rc}")

def publish_to_thingsboard():
    """Main function to prepare data and publish it to ThingsBoard."""
    logger.info("--- Starting ThingsBoard Publish Step ---")
    tb_client = ThingsBoardMQTT(config.THINGSBOARD_HOST, config.THINGSBOARD_PORT, config.THINGSBOARD_USERNAME, config.THINGSBOARD_PASSWORD)
    tb_client.connect()

    try:
        if not tb_client.is_connected:
            raise ConnectionError("Failed to connect to ThingsBoard broker.")
            
        # 1. Prepare a payload for ATTRIBUTES, starting with defaults
        attribute_payload = {}
        for key, value in config.DEFAULT_MODULE_VALUES.items():
            attribute_payload[f'Lokacija_X_{key}'] = value[0]
            attribute_payload[f'Lokacija_Y_{key}'] = value[1]
            attribute_payload[f'Rotacija_{key}'] = value[2]
        logger.info("Prepared attribute payload with default values.")

        # 2. Update the attribute payload with REAL data from the JSON file
        if os.path.exists(config.COORDS_IN_CM_PATH):
            with open(config.COORDS_IN_CM_PATH, 'r') as f:
                coords_data = json.load(f)
            
            for module_name, data in coords_data.items():
                # FIXED: Make script robust by checking for both new and old data formats
                
                # Check for new format (dictionary)
                if isinstance(data, dict) and 'center_cm' in data and data['center_cm']:
                    attribute_payload[f'Lokacija_X_{module_name}'] = data['center_cm'][0]
                    attribute_payload[f'Lokacija_Y_{module_name}'] = data['center_cm'][1]
                    attribute_payload[f'Rotacija_{module_name}'] = data.get('angle', 0)
                
                # Check for old format (list)
                elif isinstance(data, list) and len(data) == 3:
                    attribute_payload[f'Lokacija_X_{module_name}'] = data[0]
                    attribute_payload[f'Lokacija_Y_{module_name}'] = data[1]
                    attribute_payload[f'Rotacija_{module_name}'] = data[2]
                
                # Handle cases where data is invalid for this module
                else:
                    logger.warning(f"Module '{module_name}' has invalid or missing coordinate data. Skipping attribute update.")
            
            logger.info("Updated attribute payload with detected coordinates.")
        else:
            logger.warning(f"Coordinate file not found: {config.COORDS_IN_CM_PATH}")

        # 3. Publish the final coordinate data to the ATTRIBUTES topic
        if attribute_payload:
            tb_client.publish(attribute_payload, 'v1/devices/me/attributes')

        # 4. Process and publish the image URL as TELEMETRY
        # if os.path.exists(config.COMBINED_IMAGE_FINAL_PATH):
        #     logger.info("Resizing final image for web...")
        #     image = cv2.imread(config.COMBINED_IMAGE_FINAL_PATH)
        #     orig_h, orig_w = image.shape[:2]
        #     target_w = config.WEB_IMAGE_MAX_WIDTH
        #     ratio = target_w / float(orig_w)
        #     target_h = int(orig_h * ratio)
        #     resized_image = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
        #     cv2.imwrite(config.COMBINED_IMAGE_WEB_PATH, resized_image)
        #     logger.info(f"Saved web-optimized image to {config.COMBINED_IMAGE_WEB_PATH}")
            
        #     image_filename = os.path.basename(config.COMBINED_IMAGE_WEB_PATH)
        #     timestamp = int(time.time())
        #     image_url = f"http://{config.MASTER_IP}:{config.WEB_SERVER_PORT}/{image_filename}?v={timestamp}"

        #     logger.info(f"Publishing image URL to ThingsBoard telemetry...")
        #     telemetry_payload = {"Layout_URL": image_url}
        #     tb_client.publish(telemetry_payload, 'v1/devices/me/telemetry')
        # else:
        #     logger.warning(f"Final image file not found: {config.COMBINED_IMAGE_FINAL_PATH}")


        # 4. Process and publish the image URL and a timestamp as TELEMETRY
        telemetry_payload = {}
        current_timestamp = int(time.time() * 1000) # Get current time in milliseconds
        telemetry_payload["last_update"] = current_timestamp

        if os.path.exists(config.COMBINED_IMAGE_FINAL_PATH):
            logger.info("Resizing final image for web...")
            image = cv2.imread(config.COMBINED_IMAGE_FINAL_PATH)
            # ... (image resizing code is unchanged)
            orig_h, orig_w = image.shape[:2]
            target_w = config.WEB_IMAGE_MAX_WIDTH
            ratio = target_w / float(orig_w)
            target_h = int(orig_h * ratio)
            resized_image = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)
            cv2.imwrite(config.COMBINED_IMAGE_WEB_PATH, resized_image)
            logger.info(f"Saved web-optimized image to {config.COMBINED_IMAGE_WEB_PATH}")
            
            image_filename = os.path.basename(config.COMBINED_IMAGE_WEB_PATH)
            image_url = f"http://{config.MASTER_IP}:{config.WEB_SERVER_PORT}/{image_filename}?v={current_timestamp}"

            telemetry_payload["Layout_URL"] = image_url
        else:
            logger.warning(f"Final image file not found: {config.COMBINED_IMAGE_FINAL_PATH}")

        logger.info(f"Publishing telemetry data to ThingsBoard...")
        tb_client.publish(telemetry_payload, 'v1/devices/me/telemetry')


    except Exception as e:
        logger.error(f"An error occurred during ThingsBoard upload: {e}", exc_info=True)
    finally:
        logger.info("--- ThingsBoard Publish Step Finished ---")
        tb_client.disconnect()


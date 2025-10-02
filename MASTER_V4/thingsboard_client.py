import paho.mqtt.client as mqtt
import json
import logging
import time
import base64
import os

import config
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ThingsBoardMQTT:
    """Handles communication with the ThingsBoard MQTT broker."""
    def __init__(self, host, port, username, password):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.host = host
        self.port = port
        self.is_connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to ThingsBoard MQTT broker.")
            self.is_connected = True
        else:
            logger.error(f"Failed to connect to ThingsBoard, return code {rc}")
            self.is_connected = False

    def _on_disconnect(self, client, userdata, rc):
        logger.info("Disconnected from ThingsBoard MQTT broker.")
        self.is_connected = False

    def connect(self):
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            # Give it a moment to establish connection
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error connecting to ThingsBoard: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_telemetry(self, payload, topic='v1/devices/me/telemetry'):
        if not self.is_connected:
            logger.error("Not connected to ThingsBoard. Cannot publish telemetry.")
            return
        
        # The payload should be a JSON string
        json_payload = json.dumps(payload, cls=NumpyEncoder)
        result = self.client.publish(topic, json_payload)
        
        # Check if publish was successful
        if result.rc == 0:
            logger.info(f"Successfully published telemetry to topic '{topic}'")
        else:
            logger.error(f"Failed to publish telemetry. MQTT Error Code: {result.rc}")

def publish_to_thingsboard():
    """Main function to prepare data and publish it to ThingsBoard."""
    logger.info("--- Starting ThingsBoard Publish Step ---")
    tb_client = ThingsBoardMQTT(
        config.THINGSBOARD_HOST,
        config.THINGSBOARD_PORT,
        config.THINGSBOARD_USERNAME,
        config.THINGSBOARD_PASSWORD
    )
    tb_client.connect()

    try:
        if not tb_client.is_connected:
            raise ConnectionError("Failed to connect to ThingsBoard broker.")

        # 1. Reset all module values to default first
        logger.info("Resetting module values on ThingsBoard.")
        tb_client.publish_telemetry(config.DEFAULT_MODULE_VALUES)

        # 2. Publish the actual coordinates in cm
        if os.path.exists(config.COORDS_IN_CM_PATH):
            with open(config.COORDS_IN_CM_PATH, 'r') as f:
                coords_data = json.load(f)
            tb_client.publish_telemetry(coords_data)
        else:
            logger.warning(f"Coordinate file not found: {config.COORDS_IN_CM_PATH}")

        # 3. Publish the final combined image (no longer resized)
        if os.path.exists(config.COMBINED_IMAGE_FINAL_PATH):
            with open(config.COMBINED_IMAGE_FINAL_PATH, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            image_payload = {"Final_Image": f"data:image/jpeg;base64,{encoded_string}"}
            tb_client.publish_telemetry(image_payload)
        else:
            logger.warning(f"Final image file not found: {config.COMBINED_IMAGE_FINAL_PATH}")

    except Exception as e:
        logger.error(f"An error occurred during ThingsBoard upload: {e}")
    finally:
        logger.info("--- ThingsBoard Publish Step Finished ---")
        tb_client.disconnect()

if __name__ == "__main__":
    """Standalone test for the ThingsBoard client."""
    logger.info("Running thingsboard_client.py standalone for testing...")
    
    # Check that the necessary files exist before trying to publish
    if not os.path.exists(config.COORDS_IN_CM_PATH):
        logger.error(f"Missing required file for standalone test: {config.COORDS_IN_CM_PATH}")
    elif not os.path.exists(config.COMBINED_IMAGE_FINAL_PATH): # Check for final, not resized
        logger.error(f"Missing required file for standalone test: {config.COMBINED_IMAGE_FINAL_PATH}")
    else:
        publish_to_thingsboard()

import paho.mqtt.client as mqtt
import json
import logging
import threading
import time
import os
import cv2

import config
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageManager:
    """
    A thread-safe class to store data received from the slave.
    NEW: Now handles raw coordinates and a file path instead of images.
    """
    def __init__(self):
        self.slave_module_coords = {}
        self.lock = threading.Lock()
        
    def store_slave_coords(self, coords):
        with self.lock:
            self.slave_module_coords = coords
            
    def get_slave_coords(self):
        with self.lock:
            return self.slave_module_coords

class MQTTHandler:
    """
    MQTT client that listens for data from the slave.
    NEW: Now listens for raw coordinate data and a file path.
    """
    def __init__(self, image_manager):
        self.client = mqtt.Client()
        self.image_manager = image_manager
        self.data_received_event = threading.Event()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {config.SLAVE_IP}.")
            client.subscribe(config.MQTT_IMAGES_TOPIC)
            logger.info(f"Subscribed to topic: '{config.MQTT_IMAGES_TOPIC}'")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}\n")

    def _on_message(self, client, userdata, msg):
        """
        Callback for when a message is received from the slave.
        NEW: This now expects a JSON payload with module coordinates.
        """
        try:
            payload = json.loads(msg.payload.decode())
            
            # The slave now sends the coordinates directly.
            slave_coords = payload.get("module_coords_mm", {})
            
            if slave_coords:
                self.image_manager.store_slave_coords(slave_coords)
                logger.info(f"Received module coordinates from slave: {slave_coords.keys()}")
                self.data_received_event.set()
            else:
                logger.warning("Received a payload from slave but no module coordinates were found.")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON payload: {e}")
        except Exception as e:
            logger.error(f"Error processing received MQTT message: {e}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error(f"Unexpected disconnection from MQTT broker (Code: {rc}).")

    def request_images(self):
        """Sends a command to the slave to start its capture pipeline."""
        logger.info(f"Requesting capture from slave on topic '{config.MQTT_COMMAND_TOPIC}'...")
        self.client.publish(config.MQTT_COMMAND_TOPIC, "capture", qos=1)
        
    def start(self):
        """Starts the MQTT client loop."""
        try:
            self.client.connect(config.SLAVE_IP, config.MQTT_PORT, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect or start MQTT loop: {e}")
            
    def stop(self):
        """Stops the MQTT client loop."""
        self.client.loop_stop()
        self.client.disconnect()
        
def get_slave_data(timeout=30):
    """
    Handles the entire process of requesting and receiving data from the slave.
    Returns the ImageManager instance on success, or None on failure.
    """
    image_manager = ImageManager()
    mqtt_handler = MQTTHandler(image_manager)
    
    try:
        mqtt_handler.start()
        time.sleep(1) # Give a moment for the connection to establish
        mqtt_handler.request_images()
        
        # Wait for the data_received_event to be set, with a timeout
        logger.info(f"Waiting for data from slave... (timeout: {timeout}s)")
        received = mqtt_handler.data_received_event.wait(timeout)
        
        if received:
            logger.info("Slave data received successfully.")
            return image_manager
        else:
            logger.error("Timed out waiting for slave data.")
            return None
            
    except Exception as e:
        logger.error(f"An error occurred during slave communication: {e}")
        return None
    finally:
        mqtt_handler.stop()

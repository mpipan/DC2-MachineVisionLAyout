import paho.mqtt.client as mqtt
import json
import base64
import numpy as np
import cv2
import logging
import threading
import time
import os

import config
from utils import NumpyEncoder

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageManager:
    """A thread-safe class to store data received from the slave."""
    def __init__(self):
        self.remote_data = {}
        self.lock = threading.Lock()

    def store_data(self, key, value):
        with self.lock:
            self.remote_data[key] = value
            
    def get_data(self, key):
        with self.lock:
            return self.remote_data.get(key)

    def save_all_data(self):
        """Saves all received images and JSON data to files."""
        logger.info("Saving all received data from slave...")
        
        # Save images
        for key in ['zdruzena_brez_nic', 'rezultat_z_moduli']:
            image = self.get_data(key)
            if image is not None:
                # The key in the payload from the slave might be different from the final filename
                if key == 'zdruzena_brez_nic':
                    save_path = config.SLAVE_IMAGE_PATH
                else:
                    save_path = config.SLAVE_IMAGE_WITH_MODULES_PATH
                cv2.imwrite(save_path, image)
                logger.info(f"Saved slave image '{key}' to {save_path}")
        
        # Save coordinate data
        coords = self.get_data('koordinate')
        if coords:
            with open(config.SLAVE_COORDS_PATH, "w") as f:
                json.dump(coords, f, indent=4, cls=NumpyEncoder)
            logger.info(f"Saved slave coordinates to {config.SLAVE_COORDS_PATH}")


class MQTTHandler:
    """Handles MQTT connection and message processing."""
    def __init__(self, image_manager):
        self.client = mqtt.Client()
        self.image_manager = image_manager
        self.data_received_event = threading.Event()
        self._setup_client()

    def _setup_client(self):
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker successfully.")
            self.client.subscribe(config.MQTT_TOPIC_IMAGES)
        else:
            logger.error(f"Failed to connect to MQTT broker with result code: {rc}")

    def _on_message(self, client, userdata, msg):
        logger.info(f"Message received on topic {msg.topic}")
        if msg.topic == config.MQTT_TOPIC_IMAGES:
            try:
                payload = json.loads(msg.payload)
                
                # Process and store each piece of data from the payload
                for key, value in payload.items():
                    if 'image' in key or 'zdruzena' in key or 'rezultat' in key:
                        # Decode base64 image
                        image_bytes = base64.b64decode(value)
                        nparr = np.frombuffer(image_bytes, np.uint8)
                        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if image is not None:
                            self.image_manager.store_data(key, image)
                        else:
                            logger.warning(f"Failed to decode image for key: {key}")
                    else:
                        # Store other data (like coordinates) directly
                        self.image_manager.store_data(key, value)

                logger.info("Successfully processed and stored all remote data.")
                self.data_received_event.set() # Signal that data has been received

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection with code {rc}.")

    def start(self):
        """Connects to the broker and starts the client loop in a new thread."""
        try:
            self.client.connect(config.MQTT_BROKER_HOST, config.MQTT_BROKER_PORT, config.MQTT_KEEPALIVE)
            self.client.loop_start()
            logger.info("MQTT handler started.")
        except Exception as e:
            logger.error(f"Failed to start MQTT handler: {e}")
            raise

    def stop(self):
        """Stops the MQTT client loop and disconnects."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT handler stopped.")

    def request_images(self):
        """Publishes a command to the slave to capture and send images."""
        self.client.publish(config.MQTT_TOPIC_COMMAND, 'capture')
        logger.info(f"Sent 'capture' command to slave on topic '{config.MQTT_TOPIC_COMMAND}'.")

def get_slave_data(timeout=30):
    """
    Initializes MQTT communication, requests data from the slave,
    and waits for the data to be received.
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
            image_manager.save_all_data()
            return True
        else:
            logger.error("Timed out waiting for slave data.")
            return False
            
    except Exception as e:
        logger.error(f"An error occurred during slave communication: {e}")
        return False
    finally:
        mqtt_handler.stop()

if __name__ == "__main__":
    """
    This block allows running the MQTT client module independently for testing.
    It will attempt to connect, request data, and save it.
    """
    logger.info("Running mqtt_client.py standalone for testing...")
    
    # Ensure the output directory exists
    if not os.path.exists(config.RECEIVED_PATH):
        os.makedirs(config.RECEIVED_PATH)
        logger.info(f"Created directory: {config.RECEIVED_PATH}")

    success = get_slave_data(timeout=45)
    
    if success:
        logger.info("Standalone test finished successfully.")
    else:
        logger.error("Standalone test failed.")

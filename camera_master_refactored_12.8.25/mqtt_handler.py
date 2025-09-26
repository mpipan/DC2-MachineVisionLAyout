import paho.mqtt.client as mqtt
import json
import logging
import numpy as np

# Import configuration
from config import MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE, logger
from json_encoder import NumpyEncoder

class MQTTHandler:
    """Handles MQTT communication for the master camera service."""
    def __init__(self):
        self.client = mqtt.Client()
        self.setup_client()
        
    def setup_client(self):
        """Configures the MQTT client callbacks."""
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        
    def start(self):
        """Starts the MQTT client and connects to the broker."""
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            logger.info("MQTT handler started successfully")
        except Exception as e:
            logger.error(f"Failed to start MQTT handler: {e}")
            raise
        
    def stop(self):
        """Stops the MQTT client."""
        self.client.loop_stop()
        
    def request_images(self):
        """Publishes a command to the slave to capture and send images."""
        self.client.publish('camera/command', 'capture')
        logger.info("Sent capture command to slave")
        
    def publish_to_thingsboard(self, data):
        """
        Publishes processed telemetry data to ThingsBoard.
        
        Args:
            data (dict): The dictionary containing module properties.
        """
        try:
            payload = json.dumps(data, cls=NumpyEncoder)
            self.client.publish('v1/devices/me/telemetry', payload)
            logger.info("Published data to ThingsBoard.")
        except Exception as e:
            logger.error(f"Failed to publish data to ThingsBoard: {e}")
            
    def on_connect(self, client, userdata, flags, rc):
        """Callback for successful connection to the MQTT broker."""
        logger.info(f"Connected to MQTT broker with result code: {rc}")
        self.client.subscribe('camera/images')
        
    def on_message(self, client, userdata, msg):
        """Handles incoming MQTT messages."""
        logger.info(f"Message received on topic {msg.topic}")
                
    def on_disconnect(self, client, userdata, rc):
        """Callback for unexpected MQTT disconnection."""
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection with code {rc}. Will attempt to reconnect.")

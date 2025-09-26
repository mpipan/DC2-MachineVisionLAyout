import paho.mqtt.client as mqtt
import logging
import json

import config
import image_processing # Import the processing module

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- MQTT Callback Functions ---

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {config.MASTER_IP}.")
        # Subscribe to the command topic from the master
        client.subscribe(config.MQTT_COMMAND_TOPIC)
        logger.info(f"Subscribed to topic: '{config.MQTT_COMMAND_TOPIC}'")
    else:
        logger.error(f"Failed to connect to MQTT broker, return code {rc}\n")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the broker."""
    command = msg.payload.decode()
    logger.info(f"Received command '{command}' on topic '{msg.topic}'")
    
    if msg.topic == config.MQTT_COMMAND_TOPIC and command == "capture":
        # The master has requested a capture.
        # Run the entire pipeline and get the payload.
        logger.info("'capture' command received. Starting processing pipeline...")
        payload = image_processing.capture_and_process_all()
        
        if payload:
            # Serialize the payload dictionary to a JSON string
            # The NumpyEncoder is crucial here because the payload contains numpy arrays.
            json_payload = json.dumps(payload, cls=image_processing.NumpyEncoder)
            
            # Publish the results back to the master
            client.publish(config.MQTT_IMAGES_TOPIC, json_payload, qos=1)
            logger.info(f"Successfully published results to topic '{config.MQTT_IMAGES_TOPIC}'")
        else:
            logger.error("Processing pipeline failed. Nothing to publish.")
            
    else:
        logger.warning(f"Unknown command or topic. Ignoring message.")

def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects."""
    if rc != 0:
        logger.error(f"Unexpected disconnection from MQTT broker (Code: {rc}).")

# --- Setup Function ---

def setup_mqtt_client():
    """Creates and configures an MQTT client instance."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    return client

import paho.mqtt.client as mqtt
import time
import json
import logging
import base64
import numpy as np

# Import all modules from the refactored structure
from config import logger, setup_gpio, setup_camera_mux, MASTER_IP, PORT, USERNAME, PASSWORD
from image_processing import capture_and_process_images
from network_handler import TCPImageClient

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    """Callback for successful connection to the MQTT broker."""
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        # Subscribe to the command topic from the master
        client.subscribe('camera/command')
    else:
        logger.error(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """
    Callback for handling incoming MQTT messages.
    This is the main trigger for the slave's operation.
    """
    logger.info(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
    
    if msg.topic == 'camera/command' and msg.payload.decode() == 'capture':
        logger.info("Received 'capture' command from master. Starting image processing...")
        try:
            # Step 1: Capture, process, and get the results
            processed_data = capture_and_process_images()
            
            if processed_data:
                logger.info("Image processing successful. Sending data to master via TCP...")
                
                # Step 2: Send the results to the master via TCP
                client_tcp = TCPImageClient(MASTER_IP, 65432)
                client_tcp.send_data(processed_data)
                
            else:
                logger.error("Image processing failed, no data to send.")
                
        except Exception as e:
            logger.error(f"An error occurred during capture and send: {e}")

def on_disconnect(client, userdata, rc):
    """Callback for unexpected MQTT disconnection."""
    logger.error(f"Disconnected with result code: {rc}")
    if rc != 0:
        logger.error("Unexpected disconnection. Will attempt to reconnect...")

def main():
    """
    Main function for the slave camera service.
    This function sets up the MQTT client and starts the main loop to listen for commands.
    """
    logger.info("Script has been started!!!")
    
    # Initialize GPIO pins
    setup_gpio()

    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    while True:
        try:
            logger.info(f"Attempting to connect to MQTT broker at {MASTER_IP}:{PORT}")
            client.connect(MASTER_IP, PORT, 60)
            logger.info("Connected successfully.")
            client.loop_forever()
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            logger.info("Retrying connection in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()

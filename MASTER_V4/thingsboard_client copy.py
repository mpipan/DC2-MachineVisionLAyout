import paho.mqtt.client as mqtt
import json
import base64
import time
import logging
import io
from PIL import Image

import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _resize_and_encode_image(image_path, max_size=(800, 800), quality=30):
    """Resizes, compresses, and base64-encodes an image for upload."""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size)  # Resize while maintaining aspect ratio
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            encoded_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
            logger.info(f"Resized and encoded image. New base64 length: {len(encoded_string)}")
            return encoded_string
    except FileNotFoundError:
        logger.error(f"Image file not found for encoding: {image_path}")
        return None
    except Exception as e:
        logger.error(f"Error encoding image: {e}")
        return None

def _upload_data(client, data_dict):
    """Publishes a dictionary of attributes to ThingsBoard with retry logic."""
    payload = json.dumps(data_dict)
    retry_count = 0
    backoff_time = config.THINGSBOARD_INITIAL_BACKOFF

    while retry_count < config.THINGSBOARD_RETRY_LIMIT:
        result = client.publish('v1/devices/me/attributes', payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Successfully published attributes: {list(data_dict.keys())}")
            return True
        
        logger.warning(f"Failed to send message (Status: {result.rc}). Retrying in {backoff_time}s...")
        time.sleep(backoff_time)
        retry_count += 1
        backoff_time *= 2  # Exponential backoff

    logger.error(f"Failed to publish attributes after {config.THINGSBOARD_RETRY_LIMIT} attempts.")
    return False

def publish_to_thingsboard():
    """
    Main function to publish all data to ThingsBoard.
    - Resets old module values.
    - Uploads new module coordinates.
    - Uploads the final composite image.
    """
    logger.info("--- Starting ThingsBoard Publish Step ---")

    client = mqtt.Client()
    client.username_pw_set(config.THINGSBOARD_USERNAME, config.THINGSBOARD_PASSWORD)

    try:
        client.connect(config.THINGSBOARD_HOST, config.THINGSBOARD_PORT, 60)
        client.loop_start()
        logger.info("Connected to ThingsBoard MQTT broker.")

        # 1. Reset old values by sending default data
        logger.info("Resetting module values on ThingsBoard.")
        _upload_data(client, config.DEFAULT_MODULE_VALUES)
        time.sleep(1) # Pause between major uploads

        # 2. Load and upload new coordinates
        try:
            with open(config.COORDS_IN_CM_PATH, "r") as f:
                new_coords = json.load(f)
            
            if new_coords:
                logger.info("Uploading new module coordinates to ThingsBoard.")
                formatted_coords = {}
                for key, value in new_coords.items():
                    formatted_coords[f'Lokacija_X_{key}'] = value[0]
                    formatted_coords[f'Lokacija_Y_{key}'] = value[1]
                    formatted_coords[f'Rotacija_{key}'] = value[2]
                _upload_data(client, formatted_coords)
            else:
                logger.warning("No new module coordinates found to upload.")
        except FileNotFoundError:
            logger.error(f"Coordinate file not found: {config.COORDS_IN_CM_PATH}")
        
        time.sleep(1)

        # 3. Upload the new composite image
        logger.info("Uploading new composite image to ThingsBoard.")
        encoded_image = _resize_and_encode_image(config.COMBINED_IMAGE_RESIZED_PATH)
        if encoded_image:
            image_payload = {config.THINGSBOARD_IMAGE_ATTRIBUTE: encoded_image}
            _upload_data(client, image_payload)

    except Exception as e:
        logger.error(f"An error occurred during ThingsBoard upload: {e}")
    finally:
        logger.info("--- ThingsBoard Publish Step Finished ---")
        client.loop_stop()
        client.disconnect()
        logger.info("Disconnected from ThingsBoard MQTT broker.")

if __name__ == "__main__":
    """
    This block allows running the ThingsBoard client module independently for testing.
    It will attempt to connect and upload the data currently in the combined/ folder.
    """
    logger.info("Running thingsboard_client.py standalone for testing...")
    publish_to_thingsboard()
    logger.info("Standalone test finished.")

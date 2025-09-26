import time
import os
import cv2
import json
import itertools
import numpy as np
import threading
from queue import Queue

# Import the new modules
from config import logger, setup_gpio, crop_top, crop_bottom
from mqtt_handler import MQTTHandler
from network_handler import TCPImageServer
from json_encoder import NumpyEncoder
from image_processing import decode, conversion_factor, skaliranje, calculate_module_properties, background, premik_koordinat
from visualization import plot_result

# Setting up matplotlib and PIL logging to avoid verbose output
import logging
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.ERROR)

def main():
    """
    The main master camera service that orchestrates all operations.
    
    This function sets up the GPIO pins, starts the TCP server in a separate thread
    to receive images from the slave, and starts the MQTT client. It then enters
    a main loop to process received data and publish results.
    """
    logger.info("Starting master camera service...")

    # Initialize GPIO pins
    try:
        setup_gpio()
    except Exception as e:
        logger.error(f"Failed to set up GPIO pins: {e}")
        return

    # Create a queue to hold data received from the slave server thread
    image_queue = Queue()

    # Initialize and start the TCP server thread
    server_thread = TCPImageServer(image_queue)
    server_thread.start()
    logger.info("TCP server thread started.")

    # Initialize MQTT handler WITHOUT the image_manager
    mqtt_handler = MQTTHandler()
    mqtt_handler.start()
    logger.info("MQTT handler started.")

    try:
        # Main application loop
        while True:
            # Wait for data to be put into the queue by the TCP server
            # This is a blocking call, the program waits here until data arrives
            logger.info("Waiting for image data from slave...")
            received_data = image_queue.get()
            
            # Use a short timeout to prevent blocking indefinitely
            # received_data = image_queue.get(timeout=300)

            # Process the received data (which is a dictionary from the slave)
            if received_data:
                logger.info("Received image data from slave.")
                
                # Extract and save data
                zdruzena_brez_nic = received_data.get('zdruzena_brez_nic')
                rezultat_z_moduli = received_data.get('rezultat_z_moduli')
                koordinate = received_data.get('koordinate', {})
                koordinate_skalirane = received_data.get('koordinate_skalirane', {})
                koordinate_skalirane_dvignjene = received_data.get('koordinate_skalirane_dvignjene', {})

                # --- Save the images and coordinates ---
                base_path = "/home/cameramodule/Desktop/received"
                os.makedirs(base_path, exist_ok=True)

                cv2.imwrite(os.path.join(base_path, "zdruzena_slika_slave.jpg"), zdruzena_brez_nic)
                cv2.imwrite(os.path.join(base_path, "zdruzena_slika_slave_z_moduli.jpg"), rezultat_z_moduli)
                
                with open(os.path.join(base_path, "koordinate.json"), "w") as f:
                    json.dump(koordinate, f, indent=4, cls=NumpyEncoder)
                
                with open(os.path.join(base_path, "koordinate_skalirane.json"), "w") as f:
                    json.dump(koordinate_skalirane, f, indent=4, cls=NumpyEncoder)       
                
                with open(os.path.join(base_path, "koordinate_skalirane_dvignjene.json"), "w") as f:
                    json.dump(koordinate_skalirane_dvignjene, f, indent=4, cls=NumpyEncoder)
                
                logger.info("Saved all data to disk.")

                # PUBLISH TO THINGSBOARD
                mqtt_handler.publish_to_thingsboard(koordinate_skalirane_dvignjene)
                
                # VISUALIZE THE RESULTS
                # The original code's plotting function is a bit generic
                # I've used placeholder values here, you'll need to adjust them
                plot_result(2000, rezultat_z_moduli, 0.065, 0, 0)
            
            # This is a continuous loop, so we wait before checking the queue again
            # if we are not blocking. With queue.get() it's blocking so this is
            # not strictly necessary, but good practice for other async models.
            # time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        logger.exception("Full traceback:")
    finally:
        server_thread.stop()
        mqtt_handler.stop()
        logger.info("Application shut down.")


if __name__ == "__main__":
    print("Script has been started!!!")
    main()

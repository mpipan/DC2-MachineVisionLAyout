import http.server
import socketserver
import os
import logging

""" 
!!!!!!!!!!!!!README!!!!!!!!!!!!

To run the web server that serves the combined images for ThingsBoard, follow these steps:
1.  **Open a *first* terminal** and run the web server.
python web_server.py

2.  **Open a *second* terminal** and run your main process as usual.
python main.py --full
"""

# --- Configuration ---
# Use the same base path as your main application
BASE_PATH = "/home/cameramodule/Desktop"
IMAGE_DIR = os.path.join(BASE_PATH, "combined")
PORT = 8000

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Custom Handler to serve files from the correct directory ---
class ImageHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # We must change the directory *before* initializing the parent class
        super().__init__(*args, directory=IMAGE_DIR, **kwargs)

    def log_message(self, format, *args):
        # Log requests to the console using our logger
        logger.info(f"{self.address_string()} - {args[0]} {args[1]}")

# --- Main execution ---
if __name__ == "__main__":
    # Ensure the directory we want to serve exists
    if not os.path.isdir(IMAGE_DIR):
        logger.error(f"Image directory '{IMAGE_DIR}' not found. Please create it or check the path.")
        exit(1)

    with socketserver.TCPServer(("", PORT), ImageHandler) as httpd:
        logger.info(f"Serving images from '{IMAGE_DIR}' at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Stopping the server.")
            httpd.server_close()

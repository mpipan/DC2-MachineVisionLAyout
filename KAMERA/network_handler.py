import socket
import struct
import pickle
import numpy as np
import json
import base64
import cv2
import io
from PIL import Image

# Import configuration
from config import logger

class TCPImageClient:
    """
    A TCP client to send processed data to the master server.
    """
    def __init__(self, master_ip, port):
        self.master_ip = master_ip
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def connect(self):
        """Connects to the master server."""
        try:
            self.client_socket.connect((self.master_ip, self.port))
            logger.info(f"Connected to master at {self.master_ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to master: {e}")
            return False

    def send_data(self, data):
        """
        Serializes and sends the entire data dictionary, including images,
        to the master.
        
        Args:
            data (dict): The dictionary containing images and coordinates.
        """
        if not self.connect():
            return
        
        try:
            # The master expects images as base64-encoded strings,
            # so we encode them here before pickling.
            for key in ['zdruzena_brez_nic', 'rezultat_z_moduli']:
                img = data.get(key)
                if img is not None:
                    _, buffer = cv2.imencode('.jpg', img)
                    data[key] = base64.b64encode(buffer).decode('utf-8')
                    
            serialized_data = pickle.dumps(data)
            message = struct.pack("Q", len(serialized_data)) + serialized_data
            self.client_socket.sendall(message)
            logger.info("Successfully sent data to master.")
        except Exception as e:
            logger.error(f"Failed to send data to master: {e}")
        finally:
            self.client_socket.close()
            logger.info("Connection closed.")


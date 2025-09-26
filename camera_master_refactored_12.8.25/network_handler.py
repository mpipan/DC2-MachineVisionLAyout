import threading
import socket
import struct
import pickle
import numpy as np
from queue import Queue
import json
import base64
import cv2

# Import configuration
from config import logger, SLAVE_IP

class TCPImageServer(threading.Thread):
    """
    A TCP server running in a separate thread to receive image data from a slave.
    """
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('', 65432)) # Port can be configured
        self.server_socket.listen(5)
        logger.info("TCP server listening on port 65432")

    def run(self):
        """Main loop for the server thread."""
        while self.running:
            conn, addr = self.server_socket.accept()
            logger.info(f"Connection established from {addr}")
            
            data_buffer = b""
            payload_size = struct.calcsize("Q")
            
            try:
                while self.running:
                    while len(data_buffer) < payload_size:
                        packet = conn.recv(4096)
                        if not packet:
                            break
                        data_buffer += packet
                    if not packet:
                        break
                    
                    packed_msg_size = data_buffer[:payload_size]
                    data_buffer = data_buffer[payload_size:]
                    msg_size = struct.unpack("Q", packed_msg_size)[0]
                    
                    while len(data_buffer) < msg_size:
                        data_buffer += conn.recv(4096)
                    
                    frame_data = data_buffer[:msg_size]
                    data_buffer = data_buffer[msg_size:]
                    
                    # Deserialize the received data
                    received_dict = pickle.loads(frame_data)
                    
                    # Process and decode images from the dictionary
                    if 'zdruzena_brez_nic' in received_dict:
                        image_bytes = base64.b64decode(received_dict['zdruzena_brez_nic'])
                        nparr = np.frombuffer(image_bytes, np.uint8)
                        received_dict['zdruzena_brez_nic'] = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if 'rezultat_z_moduli' in received_dict:
                        image_bytes = base64.b64decode(received_dict['rezultat_z_moduli'])
                        nparr = np.frombuffer(image_bytes, np.uint8)
                        received_dict['rezultat_z_moduli'] = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # Place the decoded dictionary into the queue for the main thread
                    self.queue.put(received_dict)

            except Exception as e:
                logger.error(f"Error in TCP server loop: {e}")
            finally:
                conn.close()
                logger.info("Connection closed.")

    def stop(self):
        """Stops the server thread gracefully."""
        self.running = False
        self.server_socket.close()
        logger.info("TCP server shut down.")

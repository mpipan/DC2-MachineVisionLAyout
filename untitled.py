import os

with open("/home/cameramodule/Desktop/combined/combined.jpg", "rb") as f:
    encoded = base64.b64encode(f.read()).decode("utf-8")
    print(f"Base64 image size: {len(encoded)} characters")

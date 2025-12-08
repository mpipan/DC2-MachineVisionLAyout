import requests
import json
import time

# ================= CONFIGURATION =================
# ThingsBoard URL Derived from your settings: http:// + THINGSBOARD_HOST + :8080
TB_URL = "http://192.168.9.108:8080"

# Login Credentials (User who has permission to control the device)
USERNAME = "filip.j.vuzem@digiteh.eu"
PASSWORD = "eeKhruIDPwDCRrF"

# The ID of the Device running the Master Script (NOT the Name, the UUID)
# Find this in Devices -> Click Device -> Copy Device ID
DEVICE_ID = "5e5f66e0-3485-11ef-af17-0d3effa9188f"

# The RPC Method name. This MUST match the method name defined in your 
# Dashboard Button widget settings and your Master Script's RPC handler.
RPC_METHOD = "startFullProcess" 
RPC_PARAMS = {} # Any parameters needed (often empty for simple buttons)

# Loop settings
LOOP_MODE = False       # Set to False to run only once
DELAY_SECONDS = 40     # Delay between triggers if looping
# =================================================

def get_jwt_token():
    """Authenticates with ThingsBoard and returns a JWT token."""
    login_url = f"{TB_URL}/api/auth/login"
    try:
        response = requests.post(login_url, json={"username": USERNAME, "password": PASSWORD})
        response.raise_for_status()
        token_data = response.json()
        return token_data['token']
    except requests.exceptions.RequestException as e:
        print(f"[!] Login Failed: {e}")
        return None

def trigger_rpc(token):
    """Sends the RPC command to the specific device."""
    # Endpoint for One-Way RPC (Fire and forget). 
    # Use /twoway/{DEVICE_ID} if you need a response from the master script.
    rpc_url = f"{TB_URL}/api/plugins/rpc/oneway/{DEVICE_ID}"
    
    headers = {
        "Content-Type": "application/json",
        "X-Authorization": f"Bearer {token}"
    }
    
    payload = {
        "method": RPC_METHOD,
        "params": RPC_PARAMS
    }

    try:
        print(f"[*] Sending trigger command '{RPC_METHOD}' to device...")
        response = requests.post(rpc_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print("[+] Trigger sent successfully!")
        else:
            print(f"[!] Trigger failed. Status Code: {response.status_code}")
            print(f"    Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Connection Error: {e}")

def main():
    print("--- Simulation Trigger Script Started ---")
    
    # Initial Login
    token = get_jwt_token()
    if not token:
        return

    while True:
        trigger_rpc(token)

        if not LOOP_MODE:
            break

        print(f"[*] Waiting {DELAY_SECONDS} seconds for next snapshot...")
        time.sleep(DELAY_SECONDS)
        
        # Optional: Refresh token logic could go here for very long running scripts,
        # but for simple testing, re-logging in on failure is often easier.

if __name__ == "__main__":
    main()
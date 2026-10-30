import os
import paho.mqtt.client as mqtt
import requests
import logging
import sys
import threading
import time

# Configuration (DO NOT CHANGE THESE VALUES)
MQTT_BROKER = "35.232.45.67"
MQTT_PORT = 1883
MQTT_TOPIC = "speed"
MQTT_USERNAME = "KTS_EKCO"
MQTT_PASSWORD = "Ekco@prado123!"
CLOUD_FUNCTION_URL = "https://us-central1-ksdiv-3ba17.cloudfunctions.net/speed"

# -----------------------------------------------------------------------------
# Logging Configuration
# Determines the log file path based on the operating system to ensure cross-platform compatibility.
log_file_name = "ekco_speed_error.log"
if sys.platform.startswith('win'): # Checks if the operating system is Windows
    # On Windows, logs will be saved in the same directory as the script.
    log_file_path = log_file_name
else: # Assumes Linux/macOS or other Unix-like systems
    # On Linux/macOS, logs will be saved in the /home/ksdivision59 directory.
    log_file_path = os.path.join("/home/ksdivision59", log_file_name)

logging.basicConfig(
    level=logging.INFO, # Default logging level. Change to logging.DEBUG for more verbose output.
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Outputs logs to the console for real-time monitoring
    ]
)
# -----------------------------------------------------------------------------

# Callback function, executed when a message is received from the MQTT broker
def on_message(client, userdata, msg):
    try:
        # Decode the incoming message payload from bytes to a UTF-8 string
        message = msg.payload.decode("utf-8")
        logging.info(f"Received MQTT message: Topic='{msg.topic}', Payload='{message}'")

        # --- BUG FIX: Robust Message Splitting ---
        # The message is expected to have exactly 2 comma-separated parts (serial_number, msg_content).
        # We use split(..., 1) to ensure that if the 'msg' content itself contains commas,
        # it is not further split, and then explicitly check the number of parts.
        parts = message.split(",", 1) # Split only on the first comma

        if len(parts) == 2:
            # Unpack the parts into their respective variables if the format is correct
            serial_number, msg_content = parts
        else:
            # If the format is incorrect, log a warning and stop processing this message
            logging.warning(f"MQTT message format error: Expected 'serial_number,message_content', but received {len(parts)} parts for message: '{message}'. Skipping processing.")
            return # Exit the function for this malformed message

        # Prepare the data to be sent as a JSON payload to the Google Cloud Function.
        # All data is concatenated into a single string under the "data" key.
        data = {
            "data": f"{serial_number},{msg_content}"
        }
        logging.debug(f"Prepared data for Cloud Function POST: {data}")

        # Send an HTTP POST request to the Cloud Function URL
        response = requests.post(CLOUD_FUNCTION_URL, json=data)

        # Log the outcome of the POST request based on the HTTP status code
        if response.status_code == 200:
            logging.info(f"Successfully sent speed data for serial '{serial_number}' to Cloud Function. Response: {response.text}")
        else:
            logging.error(f"Failed to send speed data for serial '{serial_number}' to Cloud Function. "
                          f"HTTP Status Code: {response.status_code}, Response Body: {response.text}")

    except requests.exceptions.RequestException as e:
        # Catch specific exceptions related to network issues (e.g., connection errors, timeouts) during the HTTP request
        logging.error(f"Network error while sending data to Cloud Function: {e}")
    except Exception as e:
        # Catch any other unexpected errors that might occur during message processing
        # 'exc_info=True' ensures the full Python traceback is included in the log for debugging
        logging.error(f"An unexpected error occurred in on_message: {e}", exc_info=True)

# Callback function, executed when the MQTT client connects to the broker
# --- BUG FIX: Added 'properties' argument for CallbackAPIVersion.VERSION2 ---
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0: # 'rc' (return code) 0 indicates a successful connection
        logging.info("Connected to MQTT Broker successfully!")
        client.subscribe(MQTT_TOPIC) # Subscribe to the configured MQTT topic
        logging.info(f"Subscribed to topic: '{MQTT_TOPIC}'")
    else:
        # Log an error if the connection fails, providing the return code for diagnosis
        logging.error(f"Failed to connect to MQTT Broker, return code: {rc}. "
                      "Please verify MQTT_BROKER IP, MQTT_PORT, and MQTT_USERNAME/MQTT_PASSWORD.")

# Create an MQTT client instance
# --- BUG FIX: Specified CallbackAPIVersion.VERSION2 to avoid DeprecationWarning ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Set the authentication credentials for the MQTT broker connection
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Assign the custom callback functions to the client's event handlers
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Attempt to establish a connection to the MQTT broker
try:
    logging.info(f"Attempting to connect to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}...")
    # 'connect' method will block until connection is established or fails.
    # '60' is the keepalive interval in seconds.
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
except Exception as e:
    # If the connection fails for any reason, log a critical error and terminate the script
    logging.critical(f"Could not establish connection to MQTT Broker: {e}. Exiting script.")
    sys.exit(1) # Exit with a non-zero status code to indicate an error

# Start the MQTT client's network loop indefinitely.
# This keeps the script running, listening for incoming MQTT messages, and dispatching callbacks.
# --- Heartbeat for external watchdog ---
HEARTBEAT_PATH = "/app/heartbeats/ekco_speed.timestamp"

def heartbeat_writer():
    os.makedirs(os.path.dirname(HEARTBEAT_PATH), exist_ok=True)
    while True:
        try:
            with open(HEARTBEAT_PATH, "w") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        time.sleep(15)

threading.Thread(target=heartbeat_writer, daemon=True).start()

logging.info("MQTT client started. Waiting for messages. To exit press CTRL+C")
mqtt_client.loop_forever()
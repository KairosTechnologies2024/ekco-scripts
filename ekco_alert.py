import os
import paho.mqtt.client as mqtt
import requests
import logging
import threading
import time

# Configuration
MQTT_BROKER = "35.232.45.67"
MQTT_PORT = 1883
MQTT_TOPIC = "alert"
MQTT_USERNAME = "KTS_EKCO"
MQTT_PASSWORD = "Ekco@prado123!"
CLOUD_FUNCTION_URL = "https://us-central1-ksdiv-3ba17.cloudfunctions.net/api"

# --- Logging Configuration ---
# Set up basic logging to console (StreamHandler)
# You can uncomment the FileHandler line to also save logs to a file.
logging.basicConfig(
    level=logging.INFO, # Set the minimum logging level (e.g., INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
# --- End Logging Configuration ---

# Callback function when a message is received
def on_message(client, userdata, msg):
    try:
        # Decode the message from bytes to string
        message = msg.payload.decode("utf-8")
        logging.info(f"Received MQTT message: Topic='{msg.topic}', Payload='{message}'")

        # Split the message into serial_number and content.
        # Use split(, 1) to ensure only the first comma acts as a separator,
        # allowing the message content itself to contain commas.
        try:
            serial_number, msg_content = message.split(",", 1)
        except ValueError:
            logging.warning(f"MQTT message format error: Expected 'serial_number,message_content', got '{message}'. Skipping processing.")
            return # Exit the function if format is incorrect

        # Prepare the data to be sent to the cloud function
        data = {"data": f"{serial_number}, {msg_content}"}
        logging.debug(f"Prepared data for Cloud Function: {data}") # Use debug for detailed data

        # Send a POST request to the cloud function
        response = requests.post(CLOUD_FUNCTION_URL, json=data)

        # Handle response
        if response.status_code == 200:
            logging.info(f"Successfully sent data for serial '{serial_number}' to Cloud Function. Response: {response.text}")
        else:
            logging.error(f"Failed to send data for serial '{serial_number}' to Cloud Function. Status Code: {response.status_code}, Response: {response.text}")

    except requests.exceptions.RequestException as e:
        # Catch network-related errors during the POST request
        logging.error(f"Network error sending to Cloud Function: {e}")
    except Exception as e:
        # Catch any other unexpected exceptions and log the full traceback
        logging.error(f"An unexpected error occurred in on_message: {e}", exc_info=True)

# Callback function when the client connects to the MQTT broker
# The 'properties' argument is required for CallbackAPIVersion.VERSION2
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        logging.info("Connected to MQTT Broker successfully!")
        client.subscribe(MQTT_TOPIC)
        logging.info(f"Subscribed to topic: '{MQTT_TOPIC}'")
    else:
        logging.error(f"Failed to connect to MQTT Broker, return code: {rc}. Please check connection details and broker status.")

# Create an MQTT client instance, specifying Callback API Version 2
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Set username and password for MQTT broker authentication
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Assign callback functions
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to the MQTT broker
try:
    logging.info(f"Attempting to connect to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}...")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60) # 60 seconds keepalive
except Exception as e:
    logging.critical(f"Could not connect to MQTT Broker: {e}. Exiting script.")
    exit(1) # Exit the script if connection cannot be established

# Start the MQTT client loop to process network traffic and dispatch callbacks
# --- Heartbeat for external watchdog ---
HEARTBEAT_PATH = "/app/heartbeats/ekco_alert.timestamp"

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
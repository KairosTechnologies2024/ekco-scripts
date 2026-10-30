import os
import paho.mqtt.client as mqtt
import requests
import threading
import time

# Configuration
MQTT_BROKER = "35.232.45.67"
MQTT_PORT = 1883
MQTT_TOPIC = "deviceUpdateStatus"
MQTT_USERNAME = "KTS_EKCO"  
MQTT_PASSWORD = "Ekco@prado123!"  
CLOUD_FUNCTION_URL = "https://us-central1-ksdiv-3ba17.cloudfunctions.net/deviceData"

# Callback function when a message is received
def on_message(client, userdata, msg):
    try:
        # Decode the message from bytes to string and split by commas
        message = msg.payload.decode("utf-8")
        serial_number, door_status, ignition_status, fuel_cut, gps_status, battery_voltage = message.split(",")

        # Prepare the data to be sent to the cloud function
        data = {"data": f"{serial_number},{door_status},{ignition_status},{fuel_cut},{gps_status},{battery_voltage}"}

        # Send a POST request to the cloud function
        response = requests.post(CLOUD_FUNCTION_URL, json=data)

        # Handle response (without printing)
        if response.status_code != 200:
            pass  # Handle non-200 responses if necessary
    except Exception:
        pass  # Silently ignore or handle exceptions as needed

# Callback function when the client connects to the MQTT broker
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(" [*] Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f" [x] Failed to connect, return code {rc}")

# Create an MQTT client instance
mqtt_client = mqtt.Client()

# Set username and password
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

# Assign callback functions
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to the MQTT broker
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start the MQTT client loop to process network traffic and dispatch callbacks
# --- Heartbeat for external watchdog ---
HEARTBEAT_PATH = "/app/heartbeats/ekco_device_data.timestamp"

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

print(" [*] Waiting for messages. To exit press CTRL+C")
mqtt_client.loop_forever()

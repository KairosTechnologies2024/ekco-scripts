FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all scripts
COPY *.py .

# Default command: show usage if no script is specified
CMD ["python", "-c", "print('Usage: docker run <image> python <script_name>.py')\nprint('Available scripts: ekco_alert.py, ekco_device_data.py, ekco_device_health.py, ekco_device_message.py, ekco_engine.py, ekco_gps.py, ekco_speed.py')"]
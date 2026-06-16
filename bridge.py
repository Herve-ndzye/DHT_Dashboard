"""
bridge.py — Serial ↔ MQTT bridge for Arduino DHT11 project

Reads JSON from Arduino via USB Serial, publishes to your VPS MQTT broker.

Requirements:
    pip install pyserial paho-mqtt

Usage:
    python bridge.py

Edit the CONFIG section below before running.
"""

import serial
import serial.tools.list_ports
import json
import time
import sys
import logging
import paho.mqtt.client as mqtt

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║                        CONFIG                               ║
# ╚══════════════════════════════════════════════════════════════╝

SERIAL_PORT   = "COM12"   # Windows: "COM3" | Linux/Pi: "/dev/ttyUSB0"
BAUD_RATE     = 9600

MQTT_BROKER   = "broker.benax.rw"    # ← replace with your VPS IP or domain
MQTT_PORT     = 1883             # standard MQTT port (TCP)
MQTT_USER     = ""               # leave empty if no auth on your broker
MQTT_PASS     = ""
CLIENT_ID     = "Herve"

TOPIC_SENSOR  = "sensors/herve/dht"
TOPIC_STATUS  = "iot/status/herve/arduino_001"

RECONNECT_DELAY = 5              # seconds between reconnect attempts


# ╔══════════════════════════════════════════════════════════════╗
# ║                     MQTT CALLBACKS                          ║
# ╚══════════════════════════════════════════════════════════════╝

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info("✅ MQTT connected to %s:%s", MQTT_BROKER, MQTT_PORT)
        client.publish(TOPIC_STATUS, "online", retain=True, qos=1)
        send_to_arduino("MQTT_OK")
    else:
        log.error("❌ MQTT connect failed, rc=%s", rc)
        send_to_arduino("MQTT_ERR")


def on_disconnect(client, userdata, rc):
    log.warning("⚠️  MQTT disconnected (rc=%s). Reconnecting...", rc)
    send_to_arduino("MQTT_ERR")


# ╔══════════════════════════════════════════════════════════════╗
# ║                     SERIAL HELPERS                          ║
# ╚══════════════════════════════════════════════════════════════╝

ser = None

def open_serial():
    global ser
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            log.info("✅ Serial opened: %s @ %s baud", SERIAL_PORT, BAUD_RATE)
            return
        except serial.SerialException as e:
            log.error("❌ Cannot open serial %s: %s", SERIAL_PORT, e)
            log.info("   Available ports: %s",
                     [p.device for p in serial.tools.list_ports.comports()])
            log.info("   Retrying in %ss…", RECONNECT_DELAY)
            time.sleep(RECONNECT_DELAY)


def send_to_arduino(cmd: str):
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\n").encode())
        except serial.SerialException as e:
            log.error("Serial write error: %s", e)


# ╔══════════════════════════════════════════════════════════════╗
# ║                        MAIN LOOP                            ║
# ╚══════════════════════════════════════════════════════════════╝

def main():
    open_serial()

    client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.will_set(TOPIC_STATUS, "offline", retain=True, qos=1)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect

    client.reconnect_delay_set(min_delay=1, max_delay=30)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        log.error("Initial MQTT connect failed: %s", e)

    client.loop_start()

    log.info("🔄 Bridge running. Press Ctrl-C to stop.")
    log.info("   Serial:  %s", SERIAL_PORT)
    log.info("   Broker:  %s:%s", MQTT_BROKER, MQTT_PORT)

    while True:
        try:
            raw = ser.readline().decode("utf-8", errors="ignore").strip()

            if not raw or not raw.startswith("{"):
                continue

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Bad JSON: %s", raw)
                continue

            payload["timestamp"] = int(time.time())

            msg = json.dumps(payload)
            result = client.publish(TOPIC_SENSOR, msg, retain=True, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                log.info("📤 Published → %s: %s", TOPIC_SENSOR, msg)
            else:
                log.warning("Publish failed rc=%s", result.rc)

        except serial.SerialException as e:
            log.error("Serial read error: %s — reopening port…", e)
            send_to_arduino("MQTT_ERR")
            time.sleep(RECONNECT_DELAY)
            open_serial()

        except KeyboardInterrupt:
            log.info("Shutting down…")
            client.publish(TOPIC_STATUS, "offline", retain=True)
            client.loop_stop()
            client.disconnect()
            if ser:
                ser.close()
            sys.exit(0)


if __name__ == "__main__":
    main()

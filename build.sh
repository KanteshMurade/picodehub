#!/usr/bin/env bash
# Render build script for PiCodeHub.
#
# Render runs this during the build step and keeps whatever it produces in
# the deployed instance's filesystem, so installing arduino-cli here (into
# a project-local ./bin folder, not a system path) means it's still there
# when gunicorn starts serving requests — no PATH guesswork required.
#
# IMPORTANT: arduino-cli's installed cores/libraries live in a "data
# directory" that defaults to $HOME/.arduino15. Render's $HOME is not
# guaranteed to be identical between the build step and the running web
# process, so if we let arduino-cli use its default location, everything
# installed here during the build can be INVISIBLE at request time (the
# app then re-downloads indexes and fails with "platform not installed").
# To avoid that entirely, we pin arduino-cli to a fixed, project-local
# data directory (./arduino-data) for both the build and — via the same
# env vars set in app.py's _cli() — every runtime call too.
#
# Render dashboard settings:
#   Build command: bash build.sh
#   Start command: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 2

set -e

echo "== Installing Python dependencies =="
pip install -r requirements.txt

echo "== Installing arduino-cli into ./bin =="
mkdir -p bin
curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR="$(pwd)/bin" sh
chmod +x bin/arduino-cli

export ARDUINO_CLI_PATH="$(pwd)/bin/arduino-cli"
echo "arduino-cli installed at: $ARDUINO_CLI_PATH"

# Fixed, project-local data/download/user directories — same paths app.py
# will point arduino-cli at when compiling, so build-time installs are
# always visible at request time regardless of Render's $HOME behavior.
mkdir -p arduino-data arduino-downloads arduino-user
export ARDUINO_DIRECTORIES_DATA="$(pwd)/arduino-data"
export ARDUINO_DIRECTORIES_DOWNLOADS="$(pwd)/arduino-downloads"
export ARDUINO_DIRECTORIES_USER="$(pwd)/arduino-user"

"$ARDUINO_CLI_PATH" version

echo "== Updating board index =="
"$ARDUINO_CLI_PATH" core update-index

echo "== Installing board cores used by the catalog =="
# These match the board types your seeded catalog projects target.
# Add more here later if you add projects for other board families.
"$ARDUINO_CLI_PATH" core install arduino:avr
"$ARDUINO_CLI_PATH" core install esp32:esp32
"$ARDUINO_CLI_PATH" core install esp8266:esp8266 --additional-urls https://arduino.esp8266.com/stable/package_esp8266com_index.json
"$ARDUINO_CLI_PATH" core install rp2040:rp2040 --additional-urls https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json

echo "== Installing third-party libraries used by the catalog =="
# These match the #include lines found across the seeded catalog projects.
# If you add a new catalog project that needs a library not listed here,
# add its Library Manager name to this list and redeploy.
"$ARDUINO_CLI_PATH" lib install "DHT sensor library"
"$ARDUINO_CLI_PATH" lib install "Adafruit GFX Library"
"$ARDUINO_CLI_PATH" lib install "Adafruit SSD1306"
"$ARDUINO_CLI_PATH" lib install "SparkFun MAX3010x Pulse and Proximity Sensor Library"
"$ARDUINO_CLI_PATH" lib install "ESP32Servo"

echo "== Verifying what's actually installed in the pinned data dir =="
"$ARDUINO_CLI_PATH" core list
"$ARDUINO_CLI_PATH" lib list

echo "== Build complete =="

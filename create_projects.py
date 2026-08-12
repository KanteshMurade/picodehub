import os
import json

PROJECTS = [
    {
        "id": "Smart_Door_System",
        "title": "Smart Door System",
        "category": "Security",
        "chipCategory": "Arduino",
        "difficulty": "Intermediate",
        "chips": ["ESP32", "Arduino Uno"],
        "chipTag": "Arduino Uno",
        "rating": "4.8",
        "views": "12.4K",
        "cover": "/static/images/smart_door.jpg",
        "description": "RFID-activated smart door lock mechanism featuring RC522 RFID reader, SG90 servo motor, relay strike lock, and piezoceramic buzzer feedback.",
        "wiring": [
            {"from": "ESP32 GPIO18", "to": "Servo Control (PWM Signal)", "color": "#f6ad55", "notes": "PWM Pulse stream"},
            {"from": "ESP32 GPIO5", "to": "RC522 RFID SDA / SS", "color": "#4299e1", "notes": "SPI Chip Select"},
            {"from": "ESP32 GPIO19", "to": "RC522 RFID MISO", "color": "#ed64a6", "notes": "SPI Master In"},
            {"from": "ESP32 GPIO23", "to": "RC522 RFID MOSI", "color": "#9f7aea", "notes": "SPI Master Out"},
            {"from": "ESP32 GPIO21", "to": "Active Buzzer (+)", "color": "#00ff88", "notes": "Audio Feedback"},
            {"from": "ESP32 GND", "to": "Common GND Rail", "color": "#4a5568", "notes": "Tie all grounds together"}
        ],
        "components": [
            {"name": "ESP32 NodeMCU Board", "quantity": 1, "specs": "CP2102 USB Bridge"},
            {"name": "RC522 RFID Module", "quantity": 1, "specs": "13.56 MHz Reader"},
            {"name": "SG90 Micro Servo", "quantity": 1, "specs": "9g 180° rotation"}
        ],
        "serialPlayback": [
            "[SYSTEM] Smart Door Lock armed.",
            "[EVENT] RFID Tag Detected: 84:A2:39:FF",
            "[SECURITY] Access Granted! Unlocking Servo..."
        ]
    },
    {
        "id": "ECG_Monitor_AD8232",
        "title": "ECG Monitor (AD8232)",
        "category": "Health",
        "chipCategory": "ESP32",
        "difficulty": "Advanced",
        "chips": ["ESP32"],
        "chipTag": "ESP32",
        "rating": "4.9",
        "views": "8.7K",
        "cover": "/static/images/ecg_monitor.jpg",
        "description": "Real-time electrocardiogram pulse wave visualization monitor using AD8232 heart sensor and ESP32 with OLED graphical plotting.",
        "wiring": [
            {"from": "ESP32 3.3V", "to": "AD8232 3.3V", "color": "#ff4d4d", "notes": "3.3V power"},
            {"from": "ESP32 GND", "to": "AD8232 GND", "color": "#4a5568", "notes": "Ground wire"},
            {"from": "ESP32 GPIO36 (VP)", "to": "AD8232 OUTPUT", "color": "#00ff88", "notes": "Analog signal line"}
        ],
        "components": [
            {"name": "ESP32 Microcontroller", "quantity": 1, "specs": "Dual core 240MHz"},
            {"name": "AD8232 ECG Sensor", "quantity": 1, "specs": "Single-lead heart rate monitor"},
            {"name": "Biomedical Electrode Pads", "quantity": 3, "specs": "Disposable sticky pads"}
        ],
        "serialPlayback": [
            "[SYSTEM] AD8232 ECG Monitor Initialized.",
            "BPM=72 | ECG Waveform Signal Clean",
            "BPM=74 | Peak R-R interval 810ms"
        ]
    },
    {
        "id": "Air_Quality_Monitor",
        "title": "Air Quality Monitor",
        "category": "Sensors",
        "chipCategory": "ESP32",
        "difficulty": "Intermediate",
        "chips": ["ESP32"],
        "chipTag": "ESP32",
        "rating": "4.7",
        "views": "6.7K",
        "cover": "/static/images/air_quality.jpg",
        "description": "Environmental telemetry measuring AQI, PM2.5, CO2 concentrations, and ambient temperature with color OLED status alerts.",
        "wiring": [
            {"from": "ESP32 GPIO21 (SDA)", "to": "OLED & MQ-135 SDA", "color": "#4299e1", "notes": "I2C Data"},
            {"from": "ESP32 GPIO22 (SCL)", "to": "OLED & MQ-135 SCL", "color": "#ecc94b", "notes": "I2C Clock"}
        ],
        "components": [
            {"name": "MQ-135 Air Quality Sensor", "quantity": 1, "specs": "Hazardous gas detector"},
            {"name": "ESP32 DevKit V1", "quantity": 1, "specs": "WiFi enabled"}
        ],
        "serialPlayback": [
            "[AQI] Index: 42 (GOOD)",
            "[AQI] CO2: 412 ppm | PM2.5: 12 ug/m3"
        ]
    },
    {
        "id": "Smart_Street_Light",
        "title": "Smart Street Light",
        "category": "Automation",
        "chipCategory": "Raspberry Pi",
        "difficulty": "Beginner",
        "chips": ["Raspberry Pi"],
        "chipTag": "Raspberry Pi",
        "rating": "4.8",
        "views": "9.3K",
        "cover": "/static/images/smart_door.jpg",
        "description": "Energy-efficient municipal light controller using LDR light sensors and PIR motion detection to dynamically dim and brighten street lamps.",
        "wiring": [
            {"from": "RPi GPIO17", "to": "PIR Motion Sensor OUT", "color": "#00ff88", "notes": "Digital Input"},
            {"from": "RPi GPIO18", "to": "LED Driver PWM", "color": "#f6ad55", "notes": "PWM Dimmer"}
        ],
        "components": [
            {"name": "Raspberry Pi 4", "quantity": 1, "specs": "Linux host"},
            {"name": "HC-SR501 PIR Sensor", "quantity": 1, "specs": "Motion detector"}
        ],
        "serialPlayback": [
            "[LIGHT] Night detected. Dimming to 20%.",
            "[MOTION] Vehicle detected! Brightening to 100%."
        ]
    },
    {
        "id": "Human_Counter",
        "title": "Human Counter",
        "category": "AI",
        "chipCategory": "Arduino",
        "difficulty": "Intermediate",
        "chips": ["Arduino Uno"],
        "chipTag": "Arduino Uno",
        "rating": "4.6",
        "views": "7.2K",
        "cover": "/static/images/air_quality.jpg",
        "description": "Bidirectional room occupancy detector with dual ultrasonic sensors, displaying real-time live human count on 7-segment display.",
        "wiring": [
            {"from": "Arduino Pin 2 (Trig1)", "to": "Ultrasonic 1 Trig", "color": "#00ff88", "notes": "Sensor 1 Entry"},
            {"from": "Arduino Pin 3 (Echo1)", "to": "Ultrasonic 1 Echo", "color": "#4299e1", "notes": "Sensor 1 Echo"}
        ],
        "components": [
            {"name": "HC-SR04 Ultrasonic Sensors", "quantity": 2, "specs": "Distance sensor"},
            {"name": "TM1637 4-Digit Display", "quantity": 1, "specs": "7-Segment Display"}
        ],
        "serialPlayback": [
            "[ENTRY] Person entered room. Count = 23",
            "[EXIT] Person left room. Count = 22"
        ]
    },
    {
        "id": "Soil_Moisture_Alarm",
        "title": "Soil Moisture Alarm",
        "category": "Sensors",
        "chipCategory": "Arduino",
        "difficulty": "Beginner",
        "chips": ["Arduino Uno"],
        "chipTag": "Arduino Uno",
        "rating": "4.6",
        "views": "5.8K",
        "cover": "/static/images/smart_door.jpg",
        "description": "Smart plant hydration monitor that triggers an audible alarm and automatic water pump when soil moisture falls below threshold.",
        "wiring": [
            {"from": "Arduino A0", "to": "Moisture Sensor Analog OUT", "color": "#00ff88", "notes": "Moisture level"},
            {"from": "Arduino Pin 8", "to": "Relay Module (Water Pump)", "color": "#ff4d4d", "notes": "5V Water Pump"}
        ],
        "components": [
            {"name": "Capacitive Soil Moisture Sensor", "quantity": 1, "specs": "Corrosion resistant"},
            {"name": "5V Submersible Pump", "quantity": 1, "specs": "Mini DC water pump"}
        ],
        "serialPlayback": [
            "[SOIL] Moisture level: 28% (DRY!)",
            "[PUMP] Activating irrigation pump for 5s..."
        ]
    },
    {
        "id": "Speed_Card_Reader",
        "title": "Speed Card Reader",
        "category": "Security",
        "chipCategory": "ESP32",
        "difficulty": "Advanced",
        "chips": ["ESP32-CAM"],
        "chipTag": "ESP32-CAM",
        "rating": "4.9",
        "views": "1.2K",
        "cover": "/static/images/ecg_monitor.jpg",
        "description": "Optical speed scanner reading ID badges and access keys at high speeds using ESP32-CAM camera module and onboard flash LED.",
        "wiring": [
            {"from": "ESP32-CAM U0T", "to": "FTDI RX", "color": "#4299e1", "notes": "Serial Tx"},
            {"from": "ESP32-CAM U0R", "to": "FTDI TX", "color": "#ecc94b", "notes": "Serial Rx"}
        ],
        "components": [
            {"name": "ESP32-CAM Module", "quantity": 1, "specs": "OV2640 Camera"},
            {"name": "FTDI Adapter", "quantity": 1, "specs": "USB to Serial programmer"}
        ],
        "serialPlayback": [
            "[CAM] Frame captured 1600x1200.",
            "[OCR] Barcode scanned: USER_99214_GRANTED"
        ]
    },
    {
        "id": "Pico_Macro_Keyboard",
        "title": "Pico Macro Keyboard",
        "category": "Other",
        "chipCategory": "Pico",
        "difficulty": "Intermediate",
        "chips": ["Raspberry Pi Pico"],
        "chipTag": "Raspberry Pi Pico",
        "rating": "4.8",
        "views": "5.5K",
        "cover": "/static/images/smart_door.jpg",
        "description": "Custom 12-key Mechanical Numpad macro pad with RGB backlighting, custom shortcut keys, and rotary encoder volume knob.",
        "wiring": [
            {"from": "Pico GP0 .. GP11", "to": "Key Switches (Matrix)", "color": "#00ff88", "notes": "Key Matrix Pins"},
            {"from": "Pico GP16", "to": "WS2812B RGB Data", "color": "#a855f7", "notes": "Neopixel LED Strip"}
        ],
        "components": [
            {"name": "Raspberry Pi Pico", "quantity": 1, "specs": "RP2040 Microcontroller"},
            {"name": "Gateron Mechanical Switches", "quantity": 12, "specs": "Linear Red Switches"}
        ],
        "serialPlayback": [
            "[HID] Keypress: MACRO_1 (Open VS Code)",
            "[HID] Rotary Knob: Volume Up +2%"
        ]
    },
    {
        "id": "IoT_Dashboard",
        "title": "IoT Dashboard",
        "category": "IoT",
        "chipCategory": "ESP32",
        "difficulty": "Advanced",
        "chips": ["ESP32"],
        "chipTag": "ESP32",
        "rating": "4.5",
        "views": "5.1K",
        "cover": "/static/images/air_quality.jpg",
        "description": "Central MQTT home automation hub managing web sockets, relay switches, current sensors, and live telemetry web charts.",
        "wiring": [
            {"from": "ESP32 GPIO4", "to": "Relay Bank Control", "color": "#ff4d4d", "notes": "Home AC Power Switches"}
        ],
        "components": [
            {"name": "ESP32 NodeMCU", "quantity": 1, "specs": "WiFi 802.11 b/g/n"},
            {"name": "4-Channel Relay Module", "quantity": 1, "specs": "Optocoupler isolated"}
        ],
        "serialPlayback": [
            "[MQTT] Connected to broker (test.mosquitto.org)",
            "[STATUS] Living Room Light: ON | Temperature: 24.2°C"
        ]
    },
    {
        "id": "OLED_Desk_Buddy",
        "title": "OLED Desk Buddy",
        "category": "Other",
        "chipCategory": "Arduino",
        "difficulty": "Beginner",
        "chips": ["Arduino Uno"],
        "chipTag": "Arduino Uno",
        "rating": "4.7",
        "views": "6.0K",
        "cover": "/static/images/smart_door.jpg",
        "description": "Interactive desktop companion with animated pixel faces, Pomodoro study timer, and crypto price tracker.",
        "wiring": [
            {"from": "Arduino A4 (SDA)", "to": "OLED SDA", "color": "#4299e1", "notes": "I2C Data"},
            {"from": "Arduino A5 (SCL)", "to": "OLED SCL", "color": "#ecc94b", "notes": "I2C Clock"}
        ],
        "components": [
            {"name": "Arduino Uno R3", "quantity": 1, "specs": "ATmega328P"},
            {"name": "0.96 inch SSD1306 OLED", "quantity": 1, "specs": "128x64 display"}
        ],
        "serialPlayback": [
            "[BUDDY] Eye animation frame 4/12",
            "[TIMER] Pomodoro Session 1: 25 minutes left"
        ]
    }
]

base_dir = r"c:\Users\Administrator\Desktop\PICODEHUB\projects"

for p in PROJECTS:
    folder = os.path.join(base_dir, p["id"])
    os.makedirs(folder, exist_ok=True)
    
    # Save project.json
    json_path = os.path.join(folder, "project.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2)
        
    # Save sketch file
    ino_path = os.path.join(folder, f"{p['id']}.ino")
    if not os.path.exists(ino_path):
        with open(ino_path, "w", encoding="utf-8") as f:
            f.write(f"/*\n  {p['title']} - Technosankalp Solutions\n  Category: {p['category']} | Chip: {p['chipTag']}\n*/\n\nvoid setup() {{\n  Serial.begin(115200);\n  Serial.println(\"[SYSTEM] {p['title']} Initialized.\");\n}}\n\nvoid loop() {{\n  // Main loop logic\n  delay(1000);\n}}\n")

print("Created 10 projects successfully.")

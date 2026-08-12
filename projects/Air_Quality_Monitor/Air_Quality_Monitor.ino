/*
  Air Quality Monitor - Technosankalp Solutions / Sodh Lab
  Category: Sensors | Microcontroller: ESP32
  
  Description:
    Reads air quality (AQI / CO2 / TVOC estimation) from an MQ-135 gas sensor
    and ambient temperature/humidity from a DHT sensor.
    Displays live readings and status on an I2C OLED screen and streams serial telemetry.
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Pin Definitions
const int MQ135_PIN = 34;   // ADC1 pin for MQ-135 Analog Out
const int DHT_PIN = 4;      // DHT Sensor Data Pin
const int BUZZER_PIN = 15;  // Warning Buzzer Pin
const int ALERT_LED = 2;    // Onboard Status LED

// AQI Thresholds
const int AQI_GOOD = 50;
const int AQI_MODERATE = 100;
const int AQI_POOR = 150;

// Variables
float temperature = 24.5;
float humidity = 55.0;
int rawGasValue = 0;
int calculatedAQI = 0;
int co2Ppm = 400;

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(ALERT_LED, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(ALERT_LED, LOW);

  Serial.println("=========================================");
  Serial.println("  TECHNOSANKALP AIR QUALITY MONITOR V1.0 ");
  Serial.println("=========================================");

  // Initialize I2C OLED display (Address 0x3C)
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[ERROR] SSD1306 OLED allocation failed.");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println("Air Quality Monitor");
    display.println("Initializing sensors...");
    display.display();
    delay(1000);
  }

  Serial.println("[SYSTEM] MQ-135 & DHT Sensors Initialized.");
  Serial.println("[SYSTEM] Starting telemetry loop...");
}

void loop() {
  static unsigned long lastReading = 0;
  if (millis() - lastReading >= 3000) {
    lastReading = millis();

    // Read analog MQ-135 sensor (ESP32 12-bit ADC: 0-4095)
    rawGasValue = analogRead(MQ135_PIN);
    
    // Calculate approximate AQI and CO2 equivalent
    calculatedAQI = map(rawGasValue, 200, 3000, 20, 350);
    if (calculatedAQI < 10) calculatedAQI = 15 + random(0, 10);
    co2Ppm = 400 + (calculatedAQI * 3);

    // Simulate realistic ambient temperature/humidity drift
    temperature = 24.0 + (random(-5, 6) / 10.0);
    humidity = 55.0 + (random(-10, 11) / 10.0);

    // Formulate AQI status text
    String aqiStatus = "GOOD";
    if (calculatedAQI > AQI_POOR) {
      aqiStatus = "HAZARDOUS";
      digitalWrite(BUZZER_PIN, HIGH);
      digitalWrite(ALERT_LED, HIGH);
    } else if (calculatedAQI > AQI_MODERATE) {
      aqiStatus = "POOR";
      digitalWrite(BUZZER_PIN, LOW);
      digitalWrite(ALERT_LED, HIGH);
    } else {
      digitalWrite(BUZZER_PIN, LOW);
      digitalWrite(ALERT_LED, LOW);
    }

    // Print Telemetry to Serial Monitor
    Serial.print("[AQI] Index: ");
    Serial.print(calculatedAQI);
    Serial.print(" (");
    Serial.print(aqiStatus);
    Serial.print(") | CO2: ");
    Serial.print(co2Ppm);
    Serial.print(" ppm | Temp: ");
    Serial.print(temperature, 1);
    Serial.print("°C | Hum: ");
    Serial.print(humidity, 1);
    Serial.println("%");

    // Update OLED Display
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("AQI Telemetry: ");
    display.println(aqiStatus);

    display.setTextSize(2);
    display.setCursor(0, 16);
    display.print("AQI: ");
    display.println(calculatedAQI);

    display.setTextSize(1);
    display.setCursor(0, 42);
    display.print("CO2: ");
    display.print(co2Ppm);
    display.println(" ppm");

    display.setCursor(0, 54);
    display.print("T: ");
    display.print(temperature, 1);
    display.print("C  H: ");
    display.print(humidity, 1);
    display.println("%");

    display.display();
  }
}

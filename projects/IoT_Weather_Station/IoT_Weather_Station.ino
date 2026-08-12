/*
  IoT Weather Station - Technosankalp Solutions
  Reads DHT22 temperature/humidity sensor & BMP280 atmospheric pressure, 
  displays readings on I2C OLED display, and transmits data.
*/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>

#define DHTPIN 4
#define DHTTYPE DHT22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

DHT dht(DHTPIN, DHTTYPE);
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

void setup() {
  Serial.begin(115200);
  dht.begin();
  
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("[ERROR] SSD1306 OLED allocation failed"));
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println("Technosankalp Weather");
    display.println("Initializing sensors...");
    display.display();
  }
  
  Serial.println("[SYSTEM] IoT Weather Station Bootstrapped.");
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  Serial.print("[SENSOR] Humidity: ");
  Serial.print(h);
  Serial.print("%  | Temperature: ");
  Serial.print(t);
  Serial.println("°C");

  delay(2500);
}

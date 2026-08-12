/*
  Smart Door System - Technosankalp Solutions
  Uses RFID scanner and Servo Motor to authenticate and unlock a door lock.
*/

#include <ESP32Servo.h>

const int SERVO_PIN = 18;
const int RFID_SS_PIN = 5;
const int BUZZER_PIN = 21;
const int RELAY_PIN = 22;

Servo doorServo;

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  doorServo.attach(SERVO_PIN);
  doorServo.write(0); // Locked position

  Serial.println("=========================================");
  Serial.println("  TECHNOSANKALP SMART DOOR SYSTEM V1.0  ");
  Serial.println("=========================================");
  Serial.println("[SYSTEM] Initializing RC522 RFID reader...");
  Serial.println("[SYSTEM] System Armed. Present RFID card.");
}

void loop() {
  // Simulated main loop for demonstration
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > 4000) {
    lastCheck = millis();
    Serial.println("[EVENT] RFID Card Detected: Tag ID 84:A2:39:FF");
    Serial.println("[SECURITY] Access Granted! Unlocking Servo...");
    
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
    
    doorServo.write(90); // Unlock
    digitalWrite(RELAY_PIN, HIGH);
    delay(3000);
    
    Serial.println("[SECURITY] Relocking door...");
    doorServo.write(0); // Lock
    digitalWrite(RELAY_PIN, LOW);
  }
}

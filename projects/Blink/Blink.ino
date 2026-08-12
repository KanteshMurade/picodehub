/*
  Blink - Technosankalp Solutions Sample
  Turns an LED on for one second, then off for one second, repeatedly.
*/

const int LED_PIN = 13;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  Serial.println("[SYSTEM] Blink test initialized on Pin 13.");
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  Serial.println("STATUS: LED ON");
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  Serial.println("STATUS: LED OFF");
  delay(1000);
}

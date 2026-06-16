/*
 * arduino_dht_lcd.ino
 *
 * Reads DHT11 temperature → displays on 16x2 I2C LCD
 * Sends JSON via Serial USB → Python bridge picks it up → MQTT on VPS
 *
 * WIRING:
 *  DHT11  → DATA: Pin 2 | VCC: 5V | GND: GND
 *  LCD I2C → SDA: A4   | SCL: A5 | VCC: 5V | GND: GND
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ── Pin config ──────────────────────────────────────────────
#define DHTPIN  2
#define DHTTYPE DHT11

// ── LCD ─────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);
DHT dht(DHTPIN, DHTTYPE);

// ── Display Name (scrolls if longer than 16 chars) ─────────
const String displayName = "Ndizeye Herve";

unsigned long lastScrollTime = 0;
const unsigned long SCROLL_INTERVAL = 300; // ms
int scrollPos = 0;

// ── Timing ──────────────────────────────────────────────────
unsigned long lastSensorRead = 0;
const unsigned long READ_INTERVAL = 5000;   // 5 seconds

// ── Custom LCD degree symbol ────────────────────────────────
byte degChar[8] = {
  0b00110,
  0b01001,
  0b01001,
  0b00110,
  0b00000,
  0b00000,
  0b00000,
  0b00000
};

// ────────────────────────────────────────────────────────────
// Updates first row with scrolling text if needed
void updateNameDisplay() {

  lcd.setCursor(0, 0);

  if (displayName.length() <= 16) {
    lcd.print(displayName);

    // Clear unused positions
    for (int i = displayName.length(); i < 16; i++) {
      lcd.print(" ");
    }
    return;
  }

  String scrollText = displayName + "    ";

  String visibleText =
      scrollText.substring(scrollPos) +
      scrollText.substring(0, scrollPos);

  lcd.print(visibleText.substring(0, 16));

  scrollPos++;

  if (scrollPos >= scrollText.length()) {
    scrollPos = 0;
  }
}

// ────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);

  lcd.init();
  lcd.backlight();
  lcd.createChar(0, degChar);

  dht.begin();

  updateNameDisplay();

  lcd.setCursor(0, 1);
  lcd.print("Starting...");

  delay(1500);

  lcd.clear();
}

// ────────────────────────────────────────────────────────────
void loop() {

  // Update scrolling name
  if (millis() - lastScrollTime >= SCROLL_INTERVAL) {
    lastScrollTime = millis();
    updateNameDisplay();
  }

  // Read sensor every 5 seconds
  unsigned long now = millis();

  if (now - lastSensorRead >= READ_INTERVAL) {
    lastSensorRead = now;
    readAndPublish();
  }
}

// ────────────────────────────────────────────────────────────
void readAndPublish() {

  float temp = dht.readTemperature();

  // Ignore failed readings
  if (isnan(temp)) {
    return;
  }

  // Row 2: Temperature only
  lcd.setCursor(0, 1);
  lcd.print("Temp:");
  lcd.print(temp, 1);
  lcd.write(0);     // degree symbol
  lcd.print("C     ");

  // Send JSON to Serial
  Serial.print("{\"temperature\":");
  Serial.print(temp, 1);
  Serial.println("}");
}
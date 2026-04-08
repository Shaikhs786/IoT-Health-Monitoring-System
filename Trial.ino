#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <DHT.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── WiFi Credentials ──────────────────────────────────────
const char* ssid       = "OPPO A59";
const char* password   = "sulueditz";

// ── Flask Server ───────────────────────────────────────────
const char* serverName = "http://10.196.205.60:5000/data";

// ── DHT11 Setup ────────────────────────────────────────────
#define DHTPIN  D4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// ── Pulse Sensor ───────────────────────────────────────────
#define PULSE_PIN A0

// ── OLED Setup (128x64, I2C: SDA=D2, SCL=D1) ──────────────
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET   -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ── Helper: show status on OLED ────────────────────────────
void showOLED(float temp, int bpm, bool connected, bool critical) {
  display.clearDisplay();

  // Header
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Smart Health Monitor");
  display.drawLine(0, 9, 127, 9, SSD1306_WHITE);

  // Temperature
  display.setCursor(0, 14);
  display.print("Temp : ");
  display.print(temp, 1);
  display.println(" C");

  // BPM
  display.setCursor(0, 26);
  display.print("BPM  : ");
  display.println(bpm);

  // Status
  display.setCursor(0, 38);
  display.print("Status: ");
  if (critical) {
    display.println("CRITICAL!");
  } else {
    display.println("NORMAL");
  }

  // WiFi
  display.setCursor(0, 50);
  display.print("WiFi: ");
  display.println(connected ? "Connected" : "Offline");

  display.display();
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  // OLED init
  Wire.begin(D2, D1); // SDA, SCL
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found!");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(20, 20);
    display.println("Connecting WiFi...");
    display.display();
  }

  // WiFi connect
  WiFi.begin(ssid, password);
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");

  // Show connected on OLED
  display.clearDisplay();
  display.setCursor(10, 20);
  display.println("WiFi Connected!");
  display.setCursor(10, 35);
  display.println(WiFi.localIP());
  display.display();
  delay(2000);
}

void loop() {
  float temp = dht.readTemperature();
  int   pulseValue = analogRead(PULSE_PIN);
  int   bpm = map(pulseValue, 0, 1023, 60, 100);

  // Validate DHT reading
  if (isnan(temp)) {
    Serial.println("DHT read failed!");
    temp = 0.0;
  }

  // Determine critical
  bool critical = (temp > 38.0 || bpm > 100 || bpm < 60);

  // Serial log
  Serial.print("Temp: "); Serial.print(temp);
  Serial.print(" C | BPM: "); Serial.print(bpm);
  Serial.println(critical ? " | CRITICAL" : " | NORMAL");

  bool wifiOK = (WiFi.status() == WL_CONNECTED);

  // Update OLED (works offline too)
  showOLED(temp, bpm, wifiOK, critical);

  // Send to Flask if WiFi available
  if (wifiOK) {
    WiFiClient client;
    HTTPClient http;

    String url = String(serverName) + "?temp=" + temp + "&bpm=" + bpm;
    http.begin(client, url);
    int httpCode = http.GET();

    Serial.print("Server Response: ");
    Serial.println(httpCode);
    http.end();
  } else {
    Serial.println("WiFi offline - showing on OLED only");
  }

  delay(5000);
}

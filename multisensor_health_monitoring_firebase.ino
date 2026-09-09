#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"
#include <WiFi.h>
#include <HTTPClient.h>

// ================= PIN DEFINITIONS =================

// MAX30102
#define SDA_PIN 21
#define SCL_PIN 22

// AD8232
#define ECG_PIN 35
#define LO_PLUS 32
#define LO_MINUS 33

// MQ AIR SENSOR
#define MQ_PIN 34


// ================= WIFI / FIREBASE =================

const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* FIREBASE_URL    = "https://YOUR_PROJECT-default-rtdb.firebaseio.com";
const char* FIREBASE_SECRET = "YOUR_DATABASE_SECRET";

const unsigned long PUSH_INTERVAL_MS = 300; // throttle network pushes
unsigned long lastPush = 0;


// ================= MAX30102 =================

MAX30105 sensor;

long irValue;
long redValue;

float bpm = 0;
int avgBPM = 0;

const byte RATE_SIZE = 4;
byte rates[RATE_SIZE];
byte rateSpot = 0;

unsigned long lastBeat = 0;


// ================= WIFI + FIREBASE HELPERS =================

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(400);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi connect timed out — will keep retrying in loop().");
  }
}

void pushToFirebase(int ecg, int lo_plus, int lo_minus, int mq,
                     long ir, long red, float bpmVal, int avgBpmVal) {
  String url = String(FIREBASE_URL) + "/vitalsync/latest.json?auth=" + FIREBASE_SECRET;

  String payload = "{";
  payload += "\"ecg\":" + String(ecg) + ",";
  payload += "\"lo_plus\":\"" + String(lo_plus) + "\",";
  payload += "\"lo_minus\":\"" + String(lo_minus) + "\",";
  payload += "\"mq\":" + String(mq) + ",";
  payload += "\"ir\":" + String(ir) + ",";
  payload += "\"red\":" + String(red) + ",";
  payload += "\"bpm\":" + String(bpmVal, 1) + ",";
  payload += "\"avg_bpm\":" + String(avgBpmVal) + ",";
  payload += "\"ts\":" + String(millis());
  payload += "}";

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.PUT(payload);
  if (code <= 0) {
    Serial.println("Firebase push failed: " + http.errorToString(code));
  }
  http.end();
}


// ================= SETUP =================

void setup() {

  Serial.begin(115200);
  delay(1500);

  Serial.println();
  Serial.println("======================================");
  Serial.println("      ESP32 MULTI SENSOR SYSTEM");
  Serial.println("======================================");
  Serial.println("MAX30102 + AD8232 + MQ SENSOR");
  Serial.println();

  // WiFi
  connectWiFi();

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // AD8232
  pinMode(LO_PLUS, INPUT);
  pinMode(LO_MINUS, INPUT);

  // MAX30102
  Serial.println("Initializing MAX30102...");

  if (!sensor.begin(Wire, I2C_SPEED_FAST)) {

    Serial.println("ERROR: MAX30102 NOT FOUND!");

    while (1) {
      delay(1000);
    }
  }

  Serial.println("MAX30102 FOUND!");

  sensor.setup();

  sensor.setPulseAmplitudeRed(0x1F);
  sensor.setPulseAmplitudeIR(0x1F);

  Serial.println("MAX30102 READY");

  // MQ
  Serial.println("MQ SENSOR READY");

  Serial.println();
  Serial.println("======================================");
  Serial.println("           SYSTEM READY");
  Serial.println("======================================");
  Serial.println();

  Serial.println("Place finger on MAX30102");
  Serial.println("Connect AD8232 electrodes");
  Serial.println();
}


// ================= LOOP =================

void loop() {

  // -------- WIFI WATCHDOG --------
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // -------- AD8232 --------

  int ecgValue = analogRead(ECG_PIN);

  int loPlus = digitalRead(LO_PLUS);
  int loMinus = digitalRead(LO_MINUS);


  // -------- MQ SENSOR --------

  int mqValue = analogRead(MQ_PIN);


  // -------- MAX30102 --------

  irValue = sensor.getIR();
  redValue = sensor.getRed();


  // -------- HEART RATE --------

  if (checkForBeat(irValue)) {

    unsigned long currentTime = millis();

    if (lastBeat != 0) {

      unsigned long delta = currentTime - lastBeat;

      bpm = 60.0 / (delta / 1000.0);

      if (bpm > 20 && bpm < 255) {

        rates[rateSpot] = (byte)bpm;

        rateSpot++;

        if (rateSpot >= RATE_SIZE) {
          rateSpot = 0;
        }

        avgBPM = 0;

        for (byte i = 0; i < RATE_SIZE; i++) {
          avgBPM += rates[i];
        }

        avgBPM = avgBPM / RATE_SIZE;
      }
    }

    lastBeat = currentTime;
  }


  // -------- SERIAL MONITOR --------

  Serial.print("ECG: ");
  Serial.print(ecgValue);

  Serial.print(" | LO+: ");
  Serial.print(loPlus);

  Serial.print(" | LO-: ");
  Serial.print(loMinus);

  Serial.print(" | MQ: ");
  Serial.print(mqValue);

  Serial.print(" | IR: ");
  Serial.print(irValue);

  Serial.print(" | RED: ");
  Serial.print(redValue);

  Serial.print(" | BPM: ");
  Serial.print(bpm, 1);

  Serial.print(" | AVG BPM: ");
  Serial.println(avgBPM);


  // -------- FIREBASE PUSH (throttled) --------

  unsigned long now = millis();
  if (now - lastPush >= PUSH_INTERVAL_MS && WiFi.status() == WL_CONNECTED) {
    lastPush = now;
    pushToFirebase(ecgValue, loPlus, loMinus, mqValue, irValue, redValue, bpm, avgBPM);
  }


  delay(20);
}
const int sensorPin = A2;  // Analog pin connected to the BP sensor
const int pumpPin = 7;     // Optional: Pin to trigger the BP monitor
//const int sampleRate = 10; // 10ms delay = 100Hz sample rate

void setup() {
  // Use a fast baud rate so the serial buffer doesn't overflow
  Serial.begin(115200); 
  pinMode(pumpPin, OUTPUT);
}

void loop() {
  // Read the raw ADC value (0-1023)
  int rawVoltage = analogRead(sensorPin);
  
  // Stream it instantly
  Serial.println(rawVoltage);
  
  // Maintain the strict 100Hz timing required for the SciPy filters
  delay(10); 
}
const int xPin = A0;  // Joystick X-axis connected to analog pin A0
const int yPin = A1;  // Joystick Y-axis connected to analog pin A1
const int buttonPin = 2; // Joystick button connected to digital pin 2

void setup() {
  Serial.begin(9600);  // Start serial communication
  pinMode(buttonPin, INPUT);  // Set button pin as input
}

void loop() {
  int xValue = analogRead(xPin);  // Read X-axis value (0-1023)
  int yValue = analogRead(yPin);  // Read Y-axis value (0-1023)
  int buttonState = digitalRead(buttonPin);  // Read button state

  // Send joystick values and button state to the serial monitor
  Serial.print(xValue);
  Serial.print(",");
  Serial.print(yValue);
  Serial.print(",");
  Serial.println(buttonState);

  delay(100);  // Delay to avoid overloading serial data
}

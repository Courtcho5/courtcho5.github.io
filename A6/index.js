//Baud rate of the arudino sketch
const BAUD_RATE = 9600; 

// Global variables
let port, connectBtn; 
// Set the inital position of the ball
let x = 0, y = 0 

// Set up function that will create the canvas and set up serial communication
function setup() {
// Sets up serial communication
  setupSerial();
// Makes canvas the size of the desktop
  createCanvas(windowWidth, windowHeight);
}
// Draw function that will 
function draw() {
// Check if the port is open
  const portIsOpen = checkPort(); 
// Close the draw loop if the port is closed
  if (!portIsOpen) return; 
// Read from the port until a new line is found, name it str
  let str = port.readUntil("\n"); 
// Close the readUntil function if nothing is read
  if (str.length == 0) return; 
// Split str into an array separated by commas
  let arr = str.trim().split(","); // Split the string by commas

// Map the first value of the array (X) to the windowWidth 
  x = map(Number(arr[0]), 0, 1023, 0, windowWidth);  
// Map the second value of the array (Y) to the windowHeight
  y = map(Number(arr[1]), 0, 1023, 0, windowHeight); 
// Map the third value of the array to the ball diameter
  diameter = map(Number(arr[2]), 0, 1023, 10, 40); 

// Set the background to a light grey
  background(220);
// Create a circle with the mapped X and Y coordinate with mapped diameter
  circle(x, y, diameter); 
}

// Creates a function where if the key is pressed, will write to arduino to execute command
function keyPressed() {
// 97 is the "a" key 
	port.write(97);
}


// Helper functions for managing the serial connection
function setupSerial() {
// Names create serial function as port
  port = createSerial();

// Check for previously used ports
  let usedPorts = usedSerialPorts();
// If there are more than 0 ports in use then open the first one
  if (usedPorts.length > 0) {
// Open the most recent port and insert baud rate
    port.open(usedPorts[0], BAUD_RATE);
  }

// Create a connect button that says "connect to Arduino"
  connectBtn = createButton("Connect to Arduino");
// Put the botton in the 5,5 position
  connectBtn.position(5, 5); 
// If clicked execute the onConntectButtonClicked function
  connectBtn.mouseClicked(onConnectButtonClicked); // Attach the click event handler
}

// If the port is not open then keep existing message
function checkPort() {
// If the port is opened function
  if (!port.opened()) {
// Keep the same message if not open
    connectBtn.html("Connect to Arduino");
// Grey background
    background("gray");
// Boolean return as false to keep the port as closed
    return false;
// Else statement if the port is open then swap to disconnect message
  } else {
// Disconnect statement
    connectBtn.html("Disconnect");
// Boolean return as true to keep port open
    return true;
  }
}

// Function to open and close the serial port when clicked
function onConnectButtonClicked() {
// If statement where if the port is not opened then open it 
  if (!port.opened()) {
// Give the open port the baud rate
    port.open(BAUD_RATE);  
// Else close the port
  } else {
    port.close();  // Close the port
  }
}

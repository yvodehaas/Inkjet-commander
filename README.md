# Inkjet-commander
The software to control and print with the HP45 controller

Inkjet commander is the a python software used to control the HP45 V4 controller (https://ytec3d.com/hp45-controller-v4/)
The most up to date manual as of right now can be found here: https://ytec3d.com/inkjet-commander-manual/

Functions:
- Set up a serial connection with the HP45 V4 controller
- Manage the buffer (to be printed lines)
- Control settings such as drops per inch, DPI and what side of the printhead to use
- Preheat and prime the printhead
- Test the printhead for broken nozzles
- Encoder mode movement (get position from a quadrature encoder)
- Virtual mode movement (Move at a constant, virtual speed, started by a trigger)
- Set the trigger pins and mode
- Open and convert bitmap images
- Send converted bitmap images to the printhead

Dependencies for the software:
-	Python 3.6.2 or higher (https://www.python.org/downloads/)
-	PyQT5 (https://pypi.org/project/PyQt5/)
  -	"pip install PyQt5"
-	Numpy (https://numpy.org/)
  -	"pip install Numpy"
-	Pyserial (https://pyserial.readthedocs.io/)
  - "pip install pyserial"

Dependencies for the HP45 controller
- Arduino IDE 1.8.12 or higher (https://www.arduino.cc/en/software)
- Teensyduino (https://www.pjrc.com/teensy/teensyduino.html)

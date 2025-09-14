# stowawayPicoUSB

**V1.0**

A company named Targus made ingenious foldable keyboards back in the days - this is a small project to send keystrokes from the Stowaway Handspring version to USB via a Raspi Pico.

![GIF of keyboard unfolding](./stowawayPicoUSB.gif "Stowaway keyboard unfolding")

## Hardware

- Raspberry Pi Pico (5€)
- 8-pin 2.54mm socket and pin-row connector
- SSD1306 display (8€)(optional)
- USB cable

Time to build it: less than half an hour.

## Software

- CircuitPython 9.x
- Adafruit HID library for USB connectivity
- [CircitPython libraries](https://circuitpython.org/libraries) - see below


## How to build it

#### Init Raspi Pico 

- Connect a virgin Raspi Pico to your computer - a **USB drive named RPI appears in the file system**
- Download and **copy the Circuit Python .uf2 file to the RPI-RP2 USB drive** - file and instructions here: [Adafruit Page](https://circuitpython.org/board/raspberry_pi_pico/) You may either use the 9.x or 10.x version of Circuit Python, just be sure to pick the matching libraries in the next step. The Pico reboots now and registers as a USB drive called CIRCUITPY now. 

#### Connect

![Schematic](./PicoWiring_Breadboard.png)
- Solder a connection to the pin-row connector
- Solder the pin-row socket to the Stowaway keyboard
- If you want the disply, solder the SDA and SCL connections and power wires

#### Install software

- Get the **Adafruit Library** bundle [(download page)](https://circuitpython.org/libraries)
- Find and copy these libraries to the ```/lib``` folder on the CIRCUITPY drive: 
	- ```adafruit_hid``` folder
	- ```adafruit_displayio_ssd1306```
	- ```adafruit_display_text```
	- ```asyncio```
	- ```adafruit_ticks``` (needed for asyncio)
- **Clone the project** to a local folder (or get the ```src/*.py``` files)
- Copy ```main.py``` and ```stow_kbd.py``` to CIRCUITPY root folder.

You may have to erase the ```code.py``` default script from the folder.

![display showing "Keycode 4 pressed"](./keys_display.png)

If you connect the Pico to USB now, the display powers up, and the keyboard listens to keystrokes. 

All the interpretation is handled by the computer the USB bus is plugged into. 

## The code

is a partly vibe-coded crude proof-of-concept to sho

### ```stow_kbd.py```

has the ```KeyboardReader``` class. Most important methods besides ```start()``` and ```stop()``` are: 

- ```read()``` - returns scancode buffer
- ```read_one()``` - reads one scancode byte from buffer, filtering the second byte from a "all keys up" message
- ```get()``` - reads scancode buffer, converts to keycode, and sends kbd.press() or kbd.release() message, returning scancode and keycode. 

### ```main.py```

- initialises the SSD1306 display, using the ```adafruit_displayio_ssd1306``` library [(docs)](https://docs.circuitpython.org/projects/displayio_ssd1306/en/latest/) which outputs nice status text on a 21x4 character window.
- Has a cprint() routine which outputs text to the terminal and to the display in parallel

*Note*: If you do not set a root group (by commenting out the ```display.root_group = splash``` line in ```setup_display```, you can use simple ```print()``` commands to show the status, as the REPL terminal is mirrored - but with a status line which you presumably can't get rid of. 

- has a wrapper for the ```KeyboardReader```, starting the routine and using ```KeyboardReader.get()``` to send keypresses to USB. The scancode and keycode are printed to the display. 

### Todo

Problems to fix: 

- Doesn't catch the auto-repetitions as suggested in the Stowaway documentation

Nice-to-have: 

- Timeout: if no key has been pressed for a while, power-cycle the keyboard

### Documentation

- [Raspberry Pi Pico Pinout](https://www.elektronik-kompendium.de/sites/raspberry-pi/2611051.htm)
- [Targus Stowaway Handspring Documentation (PDF)](./stowaway_handspring.pdf) (Note: as the company no longer exists, I consider this to be abandonware) 

### Working with VSC

- There's a VSC extension called ["CircuitPython V2" on the VSC marketplace](https://marketplace.visualstudio.com/items?itemName=wmerkens.vscode-circuitpython-v2). 
- Once the initialized Raspi Pico is connected, you have to set the board to "Raspberry Pi:Pico" in the selection on the lower right edge of the VSC window; then click on the connector symbol next to it and pick the correct USB interface for the Pico (it's ```/dev/tty.usbmodem2101``` on my Mac)
- Working with CP in VSC is a bit different from MicroPython. You don't upload your files from the project folder to your device to test them - **you work on the CIRCUITPY USB drive folder** as a project folder. Every time you change the files, the extension triggers a reload and starts the ```code.py```  or ```main.py``` script; if you need to go to the REPL interface, you can do so by interrupting the program or just pressing a key once it stops. 
- Look at the [Adafruit Tutorial for working with VSC](https://learn.adafruit.com/using-the-circuitpython-extension-for-visual-studio-code/use-the-circuitpython-extension-for-vs-code)

If you like an AI to help you coding, have a look at the [VOID project](https://voideditor.com) which is an AI-enabled fork of VSC but without the annoying Copilot. Use Mistral's ```codestral``` model (there's a special API key which gives you free usage) for autocompletion, it's fast and cheap and good. 

For agentic mode - i.e. "Write a routine doing this", or "Fix problems in code", working options are ```mistral-medium-3.1``` (fast and cheap) or ```claude-sonnet-4-0``` (good but not cheap). 

Local models under Ollama are another good option; I like ```qwen3-coder``` very much but tool use - and thus agentic mode - does not seem to work in Void with it right now.  

## License

As this project relies heavily on Adafruit's CircuitPython libraries, which are under a MIT license, this project is published under the **[MIT LICENSE](./LICENSE) (2025) untergeekDE** as well. 


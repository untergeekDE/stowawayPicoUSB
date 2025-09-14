# CircuitPython: Main program for Stowaway keyboard demo (non-async version)
# Hardware targets: e.g. RP2040 (Pico) + SSD1306 (I2C) + UART keyboard module
VERSION = "1.0"


import busio
import time
import stow_kbd
import asyncio
import board, displayio, terminalio, sys, i2cdisplaybus
from adafruit_display_text import label
from adafruit_displayio_ssd1306 import SSD1306

# --------------------------
# Pin configuration (adjust)
# --------------------------
i2c_scl_pin = board.GP21  
i2c_sda_pin = board.GP20  
uart_rxd_pin = board.GP17
uart_txd_pin = board.GP0   # Must be assigned, even if TX is unused
kbd_power_pin = board.GP16 # Powers the keyboard module (active-high)

# --------------------------
# Global state
# --------------------------
kbd_active = False
writer = None
display = None

original_stdout = sys.stdout



# --- Stdout mirroring ---
class OLEDWriter:
    def __init__(self, label_obj, max_lines=8, cols=21):
        self.label = label_obj
        self.max_lines = max_lines
        self.cols = cols
        self.lines = [""]

    def write(self, s):
        for ch in s:
            if ch == "\n":
                self.lines.append("")
            else:
                if len(self.lines[-1]) >= self.cols:
                    self.lines.append("")
                self.lines[-1] += ch
            if len(self.lines) > self.max_lines:
                self.lines = self.lines[-self.max_lines:]
        self.label.text = "\n".join(self.lines)
        return len(s)

    def flush(self):
        pass

class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, s):
        for st in self.streams:
            st.write(s)
        for st in self.streams:
            if hasattr(st, "flush"):
                st.flush()
        return len(s)
    def flush(self):
        for st in self.streams:
            if hasattr(st, "flush"):
                st.flush()


def cprint(*args, **kwargs):
    msg = " ".join(str(arg) for arg in args)
    if writer:
        writer.write(msg + "\n")
    print(*args, **kwargs)

def setup_display():
        # Optional OLED setup
    print("Trying I2C init")
    global display
    displayio.release_displays()
    # If no Group is defined, the display automatically mirrors the terminal. 
    
    try:
        i2c = busio.I2C(scl=i2c_scl_pin, sda=i2c_sda_pin, frequency=400000)
        bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
        display = SSD1306(bus, width=128, height=64)
        
        splash = displayio.Group()
        text = label.Label(terminalio.FONT, text="", x=0, y=8)  # y is baseline of first line
        splash.append(text)
        
        # This disables the status bar
        display.root_group = splash

        # Manual stdout/stderr mirroring
        global writer
        print("Preparing writer")
        writer = OLEDWriter(text, max_lines=5, cols=21)
        
        # sys.stdout = Tee(original_stdout, writer)
        
        cprint("Custom terminal ready")
        cprint(f"OLED on. V{VERSION}")
    except Exception as e:
        print(f"No OLED display available: {e}")

# --------------------------
# Example: read keyboard and show on SSD1306 OLED
# --------------------------
async def reader_task():
    """
    Periodically check the keyboard buffer and, if data is present,
    print to the REPL and optionally show on the OLED.
    """
    global kbd_active
    keys = []

    while True:
        # Ensure init is called repeatedly until ready is observed
        if not kbd_active:
            cprint("Init keys...")
            success = stow_kbd.init_kbd(
                uart_id=busio.UART,
                baudrate=9600,
                bits=8,
                parity=None,
                stop=1,
                tx=uart_txd_pin,
                rx=uart_rxd_pin,
                power_pin=kbd_power_pin,
                ready_timeout_ms=1000,  # Increased timeout to 1000ms
                rxbuf_max=128,
            )
            if success:
                cprint("Keys ready")
                kbd_active = True
            else:
                cprint("FAIL: timeout")

        if kbd_active and stow_kbd.uart.any():
            # Use get() method to process keypresses and send USB HID events
            scancode, key = stow_kbd.uart.get()  # This processes the data and sends USB keypresses automatically
            if scancode is not None and key is not None:
                cprint(f"Scan: 0x{scancode:02X} Key: 0x{key:02X}s")

        await asyncio.sleep(0.02)  # 10ms delay

def main():
    setup_display()
    # Start the reader loop
    try:
        cprint("Starting reader_task")
        asyncio.run(reader_task())
    except KeyboardInterrupt:
        cprint("Exiting gracefully...")
    except Exception as e:
        cprint(f"Reader_Task: {e}")
    finally:
        # Clean up if we ever exit
        if stow_kbd.keyboard:
            stow_kbd.keyboard.stop()

def main_test_text():
    # test display: 4 lines of 21 characters
    import board
    cprint("board.DISPLAY:", hasattr(board, "DISPLAY"))
    setup_display()
    for i in range(8):
        string = ""
        for k in range(21):
            string += str((i+ k+1) % 10)
        cprint(string)
    # Wait for enter to finish
    input()

# Entry point 
if __name__ == "__main__":
    main()
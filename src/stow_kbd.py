# MicroPython: Async UART keyboard reader for Stowaway keyboard
# Hardware targets: e.g. RP2040 (Pico) + UART keyboard module

import time
import board
import busio
import digitalio
import usb_hid
from adafruit_hid.keyboard import Keyboard

# -------------------------
# Keymap constant
# -------------------------
# Taken from the Stowaway documentation:
STOWAWAY_KEYMAP_US = [
    "1", "2", "3", "Z", "4", "5", "6", "7", # Y0
    "CMMD", "Q", "W", "E", "R", "T", "Y", "~", # Y1
    "X", "A", "S", "D", "F", "G", "H", "Space1", # Y2
    "CapsLock", "Tab", "Ctrl", None, None, None, None, None, # Y3
    None, None, "FN", "Alt", None, None, None, None, # Y4
    None, None, None, None, "C", "V", "B", "N", # Y5
    "-", "+", "Backspace", "Special1", "8", "9", "0", "Space2", # Y6
    "[", "]", "\\", "Special2", "U", "I", "O", "P", # Y7 - watch for escaped character \ here
    "'", "Enter", "Special3", None, "J", "K", "L",  ";", #Y8
    "/", "Up", "Special4", None, "M", ",", ".", "Done", # Y9
    "DEL", "Left", "Down", "Right", None, None, None, None, # 10
    "ShiftL", "ShiftR", None, None, None, None, None, None, # Y11
]

# Ve Germans want ze proper keyboard umlauts!
STOWAWAY_KEYMAP_DE = [
    "1", "2", "3", "Y", "4", "5", "6", "7", # Y0
    "Cmd", "Q", "W", "E", "R", "T", "Z", "<", # Y1
    "X", "A", "S", "d", "F", "G", "H", "Leer1", # Y2
    "CapsLock", "Tab", "Strg", "??", "??", "??", "??", "??", # Y3
    "??", "??", "Fn", "Alt", "??", "??", "??", "??", # Y4
    "??", "??", "??", "??", "C", "V", "B", "N", # Y5
    "Sz", "'", "Backspace", "KALEND", "8", "9", "0", "^", # Y6
    "Ue", "+", "#", "ADRESS", "U", "I", "O", "P", # Y7 - watch for escaped character \ here
    "Ae", "Eingabe", "AUFGAB", "??", "J", "K", "L",  "Oe", #Y8
    "-", "Up", "MEMO", "??", "M", ",", ".", "Fertig", # Y9
    "DEL", "Left", "Down", "Right", "??", "??", "??", "??", # 10
    "ShiftL", "ShiftR", "??", "??", "??", "??", "??", "??", # Y11
]

# STOWAWAY_KEYMAP = STOWAWAY_KEYMAP_US
STOWAWAY_KEYMAP = STOWAWAY_KEYMAP_DE # Comment this out for US keyboard

""" Keymap for sending USB keystrokes via adafruit_hid library.

    As the original keymap assumes an US-English keyboard, 
so does the USB driver. As a result, 
switching to another keyboard layout does not matter: 
You get what it says on the key. 

A couple of specials: 
- There is no ESC key on the Stowaway - use DONE key
- The SpaceRight is ^° on a German keyboard, the key left to
    the 1 key on a Mac keyboard (which is ´~ on a US Mac, so use
    GRAVE_ACCENT key
- The ACTUAL ´~ key is the Non-US \| (which translates to <> on the 
    German version of the Stowaway - it has code 104)
- There is no dedicated Fn key on USB keyboards; translate into 
    RIGHT_ALT, catch in the code, and translate. 
- The Stowaway's SPECIAL keys for calling dedicated applications
    are translated into F13-F16. 
"""

from adafruit_hid.keycode import Keycode as K


ADAFRUIT_KEYMAP = [
    K.ONE, K.TWO, K.THREE, K.Z, K.FOUR, K.FIVE, K.SIX, K.SEVEN, # Y0
    K.COMMAND, K.Q, K.W, K.E, K.R, K.T, K.Y, K.GRAVE_ACCENT, # Y1
    # 100 (0x64) is the USB keycode for Non-US \| 
    K.X, K.A, K.S, K.D, K.F, K.G, K.H, K.SPACEBAR, # Y2
    K.CAPS_LOCK, K.TAB, K.CONTROL, None, None, None, None, None, # Y3
    None, None, K.RIGHT_ALT, K.LEFT_ALT, None, None, None, None, # Y4 - Function Key!!!
    # Right-Alt is actually the Fn key on the Stowaway; catch in code. 
    None, None, None, None, K.C, K.V, K.B, K.N, # Y5
    K.MINUS, K.EQUALS, K.BACKSPACE, K.F13, K.EIGHT, K.NINE, K.ZERO, 100, # Y6
    K.LEFT_BRACKET, K.RIGHT_BRACKET, K.BACKSLASH, K.F14, K.U, K.I, K.O, K.P, # Y7 - watch for escaped character \ here
    K.QUOTE, K.ENTER, K.F15, None, K.J, K.K, K.L,  K.SEMICOLON, #Y8
    K.FORWARD_SLASH, K.UP_ARROW, K.F16, None, K.M, K.COMMA, K.PERIOD, K.ESCAPE, # Y9 - ESC is DONE key
    K.DELETE, K.LEFT_ARROW, K.DOWN_ARROW, K.RIGHT_ARROW, None, None, None, None, # 10
    K.LEFT_SHIFT, K.RIGHT_SHIFT, None, None, None, None, None, None, # Y11
]

FUNCTION_KEYS = [
    K.ONE, K.TWO, K.THREE, K.Z, K.FOUR, K.FIVE, K.SIX, K.SEVEN,
    K.EIGHT, K.NINE, K.ZERO, K.MINUS, K.EQUALS
]


# --------------------------
# Keyboard proxy: UART-like
# --------------------------
class _KbdProxy:
    """
    Thin wrapper so the rest of your code can use `uart.any()` / `uart.read()` / `uart.get()`
    without caring that the source is an AsyncKeyboard instance.
    """
    def __init__(self, kbd):
        self._kbd = kbd

    def any(self):
        # Return a count (0 if none), like machine.UART.any()
        return self._kbd.any() if self._kbd else 0

    def read(self):
        # Return buffered bytes (and clear buffer) or None if empty
        return self._kbd.read() if self._kbd else None
    
    def get(self):
        # Process buffered data and send USB keypresses
        return self._kbd.get() if self._kbd else None

# --------------------------------
# Asynchronous keyboard reader
# --------------------------------
class KeyboardReader:
    """
    Non-blocking UART keyboard reader.

    - Powers the device via `power_pin`
    - Waits for 'ready' handshake (0xF9, 0xFB) once after power-up
    - Buffers incoming bytes in RAM
    """
    def __init__(self, uart_id, baudrate, bits, parity, stop, tx, rx,
                 power_pin, ready_timeout_ms=200, rxbuf_max=1024):
        # Configure UART
        print("UART: TX={}, RX={}, baud={}".format(tx, rx, baudrate))
        try:
            self.uart = busio.UART(tx=tx, rx=rx, baudrate=baudrate)
            self.uart.timeout = 0.1  # Set a reasonable timeout
            print("UART OK")
        except Exception as e:
            print("UART fail: {}".format(e))
            raise
        self.kbd = Keyboard(usb_hid.devices)
        # Power control - initialize as OFF first (active-high assumed)
        self.power = digitalio.DigitalInOut(power_pin)
        self.power.direction = digitalio.Direction.OUTPUT
        # Explicitly set to OFF initially to ensure clean power cycle
        self.power.value = False
        # State
        self.ready = False
        self._buf = bytearray()
        self._rxbuf_max = rxbuf_max
        self._ready_timeout_ms = ready_timeout_ms
        # Track function and shift keys
        self.fn = False
        self.shift = False
        self.ctrl = False
        self.alt = False
        self.cmd = False

    def start(self):
        """Start the keyboard reader."""
        self._power_cycle()
        # After successful handshake, start background data reading
        if self.ready:
            print("Kbd reader start...")

    def stop(self):
        """Stop the keyboard reader and power down."""
        # Optionally power off the keyboard
        self.power.value = False

    def any(self):
        """Return number of bytes currently buffered."""
        # Read any new data first
        self._read_data()
        return len(self._buf)

    def read(self):
        """
        Return all buffered data as raw Stowaway scancodes
        and clear the buffer or None if nothing is available.
        """
        # Read any new data first
        self._read_data()
        if not self._buf:
            return None
        data = bytes(self._buf)
        self._buf = bytearray()
        return data
    
    def read_one(self):
        """
        Return one byte from the buffer
        and clear the buffer or None if nothing is available.
        """
        self._read_data()
        if not self._buf:
            return None
        
        data = bytes(self._buf)[0]
        self._buf = self._buf[1:]
        # If all keys are up, release key is sent twice. 
        # If that is the case, clear second byte and
        # clear all flags. 
        if data >= 0x80:
            if len(self._buf) > 0 and bytes(self._buf)[0] == data: 
                self._buf = self._buf[1:]
                self.fn = False
                self.ctrl = False
                self.shift = False
                self.alt = False
            # self._power_cycle_()
        return data
    
    def get(self):
        """
        Process all buffered data as USB keycodes,  
        sending them as keypresses via the adafruit_hid library.
        
        Return tuple: (keycode, scancode)
        """
        d = self.read_one()
        if not d:
            return None, None
            
        print("Scancode 0x{:02X}".format(d))
        scancode = d & 0x7F  # Remove key up/down bit
        is_keyup = (d & 0x80) != 0
        
        # Handle Fn key (mapped to RIGHT_ALT in keymap)
        if scancode < len(ADAFRUIT_KEYMAP) and ADAFRUIT_KEYMAP[scancode] == K.RIGHT_ALT:
            if is_keyup:
                self.fn = False
                print("Fn release")
            else:
                self.fn = True
                print("Fn pressed")
            return None, Nonersl  # Don't send the Fn key itself
            
        # Get the keycode for this scancode
        keycode = self.scan_to_keycode(scancode)
        if keycode is None:
            print("Unknown: 0x{:02X}".format(scancode))
            return d, None # d is original scancode
            
        # Key conversions for function keys
        if self.fn and keycode in [K.ONE, K.TWO, K.THREE, K.FOUR, K.FIVE, K.SIX, K.SEVEN, K.EIGHT, K.NINE, K.ZERO]:
            # Convert numbers to F1-F10 when Fn is pressed
            original_keycode = keycode
            if keycode == K.ZERO:
                keycode = K.F10
                print("Fn+0 -> F10")
            else:
                keycode = K.F1 + keycode - K.ONE
                print("Fn+{} -> F{}".format(original_keycode - K.ONE + 1, keycode - K.F1 + 1))
            
        # Send keypress/release
        try:
            if is_keyup:
                self.kbd.release(keycode)
                print("Keycode {} Release".format(keycode))
            else:
                self.kbd.press(keycode)
                print("Keycode {} Pressed".format(keycode))
        except Exception as e:
            print("Key Err: {}".format(e))
        return d, keycode
            

    def lookup(self, scancode):
        """
        Return a tuple of (key, up/down) for a given scancode.
        
        Args:
            scancode (byte): Stowaway keyboard scancode (0x00-0x7F), 
            with bit 7 set if key is being released.
        """
        modifier = (scancode & 0x80) > 0
        # True if key is being released
        # False if key is being pressed
        scancode &= 0x7F
        return STOWAWAY_KEYMAP[scancode] if scancode < len(STOWAWAY_KEYMAP) else None, modifier

    def scan_to_keycode(self, scancode):
        """
        Convert scancode into USB keycode.
        Returns USB keycode for a given scancode.

        Args:
            scancode (byte): Stowaway keyboard scancode (0x00-0x7F), 
            should already have bit 7 cleared by caller.
        """
        if scancode < len(ADAFRUIT_KEYMAP):
            return ADAFRUIT_KEYMAP[scancode]
        return None

    def _power_cycle(self):
        """
        Power-cycle the keyboard and wait for the ready handshake (0xF9, 0xFB).
        """
        print("Powercycling keys...")
        # Ensure power is OFF first, then cycle: OFF -> delay -> ON
        self.power.value = False
        time.sleep(0.02)  # 20ms additional startup time
        self.power.value = True
        time.sleep(0.02)  # 20ms delay as required
        print("Wait for Keys handshake")
        # Give the device a moment to power up before listening for handshake

        id_state = 0  # 0: expect 0xF9, 1: expect 0xFB
        t0 = time.monotonic()

        while True:
            n = self.uart.in_waiting
            if n:
                data = self.uart.read(n) or b""
                hex_str = ' '.join(['{:02X}'.format(b) for b in data])
                print("RX {} bytes: {}".format(len(data), hex_str))
                for b in data:
                    # Wait until keyboard announces it's ready
                    if not self.ready:
                        if id_state == 0:
                            if b == 0xF9:
                                print("(0xF9)", end=' ')
                                id_state = 1
                            # else stay in state 0
                        elif id_state == 1:
                            if b == 0xFB:
                                print("(0xFB) - keys ready")
                                self.ready = True
                                return  # Exit successfully when handshake is complete
                            else:
                                print("No 0xFB but 0x{:02X}, restarting".format(b))
                                id_state = 0  # restart sequence
                        continue

                    # After ready: buffer data (cap length to avoid runaway)
                    if len(self._buf) < self._rxbuf_max:
                        self._buf.append(b)
                    else:
                        # Drop oldest half if we overflow (simple backpressure)
                        cut = self._rxbuf_max // 2
                        self._buf = self._buf[cut:]
                        self._buf.append(b)

            # Check for timeout and exit if exceeded
            elapsed = (time.monotonic() - t0) * 1000  # Convert to ms
            if elapsed > self._ready_timeout_ms:
                print("Keys timeout: {:.1f}ms (limit: {}ms)".format(elapsed, self._ready_timeout_ms))
                return  # Exit on timeout, ready will remain False

            # Small delay to avoid busy-waiting
            time.sleep(0.001)

    def _read_data(self):
        """
        Read any available data from UART and buffer it.
        Should be called periodically after initialization.
        """
        if not self.ready:
            return
            
        n = self.uart.in_waiting
        if n:
            data = self.uart.read(n) or b""
            if data:
                for b in data:
                    # Buffer data (cap length to avoid runaway)
                    if len(self._buf) < self._rxbuf_max:
                        self._buf.append(b)
                    else:
                        # Drop oldest half if we overflow (simple backpressure)
                        cut = self._rxbuf_max // 2
                        self._buf = self._buf[cut:]
                        self._buf.append(b)

# --------------------------
# Module-level helpers
# --------------------------
keyboard = None   # AsyncKeyboard instance
uart = None       # _KbdProxy

def init_kbd(uart_id, baudrate, bits, parity, stop, tx, rx, power_pin, ready_timeout_ms=200, rxbuf_max=128):
    """
    Initialize the keyboard and return True when ready signature
    has been seen at least once.
    """
    global keyboard, uart
    if keyboard is None:
        try:
            print("Creating KeyboardReader...")
            keyboard = KeyboardReader(
                uart_id=uart_id,
                baudrate=baudrate,
                bits=bits,
                parity=parity,
                stop=stop,
                tx=tx,
                rx=rx,
                power_pin=power_pin,
                ready_timeout_ms=ready_timeout_ms,
                rxbuf_max=rxbuf_max,
            )
            print("Starting keyboard...")
            keyboard.start()
            print("Creating UART proxy...")
            # Provide a UART-like proxy (any/read)
            uart = _KbdProxy(keyboard)
            print("Keys ready: {}".format(keyboard.ready))
        except Exception as e:
            print("Keys init err: {}".format(e))
            return False
    return keyboard.ready
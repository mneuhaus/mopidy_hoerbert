import logging
import time
from time import sleep

import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)
longpress_time = 0.3


class GPIOManager():

    def __init__(self, frontend, pins):

        self.frontend = frontend

        self.correctlyLoaded = False

        self.down_time = {
            'button_black': -1,
            'button_green': -1,
        }
        self.buttons = {}
        self.rotary_encoders = {}

        try:
            GPIO.setmode(GPIO.BCM)
            #GPIO.setup(4, GPIO.OUT)
            self.correctlyLoaded = True
        except RuntimeError:
            logger.error("TTSGPIO: Not enough permission " +
                         "to use GPIO. GPIO input will not work")

    def register_button(self, pin, name, longpress=True):
        self.buttons[pin] = {
            "name": name,
            "down_time": -1
        }
        logger.info("Registering Button '" + name + "' on PIN " + str(pin))
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if longpress:
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=self.catch_button_press_with_longpress, bouncetime=30)
        else:
            GPIO.add_event_detect(pin, GPIO.BOTH, callback=self.catch_button_press, bouncetime=700)

    def catch_button_press_with_longpress(self, pin):
        button = self.buttons[pin]
        if GPIO.input(pin) == 1:
            if button["down_time"] >= 0:
                if button["down_time"] + longpress_time > time.time():
                    logger.info("Button '" + button["name"] + "' has been pressed")
                    self.frontend.input({'key': button["name"], 'long': False})
                else:
                    logger.info("Button '" + button["name"] + "' has been long pressed")
                    self.frontend.input({'key': button["name"], 'long': True})
            button["down_time"] = -1
        else:
            button["down_time"] = time.time()

    def catch_button_press(self, pin):
        button = self.buttons[pin]
        self.frontend.input({'key': button["name"], 'long': False})

    def register_rotary_encode(self, name, pin_up, pin_down, steps=3):
        encoder = RotaryEncoder(pin_up, pin_down, name, steps=steps, callback=self.catch_rotary_turn)
        self.rotary_encoders[name] = {
            "name": name
        }

    def catch_rotary_turn(self, name, delta):
        self.frontend.input({
            'key': name,
            'value': delta
        })

    def set_led(self, led_state):
        if self.correctlyLoaded:
            GPIO.output(4, led_state)


class RotaryEncoder:
    """
    A class to decode mechanical rotary encoder pulses.
    Ported to RPi.GPIO from the pigpio sample here:
    http://abyz.co.uk/rpi/pigpio/examples.html
    """

    def __init__(self, gpioA, gpioB, name, steps=5, callback=None, buttonPin=None, buttonCallback=None):
        """
        Instantiate the class. Takes three arguments: the two pin numbers to
        which the rotary encoder is connected, plus a callback to run when the
        switch is turned.

        The callback receives one argument: a `delta` that will be either 1 or -1.
        One of them means that the dial is being turned to the right; the other
        means that the dial is being turned to the left. I'll be damned if I know
        yet which one is which.
        """

        self.lastGpio = None
        self.gpioA = gpioA
        self.gpioB = gpioB
        self.callback = callback
        self.name = name
        self.steps = steps

        self.gpioButton = buttonPin
        self.buttonCallback = buttonCallback

        self.levA = 0
        self.levB = 0

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpioA, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.gpioB, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        GPIO.add_event_detect(self.gpioA, GPIO.BOTH, self._callback)
        GPIO.add_event_detect(self.gpioB, GPIO.BOTH, self._callback)

        if self.gpioButton:
            GPIO.setup(self.gpioButton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(self.gpioButton, GPIO.FALLING, self._buttonCallback, bouncetime=500)

    def destroy(self):
        GPIO.remove_event_detect(self.gpioA)
        GPIO.remove_event_detect(self.gpioB)
        GPIO.cleanup()

    def _buttonCallback(self, channel):
        self.buttonCallback(GPIO.input(channel))

    def _callback(self, channel):
        level = GPIO.input(channel)
        if channel == self.gpioA:
            self.levA = level
        else:
            self.levB = level

        # Debounce.
        # if channel == self.lastGpio:
        #    return

        # When both inputs are at 1, we'll fire a callback. If A was the most
        # recent pin set high, it'll be forward, and if B was the most recent pin
        # set high, it'll be reverse.
        self.lastGpio = channel
        if channel == self.gpioA and level == 1:
            if self.levB == 1:
                self.callback(self.name, self.steps)
                sleep(0.1)
        elif channel == self.gpioB and level == 1:
            if self.levA == 1:
                self.callback(self.name, - self.steps)
                sleep(0.1)

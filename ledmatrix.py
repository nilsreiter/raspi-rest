#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Generic imports
import os
import time
from datetime import datetime
from flask import Flask, jsonify, request
from queue import Queue, Empty
from threading import Thread, Lock
import werkzeug

# Imports specific to the use case
from luma.led_matrix.device import max7219
from luma.core.render import canvas
from luma.core.interface.serial import spi, noop
from luma.core.legacy import show_message as show_luma_message
from luma.core.legacy import text
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT
from PIL import ImageFont

# Constants
SCROLL_DELAY = "scroll_delay"
CONTRAST = "contrast"
STATE = "state"
TIME = "time"
OFF = "off"
MESSAGE = "message"
WHITE = "white"
C_SCROLL_DIRECTION = "scroll_direction"
C_LTR = "ltr"
C_BTT = "btt"

# Settings
cascaded = 4
block_orientation = 90
rotate = 1
inreverse = True

settings = {
    SCROLL_DELAY: 0.05,
    CONTRAST: 10,
    STATE: TIME,
    C_SCROLL_DIRECTION: C_LTR
}

# Inititalisation
app = Flask(__name__)

# Thread syncronization
commands = Queue()
statelock = Lock()

# Add welcome message to message queue
commands.put_nowait({"message": "Hello World", SCROLL_DELAY: settings[SCROLL_DELAY]})

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=90,
                 rotate=0, blocks_arranged_in_reverse_order=True)

# Font from here: https://www.dafont.com/eight-bit-dragon.font
font = ImageFont.truetype("Eight-Bit-Dragon.ttf", 8)

# Control functions for the device
def show_time(device, toggle):
    hours = datetime.now().strftime('%H')
    minutes = datetime.now().strftime('%M')
    toggle = not toggle
    device.contrast(settings[CONTRAST])
    with canvas(device) as draw:
        #draw.text((0,1), hours, fill=WHITE, font=font_437)
        #draw.text((font_437.getlength(hours), 1), ":" if toggle else " ", fill=WHITE, font=font_437)
        #draw.text((font_437.getlength(hours)+2,1), minutes, fill=WHITE, font=font_437)
        text(draw, (0, 1), hours, fill=WHITE, font=proportional(CP437_FONT))
        text(draw, (15, 1), ":" if toggle else " ", fill=WHITE, font=proportional(TINY_FONT))
        text(draw, (17, 1), minutes, fill=WHITE, font=proportional(CP437_FONT))
    time.sleep(0.5)

def show_nothing(device):
    device.clear()
    time.sleep(0.5)

def show_message(device, command):
   
    sd = float(command.get(SCROLL_DELAY, settings[SCROLL_DELAY]))
    contrast = int(command.get(CONTRAST, settings[CONTRAST]))
    device.contrast(contrast)

    pixelLength = int(font.getlength(command[MESSAGE]))
    
    scrollDirection = command.get(C_SCROLL_DIRECTION, settings[C_SCROLL_DIRECTION])
    
    if scrollDirection == C_BTT:
        pos = [0,8]
    else:
        pos = [32,0]

    
    def nextPos(pos, dir=C_LTR):
      if dir == C_BTT:
        return (pos[0], pos[1]-1)
      else:
        return (pos[0]-1, pos[1])

    if scrollDirection == C_BTT:
        maxIter = 17
    else:
        maxIter = pixelLength+40
    for i in range(0, maxIter):
        with canvas(device) as draw:
            draw.text( pos, command[MESSAGE], fill=10, font=font)
        time.sleep(sd)
        pos = nextPos(pos, scrollDirection)

def control_loop():
    toggle = False
    global state
    while True:
        toggle = not toggle
        try:
            command = commands.get_nowait()
            show_message(device, command)
        except Empty:
            statelock.acquire()
            if settings[STATE] == TIME:
                show_time(device, toggle)
            else:
                show_nothing(device)
            statelock.release()
        

# Flask functions
@app.route("/set", methods=["POST", "GET"])
def state_endpoint():
    global settings
    if request.method == 'POST':
        d = request.get_json()
        statelock.acquire()
        for k in settings:
          if k == STATE and d.get(k, settings[k]) not in [TIME, OFF]:
            raise werkzeug.exceptions.BadRequest
          if k == CONTRAST and ( d.get(k, settings[k]) < 0 or d.get(k, settings[k]) > 255):
            raise werkzeug.exceptions.BadRequest
          if k == SCROLL_DELAY and ( d.get(k, settings[k]) < 0 or d.get(k, settings[k]) > 1):
            raise werkzeug.exceptions.BadRequest
          settings[k] = d.get(k, settings[k])
        statelock.release()
        return d
    else:
        return settings

@app.route("/message", methods=['POST'])
def message_endpoint():
    command = request.get_json()
    if MESSAGE not in command.keys():
      raise werkzeug.exceptions.BadRequest
    commands.put_nowait(command)
    return {"result": "ok"}


if __name__ == "__main__":
    Thread(target=control_loop, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

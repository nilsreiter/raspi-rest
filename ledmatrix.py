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
from luma.core.legacy import text, textsize
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT
from PIL import ImageFont

# Constants
SCROLL_DELAY = "scroll_delay"
CONTRAST = "contrast"
STATE = "state"
STATUS_MESSAGE = "status_message"
TIME = "time"
OFF = "off"
MESSAGE = "message"
WHITE = "white"
C_SCROLL_DIRECTION = "scroll_direction"
C_LTR = "ltr"
C_BTT = "btt"
REPEAT = "repeat"

# Settings
cascaded = 8
block_orientation = 90
rotate = 0
inreverse = True

settings = {
    SCROLL_DELAY: 0.05,
    CONTRAST: 10,
    STATE: TIME,
    C_SCROLL_DIRECTION: C_LTR,
    STATUS_MESSAGE: None,
}

# Inititalisation
app = Flask(__name__)

# Thread syncronization
commands = Queue()
statelock = Lock()

# Add welcome message to message queue
commands.put_nowait({"message": "Hello World", SCROLL_DELAY: settings[SCROLL_DELAY]})

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=cascaded, block_orientation=block_orientation,
                 rotate=rotate, blocks_arranged_in_reverse_order=inreverse)

# font = ImageFont.truetype("fonts/FreePixel.ttf", 8)
font = ImageFont.truetype("fonts/dogicapixelbold.ttf", 8)
# font = ImageFont.truetype("fonts/SF-Compact-Display-Regular.ttf", 8)
# font = proportional(CP437_FONT)

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
        text(draw, (0, 0), hours, fill=WHITE, font=proportional(CP437_FONT))
        text(draw, (15, 0), ":" if toggle else " ", fill=WHITE, font=proportional(TINY_FONT))
        text(draw, (17, 0), minutes, fill=WHITE, font=proportional(CP437_FONT))
        if settings[STATUS_MESSAGE]:
            if "°" in settings[STATUS_MESSAGE] or "ø" in settings[STATUS_MESSAGE]:
                fnt=proportional(CP437_FONT)
                settings[STATUS_MESSAGE] = settings[STATUS_MESSAGE].replace("°", "ø")
                pixelLength = textsize(settings[STATUS_MESSAGE], fnt)[0] #(len(settings[STATUS_MESSAGE]))*8-4
                text(draw, (32 + (32-pixelLength), 0), settings[STATUS_MESSAGE], fill=1, font=fnt)
            else:
                pixelLength = int(font.getlength(settings[STATUS_MESSAGE]))
                text(draw, (32 + ((32-pixelLength)/2), 0), settings[STATUS_MESSAGE], fill=1, font=font)
    time.sleep(0.5)

 
def show_nothing(device):
    device.clear()
    time.sleep(0.5)

def show_message(device, command):
   
    sd = float(command.get(SCROLL_DELAY, settings[SCROLL_DELAY]))
    contrast = int(command.get(CONTRAST, settings[CONTRAST]))
    device.contrast(contrast)

    try:
        pixelLength = int(font.getlength(command[MESSAGE]))
    except AttributeError:
        pixelLength = len(command[MESSAGE])*8
        
    scrollDirection = command.get(C_SCROLL_DIRECTION, settings[C_SCROLL_DIRECTION])
    
    if scrollDirection == C_BTT:
        pos = [0,8]
    else:
        pos = [cascaded*8,1]

    
    def nextPos(pos, dir=C_LTR):
      if dir == C_BTT:
        return (pos[0], pos[1]-1)
      else:
        return (pos[0]-1, pos[1])

    if scrollDirection == C_BTT:
        maxIter = 17
    else:
        maxIter = pixelLength+cascaded*8

    text = "+ " + command[MESSAGE].strip() + " +"
    for i in range(0, maxIter):
        with canvas(device) as draw:
            # text(draw, pos, text, fill=10, font=font)
            draw.text( pos, text, fill=10, font=font)
        time.sleep(sd)
        pos = nextPos(pos, scrollDirection)

    if int(command.get(REPEAT, 0)) > 0:
        command[REPEAT] = int(command[REPEAT]) - 1
        commands.put_nowait(command)
        
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
        # print(settings)
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Generic imports
import os
import time
from datetime import datetime
from flask import Flask, jsonify, request
from queue import Queue, Empty
from threading import Thread, Lock

# Imports specific to the use case
from luma.led_matrix.device import max7219
from luma.core.render import canvas
from luma.core.interface.serial import spi, noop
from luma.core.legacy import show_message as show_luma_message
from luma.core.legacy import text
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT

# Settings
cascaded = 4
block_orientation = 90
rotate = 1
inreverse = True

contrast_time = 2
contrast_notification = 255

default_scroll_delay = 0.05

state = "time"

# Inititalisation
app = Flask(__name__)

# Thread syncronization
commands = Queue()
statelock = Lock()

# Add welcome message to message queue
commands.put_nowait({"message": "Hello World", "scroll_delay": 0.01})

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=90,
                 rotate=0, blocks_arranged_in_reverse_order=True)

# Control functions for the device
def show_time(device, toggle):
    hours = datetime.now().strftime('%H')
    minutes = datetime.now().strftime('%M')
    toggle = not toggle
    device.contrast(contrast_time)
    with canvas(device) as draw:
        text(draw, (0, 1), hours, fill="white", font=proportional(CP437_FONT))
        text(draw, (15, 1), ":" if toggle else " ", fill="white", font=proportional(TINY_FONT))
        text(draw, (17, 1), minutes, fill="white", font=proportional(CP437_FONT))
    time.sleep(0.5)

def show_nothing(device):
    device.clear()
    time.sleep(0.5)

def show_message(device, command):
   
    sd = float(command.get("scroll_delay", default_scroll_delay))
    contrast = int(command.get("contrast", contrast_notification))
    device.contrast(contrast)
    show_luma_message(device, command["message"],
         fill="white",
         font=proportional(CP437_FONT),
         scroll_delay=sd)

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
            if state == "time":
                show_time(device, toggle)
            else:
                show_nothing(device)
            statelock.release()
        

# Flask functions
@app.route("/state", methods=["POST", "GET"])
def state():
    global state
    if request.method == 'POST':
        d = request.get_json()
        newState = d.get("state", "off")
        if newState in ["time", "off"]:
            statelock.acquire()
            state = newState
            statelock.release()
        return {"result": "ok"}
    else:
        return {"state": state }

@app.route("/message", methods=['POST'])
def accept_message():
    command = request.get_json()
    if "message" not in command.keys():
      raise werkzeug.exceptions.BadRequest
    commands.put_nowait(command)
    return {"result": "ok"}


if __name__ == "__main__":
    Thread(target=control_loop, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import time
from datetime import datetime
from flask import Flask, jsonify, request

from luma.led_matrix.device import max7219
from luma.core.render import canvas
from luma.core.interface.serial import spi, noop
from luma.core.legacy import show_message, text
from luma.core.legacy.font import proportional, CP437_FONT, TINY_FONT
from queue import Queue, Empty
from threading import Thread, Lock

cascaded = 4
block_orientation = 90
rotate = 1
inreverse = True

contrast_time = 2
contrast_notification = 255

default_scroll_delay = 0.05

app = Flask(__name__)
commands = Queue()
statelock = Lock()
state = "time"

serial = spi(port=0, device=0, gpio=noop())
device = max7219(serial, cascaded=4, block_orientation=90,
                 rotate=0, blocks_arranged_in_reverse_order=True)

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
    
def game_loop():
    toggle = False
    global state
    while True:
        toggle = not toggle
        try:
            command = commands.get_nowait()
            if type(command) == str:
                state = command
                continue
            sd = float(command.get("scroll_delay", default_scroll_delay))
            contrast = int(command.get("contrast", contrast_notification))
            device.contrast(contrast)
            show_message(device, command["message"],
                 fill="white",
                 font=proportional(CP437_FONT),
                 scroll_delay=sd)
            # time.sleep(len(command["message"])*sd)
        except Empty:
            statelock.acquire()
            if state == "time":
                show_time(device, toggle)
            else:
                show_nothing(device)
            statelock.release()
        # sleep(5)  # TODO poll other things
        
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
            #commands.put_nowait(newState)
        return {"result": "ok"}
    else:
        return {"state": state }

@app.route("/", methods=['POST'])
def hello_world():
    d = request.get_json()
    text = d["message"]
    commands.put_nowait(d)
    return {"result": "ok"}


if __name__ == "__main__":
    show_message(device, "Hello World",
                 fill="white",
                 font=proportional(CP437_FONT),
                 scroll_delay=0.01)
    statelock.acquire()
    state = "time"
    statelock.release()
    Thread(target=game_loop, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

import pyautogui
from pynput import mouse, keyboard
import time
import json
import threading
import math

recorded_events = []
stop_flag = False
MIN_DIST = 2  # minimum distance to record

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def record_mouse():
    """Record only mouse movements at significant distances."""
    global recorded_events, stop_flag
    start_time = time.time()
    last_pos = pyautogui.position()

    while not stop_flag:
        x, y = pyautogui.position()
        t = time.time() - start_time

        if distance((x, y), last_pos) >= MIN_DIST:
            recorded_events.append({"type": "move", "pos": (x, y), "time": t})
            last_pos = (x, y)

        time.sleep(0.005)

def on_click(x, y, button, pressed):
    """Record click events using pynput for accuracy."""
    t = time.time() - start_time
    recorded_events.append({
        "type": "click",
        "pos": (x, y),
        "button": str(button).split(".")[1],  # "left" or "right"
        "action": "down" if pressed else "up",
        "time": t
    })

def on_key_press(key):
    global stop_flag
    if key == keyboard.Key.f10:
        stop_flag = True
        return False

def start_recording():
    global recorded_events, stop_flag, start_time
    recorded_events = []
    stop_flag = False

    print("Move your mouse and click. Press F10 to stop recording.")

    # Start mouse movement recording thread
    t1 = threading.Thread(target=record_mouse)
    t1.start()

    # Start click listener
    with mouse.Listener(on_click=on_click) as m_listener, keyboard.Listener(on_press=on_key_press) as k_listener:
        start_time = time.time()
        while not stop_flag:
            time.sleep(0.01)

    t1.join()

    # Save events
    with open("mouse_record.json", "w") as f:
        json.dump(recorded_events, f, indent=4)

    print(f"Recording saved with {len(recorded_events)} events.")

def replay():
    print("Starting replay...")
    with open("mouse_record.json", "r") as f:
        events = json.load(f)

    for i, e in enumerate(events):
        if i == 0:
            dt = e["time"]
        else:
            dt = e["time"] - events[i-1]["time"]

        if dt > 0:
            time.sleep(dt)

        x, y = e["pos"]

        if e["type"] == "move":
            pyautogui.moveTo(x, y, duration=0)
        elif e["type"] == "click":
            pyautogui.moveTo(x, y, duration=0)
            if e["action"] == "down":
                pyautogui.mouseDown(button=e["button"])
            else:
                pyautogui.mouseUp(button=e["button"])

    print("Replay finished.")

if __name__ == "__main__":
    mode = input("Record or Replay? (r/p): ").lower()
    if mode == "r":
        start_recording()
    elif mode == "p":
        replay()
    else:
        print("Invalid choice.")

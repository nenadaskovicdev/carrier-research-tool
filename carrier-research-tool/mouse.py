import time
import json
import select
from evdev import InputDevice, list_devices, ecodes
from wayland_automation.mouse_controller import Mouse
from wayland_automation.keyboard_controller import Keyboard

mouse_controller = Mouse()
keyboard_controller = Keyboard()

# ---------------------------
# 1. Record mouse events
# ---------------------------
def record_mouse(duration=5, output_file="mouse_record.json"):
    devices = [InputDevice(fn) for fn in list_devices()]
    mouse = None
    for dev in devices:
        if "mouse" in dev.name.lower():
            mouse = dev
            break
    if not mouse:
        raise Exception("No mouse device found")

    print(f"Recording mouse from {mouse.name} for {duration} seconds...")
    events = []
    start_time = time.time()

    mouse.grab()
    try:
        while time.time() - start_time < duration:
            r, _, _ = select.select([mouse.fd], [], [], 0.01)  # poll every 10ms
            if r:
                for event in mouse.read():
                    if event.type in (ecodes.EV_REL, ecodes.EV_KEY):
                        events.append({
                            "type": event.type,
                            "code": event.code,
                            "value": event.value,
                            "time": time.time() - start_time
                        })
    finally:
        mouse.ungrab()

    with open(output_file, "w") as f:
        json.dump(events, f, indent=2)

    if not events:
        print("\n⚠️  No events recorded!")
        print("Make sure you moved or clicked the mouse during recording.")
        print("Also, check your permissions: your user must be in the 'input' group or run with sudo.")
    else:
        print(f"Recorded {len(events)} events to {output_file}")
    return events

# ---------------------------
# 2. Replay mouse events
# ---------------------------
def replay_mouse(input_file="mouse_record.json"):
    with open(input_file) as f:
        events = json.load(f)

    if not events:
        print("No events to replay! Please record some events first.")
        return

    print(f"Replaying {len(events)} events...")
    last_time = 0
    for e in events:
        dt = e["time"] - last_time
        if dt > 0:
            time.sleep(dt)
        last_time = e["time"]

        if e["type"] == ecodes.EV_REL:
            if e["code"] == 0:  # X axis
                mouse_controller.move_cursor(e["value"], 0)
            elif e["code"] == 1:  # Y axis
                mouse_controller.move_cursor(0, e["value"])
        elif e["type"] == ecodes.EV_KEY:
            if e["code"] == 272:  # left button
                if e["value"]:
                    mouse_controller.click(
                        mouse_controller.get_position()[0],
                        mouse_controller.get_position()[1],
                        button="left")
            elif e["code"] == 273:  # right button
                if e["value"]:
                    mouse_controller.click(
                        mouse_controller.get_position()[0],
                        mouse_controller.get_position()[1],
                        button="right")

    print("Replay finished.")

# ---------------------------
# 3. Run script
# ---------------------------
if __name__ == "__main__":
    choice = input("Record or Replay? (r/p): ").strip().lower()
    if choice == "r":
        duration = int(input("Duration in seconds: ").strip())
        record_mouse(duration)
    elif choice == "p":
        replay_mouse()

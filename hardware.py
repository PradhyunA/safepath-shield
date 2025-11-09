import time

try:
    import serial
except ImportError:
    serial = None

class HardwareInterface:
    def __init__(self, port="/dev/ttyACM0", baud=115200):
        if serial is None:
            print("[HW] pyserial not installed; hardware disabled.")
            self.ser = None
            return
        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=1)
            time.sleep(2)
            print(f"[HW] Connected on {port}")
        except Exception as e:
            print(f"[HW] Could not open {port}: {e}")
            self.ser = None

    def send_plan(self, plan):
        if not self.ser:
            return
        lines = []
        for door_id, state in plan["doors"].items():
            lines.append(f"DOOR {door_id} {state}")
        msg = "\n".join(lines) + "\nEND\n"
        self.ser.write(msg.encode("utf-8"))

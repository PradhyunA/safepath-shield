import time

try:
    import serial  # type: ignore
except ImportError:
    serial = None


class HardwareInterface:
    """
    Sends door commands to Arduino over serial.
    Safe no-op if no serial or device not found.
    """

    def __init__(self, port="/dev/ttyACM0", baud=115200):
        self.ser = None
        if serial is None:
            print("[HW] pyserial not installed; hardware disabled.")
            return

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=1)
            time.sleep(2)
            print(f"[HW] Connected to {port}")
        except Exception as e:
            print(f"[HW] Could not open {port}: {e}")
            self.ser = None

    def send_plan(self, plan: dict):
        if not self.ser:
            return

        lines = []
        for door_id, state in plan.get("doors", {}).items():
            lines.append(f"DOOR {door_id} {state}")
        msg = "\n".join(lines) + "\nEND\n"

        try:
            self.ser.write(msg.encode("utf-8"))
        except Exception as e:
            print(f"[HW] Write failed: {e}")

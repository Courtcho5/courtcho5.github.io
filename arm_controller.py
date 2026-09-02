"""
Robotic Arm Controller
----------------------
Requirements: pip install pyserial
Run: python arm_controller.py

Arm dimensions:
  Base height : 13.5 cm
  Upper arm   : 14.0 cm
  Forearm     : 13.0 cm
  Wrist+grip  : 12.5 cm
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import time
import math

# ── Arm dimensions (cm) ──────────────────────────────────────────
BASE_HEIGHT = 13.5
L1          = 14.0   # upper arm  (shoulder → elbow)
L2          = 13.0   # forearm    (elbow → wrist)
L3          = 12.5   # wrist+grip (wrist → tip)

# ── IK servo offsets ─────────────────────────────────────────────
# These map geometric angles to your physical servo positions.
# HOW TO CALIBRATE:
#   1. Manually position the arm so it points straight forward, horizontally.
#   2. Note the servo angles shown on the sliders.
#   3. Adjust the offsets below until IK gives matching angles.
#
# BASE_OFFSET   : servo angle (S6) when arm faces the +X direction
# SHOULDER_OFFSET: servo angle (S5) when upper arm is horizontal (0°)
# ELBOW_OFFSET  : servo angle (S4) when forearm is straight (inline with upper arm)
# WRIST_OFFSET  : servo angle (S3) when wrist is neutral/level

BASE_OFFSET     = 150   # S6 home = 150 → treat as forward-facing
SHOULDER_OFFSET = 180   # S5 home = 180 → arm up
ELBOW_OFFSET    = 180   # S4 home = 180 → arm extended
WRIST_OFFSET    = 30    # S3 home = 30  → wrist neutral

# ── Servo config ─────────────────────────────────────────────────
SERVOS = [
    {"name": "Gripper",  "min": 120, "max": 180, "home": 180},
    {"name": "Wrist",    "min": 0,   "max": 180, "home": 30 },
    {"name": "Wrist 2",  "min": 0,   "max": 180, "home": 30 },
    {"name": "Elbow",    "min": 50,  "max": 180, "home": 180},
    {"name": "Shoulder", "min": 80,  "max": 180, "home": 180},
    {"name": "Base",     "min": 0,   "max": 180, "home": 150},
]

PRESETS = {
    "Home":     [180, 30,  30,  180, 180, 150],
    "Pick Up":  [119, 75,  30,  159, 121, 124],
    "Drop Off": [180, 93,  35,  148, 127, 53 ],
    "Rest":     [180, 30,  30,   50, 180, 90 ],
}

# ── Colors ────────────────────────────────────────────────────────
BG        = "#1a1a2e"
PANEL     = "#16213e"
ACCENT    = "#0f3460"
HIGHLIGHT = "#e94560"
TEXT      = "#eaeaea"
TEXT_DIM  = "#888888"
SUCCESS   = "#4ecca3"
WARNING   = "#f5a623"

# ── IK Math ───────────────────────────────────────────────────────

def inverse_kinematics(x, y, z):
    """
    Given a target position (x, y, z) in cm relative to the base centre
    on the floor, return servo angles for S6, S5, S4, S3.
    Returns (angles_dict, error_string) — one will be None.

    Coordinate system:
      X = forward from the base
      Y = left/right
      Z = up (0 = floor, 13.5 = shoulder height)
    """
    try:
        # ── 1. Base rotation (S6) ─────────────────────────────
        base_rad  = math.atan2(y, x)
        base_deg  = math.degrees(base_rad)
        # Offset so that arm facing +X = BASE_OFFSET on servo
        base_servo = BASE_OFFSET - base_deg
        base_servo = max(0, min(180, base_servo))

        # ── 2. Flatten into 2D plane (r, h) ───────────────────
        r = math.sqrt(x**2 + y**2)   # horizontal reach
        h = z - BASE_HEIGHT           # height above shoulder joint

        # Subtract wrist+gripper length (keep gripper horizontal)
        r_eff = r - L3
        # h_eff stays the same (gripper horizontal → no vertical offset)

        # ── 3. Shoulder-to-wrist distance ─────────────────────
        d = math.sqrt(r_eff**2 + h**2)

        if d > (L1 + L2):
            return None, f"Out of reach (max ~{L1+L2+L3:.1f} cm)"
        if d < abs(L1 - L2):
            return None, "Target too close to base"
        if r_eff < 0:
            return None, "Target too close — wrist would overshoot"

        # ── 4. Elbow angle (law of cosines) ───────────────────
        cos_e   = (L1**2 + L2**2 - d**2) / (2 * L1 * L2)
        cos_e   = max(-1.0, min(1.0, cos_e))
        elbow_rad = math.acos(cos_e)
        elbow_deg = math.degrees(elbow_rad)

        # ── 5. Shoulder angle ─────────────────────────────────
        phi     = math.atan2(h, r_eff)
        cos_s   = (L1**2 + d**2 - L2**2) / (2 * L1 * d)
        cos_s   = max(-1.0, min(1.0, cos_s))
        psi     = math.acos(cos_s)
        shoulder_rad = phi + psi
        shoulder_deg = math.degrees(shoulder_rad)

        # ── 6. Map to servo angles ────────────────────────────
        # Higher shoulder servo = more upright → subtract geo angle
        shoulder_servo = SHOULDER_OFFSET - shoulder_deg
        # Higher elbow servo = more extended → subtract geo angle
        elbow_servo    = ELBOW_OFFSET - elbow_deg
        # Wrist compensates to keep gripper level
        wrist_comp     = shoulder_deg + elbow_deg - 90
        wrist_servo    = WRIST_OFFSET + wrist_comp

        # ── 7. Check mechanical limits — refuse if any joint exceeds them ──
        checks = [
            ("S6 (Base)",     base_servo,     0,   180),
            ("S5 (Shoulder)", shoulder_servo, 80,  180),
            ("S4 (Elbow)",    elbow_servo,    50,  180),
            ("S3 (Wrist 2)",  wrist_servo,    0,   180),
        ]
        violations = []
        for name, val, lo, hi in checks:
            if val < lo or val > hi:
                violations.append(f"{name}: {int(round(val))}° (limit {lo}–{hi}°)")

        if violations:
            return None, "Joint limit exceeded:\n  " + "\n  ".join(violations)

        return {
            "S6": int(round(base_servo)),      # Base
            "S5": int(round(shoulder_servo)),  # Shoulder
            "S4": int(round(elbow_servo)),     # Elbow
            "S3": int(round(wrist_servo)),     # Wrist 2
        }, None

    except Exception as e:
        return None, str(e)


# ── App ───────────────────────────────────────────────────────────

class ArmController:
    def __init__(self, root):
        self.root = root
        self.root.title("Robotic Arm Controller")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.serial      = None
        self.connected   = False
        self.slider_vars = []
        self.angle_labels= []

        self._build_ui()
        self._refresh_ports()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        tf = tk.Frame(self.root, bg=HIGHLIGHT, pady=10)
        tf.pack(fill="x")
        tk.Label(tf, text="⚙  ROBOTIC ARM CONTROLLER",
                 font=("Courier", 14, "bold"), bg=HIGHLIGHT, fg=TEXT).pack()

        main = tk.Frame(self.root, bg=BG)
        main.pack(padx=16, pady=12, fill="both")

        left  = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", padx=(0, 10))

        right = tk.Frame(main, bg=BG)
        right.pack(side="right", fill="both")

        self._build_connection(left)
        self._build_sliders(left)
        self._build_presets(right)
        self._build_ik(right)
        self._build_log(right)

    def _build_connection(self, parent):
        frame = tk.LabelFrame(parent, text=" Connection ", font=("Courier", 9),
                               bg=PANEL, fg=TEXT_DIM, bd=1, relief="flat",
                               padx=10, pady=8)
        frame.pack(fill="x", pady=(0, 10))

        row = tk.Frame(frame, bg=PANEL)
        row.pack(fill="x")

        tk.Label(row, text="Port:", bg=PANEL, fg=TEXT,
                 font=("Courier", 10)).pack(side="left")

        self.port_var  = tk.StringVar()
        self.port_menu = ttk.Combobox(row, textvariable=self.port_var,
                                       width=12, state="readonly")
        self.port_menu.pack(side="left", padx=6)

        tk.Button(row, text="↺", bg=ACCENT, fg=TEXT, relief="flat",
                  font=("Courier", 11), cursor="hand2",
                  command=self._refresh_ports).pack(side="left", padx=(0, 6))

        self.connect_btn = tk.Button(row, text="Connect", bg=SUCCESS, fg=BG,
                                      font=("Courier", 10, "bold"), relief="flat",
                                      padx=10, cursor="hand2",
                                      command=self._toggle_connection)
        self.connect_btn.pack(side="left")

        self.status_label = tk.Label(frame, text="● Disconnected",
                                      bg=PANEL, fg=WARNING, font=("Courier", 9))
        self.status_label.pack(anchor="w", pady=(4, 0))

    def _build_sliders(self, parent):
        frame = tk.LabelFrame(parent, text=" Joint Control ", font=("Courier", 9),
                               bg=PANEL, fg=TEXT_DIM, bd=1, relief="flat",
                               padx=12, pady=8)
        frame.pack(fill="x")

        for i, servo in enumerate(SERVOS):
            self._build_slider_row(frame, i, servo)

        tk.Button(frame, text="⌂  All Home", bg=ACCENT, fg=TEXT,
                  font=("Courier", 10), relief="flat", padx=12, pady=4,
                  cursor="hand2", command=self._go_home).pack(pady=(10, 0))

    def _build_slider_row(self, parent, idx, servo):
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=4)

        tk.Label(row, text=f"S{idx+1}  {servo['name']:<10}",
                 bg=PANEL, fg=TEXT, font=("Courier", 10),
                 width=16, anchor="w").pack(side="left")

        tk.Label(row, text=str(servo["min"]), bg=PANEL, fg=TEXT_DIM,
                 font=("Courier", 9), width=3).pack(side="left")

        var = tk.IntVar(value=servo["home"])
        slider = tk.Scale(row, from_=servo["min"], to=servo["max"],
                          orient="horizontal", variable=var,
                          bg=PANEL, fg=TEXT, troughcolor=ACCENT,
                          highlightthickness=0, bd=0,
                          activebackground=HIGHLIGHT, sliderrelief="flat",
                          width=12, length=200, showvalue=False,
                          command=lambda v, i=idx: self.angle_labels[i].config(text=f"{v}°"))
        slider.bind("<ButtonRelease-1>",
                    lambda e, i=idx: self._on_slider(i, self.slider_vars[i].get()))
        slider.pack(side="left", padx=4)

        tk.Label(row, text=str(servo["max"]), bg=PANEL, fg=TEXT_DIM,
                 font=("Courier", 9), width=3).pack(side="left")

        angle_lbl = tk.Label(row, text=f"{servo['home']}°",
                              bg=HIGHLIGHT, fg=TEXT,
                              font=("Courier", 10, "bold"),
                              width=4, anchor="center")
        angle_lbl.pack(side="left", padx=(4, 0))

        self.slider_vars.append(var)
        self.angle_labels.append(angle_lbl)

    def _build_presets(self, parent):
        frame = tk.LabelFrame(parent, text=" Presets ", font=("Courier", 9),
                               bg=PANEL, fg=TEXT_DIM, bd=1, relief="flat",
                               padx=12, pady=8)
        frame.pack(fill="x", pady=(0, 10))

        row1 = tk.Frame(frame, bg=PANEL); row1.pack()
        row2 = tk.Frame(frame, bg=PANEL); row2.pack(pady=(4,0))

        for i, (name, angles) in enumerate(PRESETS.items()):
            r = row1 if i < 2 else row2
            tk.Button(r, text=name, bg=ACCENT, fg=TEXT,
                      font=("Courier", 10), relief="flat",
                      padx=8, pady=5, width=10, cursor="hand2",
                      command=lambda a=angles: self._run_preset(a)).pack(side="left", padx=3)

    def _build_ik(self, parent):
        frame = tk.LabelFrame(parent, text=" Inverse Kinematics ", font=("Courier", 9),
                               bg=PANEL, fg=TEXT_DIM, bd=1, relief="flat",
                               padx=12, pady=8)
        frame.pack(fill="x", pady=(0, 10))

        # Info label
        tk.Label(frame, text="Move gripper tip to position (cm):",
                 bg=PANEL, fg=TEXT_DIM, font=("Courier", 9)).pack(anchor="w")

        # X Y Z inputs
        coords = tk.Frame(frame, bg=PANEL)
        coords.pack(fill="x", pady=6)

        self.ik_vars = {}
        defaults = {"X": 20.0, "Y": 0.0, "Z": 5.0}

        for axis, default in defaults.items():
            col = tk.Frame(coords, bg=PANEL)
            col.pack(side="left", padx=(0, 10))
            tk.Label(col, text=axis, bg=PANEL, fg=HIGHLIGHT,
                     font=("Courier", 11, "bold")).pack()
            var = tk.StringVar(value=str(default))
            tk.Entry(col, textvariable=var, width=7,
                     bg=ACCENT, fg=TEXT, insertbackground=TEXT,
                     font=("Courier", 10), relief="flat").pack()
            self.ik_vars[axis] = var

        # Buttons
        btn_row = tk.Frame(frame, bg=PANEL)
        btn_row.pack(fill="x", pady=(4, 0))

        tk.Button(btn_row, text="Calculate", bg=ACCENT, fg=TEXT,
                  font=("Courier", 10), relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._ik_calculate).pack(side="left", padx=(0, 6))

        tk.Button(btn_row, text="▶  Send to Arm", bg=SUCCESS, fg=BG,
                  font=("Courier", 10, "bold"), relief="flat", padx=8, pady=4,
                  cursor="hand2", command=self._ik_send).pack(side="left")

        # Results display
        self.ik_result_frame = tk.Frame(frame, bg=PANEL)
        self.ik_result_frame.pack(fill="x", pady=(8, 0))

        self.ik_status = tk.Label(frame, text="", bg=PANEL,
                                   font=("Courier", 9), fg=TEXT_DIM)
        self.ik_status.pack(anchor="w", pady=(4, 0))

        # Store last calculated angles
        self.ik_angles = None

    def _build_log(self, parent):
        frame = tk.LabelFrame(parent, text=" Log ", font=("Courier", 9),
                               bg=PANEL, fg=TEXT_DIM, bd=1, relief="flat",
                               padx=8, pady=8)
        frame.pack(fill="both", expand=True)

        self.log = tk.Text(frame, bg=BG, fg=SUCCESS, font=("Courier", 9),
                           width=36, height=7, relief="flat",
                           state="disabled", cursor="arrow")
        self.log.pack(fill="both", expand=True)

        tk.Button(frame, text="Clear", bg=ACCENT, fg=TEXT_DIM,
                  font=("Courier", 9), relief="flat", cursor="hand2",
                  command=self._clear_log).pack(pady=(4, 0))

    # ── Serial ────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_menu["values"] = ports
        if ports:
            self.port_var.set(ports[0])

    def _toggle_connection(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "No port selected")
            return
        try:
            self.serial = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)
            self.connected = True
            self.connect_btn.config(text="Disconnect", bg=HIGHLIGHT)
            self.status_label.config(text=f"● Connected on {port}", fg=SUCCESS)
            self._log(f"Connected to {port}")
            threading.Thread(target=self._read_serial, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection failed", str(e))

    def _disconnect(self):
        if self.serial:
            self.serial.close()
        self.connected = False
        self.connect_btn.config(text="Connect", bg=SUCCESS)
        self.status_label.config(text="● Disconnected", fg=WARNING)
        self._log("Disconnected")

    def _send(self, cmd):
        if not self.connected:
            self._log("Not connected!")
            return
        try:
            self.serial.write((cmd + "\n").encode())
            self._log(f">> {cmd}")
        except Exception as e:
            self._log(f"Error: {e}")

    def _read_serial(self):
        while self.connected:
            try:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode().strip()
                    if line:
                        self._log(f"<< {line}")
            except:
                break

    # ── Controls ──────────────────────────────────────────────────

    def _on_slider(self, idx, value):
        self.angle_labels[idx].config(text=f"{value}°")
        self._send(f"S{idx+1} {value}")

    def _go_home(self):
        self._log("Moving to Home...")
        for i, servo in enumerate(SERVOS):
            self.slider_vars[i].set(servo["home"])
            self.angle_labels[i].config(text=f"{servo['home']}°")
        self._send("HOME")

    def _run_preset(self, angles):
        order = [1, 2, 3, 4, 5, 0]  # gripper last
        for i in order:
            self.slider_vars[i].set(angles[i])
            self.angle_labels[i].config(text=f"{angles[i]}°")
            self._send(f"S{i+1} {angles[i]}")
            time.sleep(0.8)

    # ── IK ────────────────────────────────────────────────────────

    def _ik_calculate(self):
        """Run IK and display results without sending."""
        try:
            x = float(self.ik_vars["X"].get())
            y = float(self.ik_vars["Y"].get())
            z = float(self.ik_vars["Z"].get())
        except ValueError:
            self.ik_status.config(text="⚠ Enter valid numbers for X, Y, Z", fg=WARNING)
            return

        angles, error = inverse_kinematics(x, y, z)

        # Clear old result widgets
        for w in self.ik_result_frame.winfo_children():
            w.destroy()

        if error:
            self.ik_status.config(text=f"⚠ {error}", fg=WARNING)
            self.ik_angles = None
            return

        self.ik_angles = angles

        # Show calculated angles
        labels = {"S6": "Base", "S5": "Shoulder", "S4": "Elbow", "S3": "Wrist 2"}
        for servo, deg in angles.items():
            row = tk.Frame(self.ik_result_frame, bg=PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{servo} ({labels[servo]}):",
                     bg=PANEL, fg=TEXT_DIM, font=("Courier", 9),
                     width=18, anchor="w").pack(side="left")
            tk.Label(row, text=f"{deg}°",
                     bg=PANEL, fg=SUCCESS, font=("Courier", 9, "bold")).pack(side="left")

        self.ik_status.config(
            text=f"✓ Calculated for ({x}, {y}, {z}) cm — press Send to move",
            fg=SUCCESS)

    def _ik_send(self):
        """Calculate then send angles to the arm."""
        self._ik_calculate()
        if not self.ik_angles:
            return

        self._log(f"IK move → {self.ik_angles}")

        # Servo index map: S6=idx5, S5=idx4, S4=idx3, S3=idx2
        idx_map = {"S6": 5, "S5": 4, "S4": 3, "S3": 2}

        # Move base and shoulder first, then elbow, then wrist
        order = ["S6", "S5", "S4", "S3"]
        for key in order:
            idx  = idx_map[key]
            deg  = self.ik_angles[key]
            self.slider_vars[idx].set(deg)
            self.angle_labels[idx].config(text=f"{deg}°")
            self._send(f"S{idx+1} {deg}")
            time.sleep(0.8)

    # ── Log ───────────────────────────────────────────────────────

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


# ── Run ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x620")
    app = ArmController(root)
    root.mainloop()
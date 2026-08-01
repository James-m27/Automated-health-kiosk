import customtkinter as ctk
import time
import subprocess
import threading
from hardware_api import TemperatureSensor, PulseOximeter, BloodPressureMonitor, ThermalPrinter
import os
import signal

# ─────────────────────────────────────────────
#  Basic Configuration
# ─────────────────────────────────────────────
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ─────────────────────────────────────────────
#  Colour Palette
# ─────────────────────────────────────────────
C_BG           = "#1a1a2e"   # deep navy background
C_PANEL        = "#16213e"   # slightly lighter panel
C_CARD         = "#0f3460"   # card blue
C_ACCENT       = "#1f6aa5"   # primary accent
C_ACCENT_LIGHT = "#57bbff"   # highlight / active state
C_RED          = "#e94560"   # warning / stop
C_GREEN        = "#4caf50"   # success
C_TEXT_MAIN    = "#e0e0e0"
C_TEXT_DIM     = "#a0a0b0"
C_SIDEBAR      = "#12122a"


# Initialize Hardware
hw_temp = TemperatureSensor()
hw_pulse = PulseOximeter()
hw_bp = BloodPressureMonitor()
hw_printer = ThermalPrinter()


# ─────────────────────────────────────────────
#  Guided Steps Configuration
# ─────────────────────────────────────────────
STEPS = [
    {
        "title": "Step 1 of 3 — Body Temperature",
        "instruction": "Place the thermometer gently against your forehead\nand remain still.",
        "icon": "🌡️",
        "key": "temperature",
        "unit": "°C",
        "reader": hw_temp.get_reading,
        "duration": 2,
    },
    {
        "title": "Step 2 of 3 — Heart Rate & SpO₂",
        "instruction": "Insert your index finger into the pulse oximeter\ncup and keep your hand relaxed and steady.",
        "icon": "💓",
        "key": ["heart_rate", "spo2"],
        "unit": "BPM  |  %",
        "reader": hw_pulse.get_reading,
        "duration": 15,
    },
    {
        "title": "Step 3 of 3 — Blood Pressure",
        "instruction": "Place your arm through the cuff and sit upright.\nPress the button on the cuff to begin inflation.",
        "icon": "🩺",
        "key": "blood_pressure",
        "unit": "mmHg",
        "reader": hw_bp.get_reading,
        "duration": 45,
    },
]

INACTIVITY_TIMEOUT = 180   # seconds (3 minutes)


class VirtualKeyboard(ctk.CTkToplevel):
    def __init__(self, parent, target_entry):
        super().__init__(parent)
        self.target_entry = target_entry
        self.title("Touch Keyboard")
        self.configure(fg_color=C_PANEL)
        self.resizable(False, False)
        
        # Keep window on top
        self.attributes("-topmost", True)
        self.transient(parent)

        # 1. BUILD THE KEYBOARD FIRST 
        # (This allows the app to calculate the new scaled size of the buttons)
        self._build_keyboard()

        # 2. THEN CALCULATE SIZE AND CENTER IT
        self.update_idletasks()
        w = self.winfo_reqwidth()  # Dynamically get the required width
        h = self.winfo_reqheight() # Dynamically get the required height
        
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, self.winfo_screenheight() - h - 15)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_keyboard(self):
        layout = [
            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', '⌫']
        ]

        # Key rows
        for row in layout:
            frame = ctk.CTkFrame(self, fg_color="transparent")
            frame.pack(pady=4)
            for key in row:
                btn_w = 70 if key == '⌫' else 58
                btn = ctk.CTkButton(
                    frame, text=key, width=btn_w, height=48,
                    font=ctk.CTkFont(size=18, weight="bold"),
                    fg_color=C_CARD, hover_color=C_ACCENT,
                    command=lambda k=key: self._press(k)
                )
                btn.pack(side="left", padx=3)

        # Bottom row: Space and Done
        bot_frame = ctk.CTkFrame(self, fg_color="transparent")
        bot_frame.pack(pady=6)

        ctk.CTkButton(
            bot_frame, text="SPACE", width=340, height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=C_CARD, hover_color=C_ACCENT,
            command=lambda: self._press(" ")
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            bot_frame, text="DONE  ✓", width=140, height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=C_GREEN, hover_color="#388e3c",
            command=self.destroy
        ).pack(side="left", padx=6)

    def _press(self, key):
        if key == '⌫':
            current = self.target_entry.get()
            self.target_entry.delete(0, 'end')
            self.target_entry.insert(0, current[:-1])
        else:
            self.target_entry.insert('end', key)


# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────
class MedicalKioskApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Medical Kiosk  –  ver 1.0")

        # --- FULLSCREEN ---
        self.attributes("-fullscreen", True)
        self.configure(fg_color=C_BG)

        # --- TOUCH SCALING ---
        ctk.set_widget_scaling(1.7)

        # ── Session state ──
        self.patient_name   = ""
        self.results        = {}
        self.current_step   = 0
        self.session_active = True
        self.active_entry   = None
        self.vkb            = None

        # ── Inactivity timer ──
        self._inactivity_seconds = 0
        self._inactivity_job    = None
        self.bind_all("<Any-KeyPress>",  self._reset_inactivity)
        self.bind_all("<Any-Button>",    self._reset_inactivity)
        self.bind_all("<Motion>",        self._reset_inactivity)
        self._start_inactivity_timer()

        # ── Build layout ──
        self._build_layout()

        # ── Show welcome screen ──
        self.show_welcome()

    def _show_keyboard(self, event=None):
        if hasattr(self, 'active_entry') and self.active_entry:
            if not hasattr(self, 'vkb') or not self.vkb or not self.vkb.winfo_exists():
                self.vkb = VirtualKeyboard(self, self.active_entry)

    def _hide_keyboard(self, event=None):
        if hasattr(self, 'vkb') and self.vkb and self.vkb.winfo_exists():
            self.vkb.destroy()

    # ─────────────────────────────────────────
    #  Layout
    # ─────────────────────────────────────────
    def _build_layout(self):
        """Permanent sidebar + swappable main area."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0,
                                    fg_color=C_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(5, weight=1)

        logo = ctk.CTkLabel(self.sidebar, text="HEALTH\nKIOSK",
                            font=ctk.CTkFont(family="Courier New", size=22, weight="bold"),
                            text_color=C_ACCENT_LIGHT)
        logo.grid(row=0, column=0, padx=20, pady=(30, 6))

        divider = ctk.CTkFrame(self.sidebar, height=2, fg_color=C_ACCENT)
        divider.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.sidebar_status = ctk.CTkLabel(
            self.sidebar, text="Welcome", wraplength=160,
            font=ctk.CTkFont(size=12), text_color=C_TEXT_DIM)
        self.sidebar_status.grid(row=2, column=0, padx=14, pady=6)

        self.progress_label = ctk.CTkLabel(
            self.sidebar, text="", wraplength=160,
            font=ctk.CTkFont(size=11), text_color=C_TEXT_DIM)
        self.progress_label.grid(row=3, column=0, padx=14, pady=4)

        # End Session button
        self.end_btn = ctk.CTkButton(
            self.sidebar, text="End Session",
            fg_color="transparent", border_width=2,
            border_color=C_RED, text_color=C_RED,
            hover_color="#3a0012",
            font=ctk.CTkFont(size=13),
            command=self._end_session)
        self.end_btn.grid(row=6, column=0, padx=20, pady=30, sticky="s")

        # ── Main area container ──
        self.main_container = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        self._current_frame = None

    def _swap_frame(self, new_frame: ctk.CTkFrame):
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = new_frame
        new_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

    # ─────────────────────────────────────────
    #  Inactivity Timer
    # ─────────────────────────────────────────
    def _start_inactivity_timer(self):
        self._inactivity_seconds = 0
        self._tick_inactivity()

    def _tick_inactivity(self):
        if not self.session_active:
            return
        self._inactivity_seconds += 1
        if self._inactivity_seconds >= INACTIVITY_TIMEOUT:
            self.show_goodbye(reason="inactivity")
        else:
            self._inactivity_job = self.after(1000, self._tick_inactivity)

    def _reset_inactivity(self, event=None):
        self._inactivity_seconds = 0

    def _set_end_btn(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.end_btn.configure(state=state)

    def _end_session(self):
        self.show_goodbye(reason="user")

    # ─────────────────────────────────────────
    #  SCREEN 1 — Welcome
    # ─────────────────────────────────────────
    def show_welcome(self):
        self._set_end_btn(True)
        self.sidebar_status.configure(text="Welcome")
        self.progress_label.configure(text="")

        f = ctk.CTkFrame(self.main_container, fg_color=C_PANEL, corner_radius=20)

        bar = ctk.CTkFrame(f, fg_color=C_ACCENT, height=6, corner_radius=3)
        bar.pack(fill="x", padx=0, pady=(0, 0))

        ctk.CTkLabel(f, text="🏥", font=ctk.CTkFont(size=64)).pack(pady=(40, 10))

        ctk.CTkLabel(f, text="Welcome to the Health Kiosk",
                     font=ctk.CTkFont(family="Georgia", size=28, weight="bold"),
                     text_color=C_TEXT_MAIN).pack(pady=(0, 8))

        ctk.CTkLabel(f,
                     text="This device measures your:\n"
                          "Body Temperature  ·  Heart Rate  ·  Blood Pressure  ·  SpO₂",
                     font=ctk.CTkFont(size=14), text_color=C_TEXT_DIM,
                     justify="center").pack(pady=(0, 6))

        ctk.CTkLabel(f,
                     text="The session takes about 2–3 minutes.\n"
                          "Please remove any nail polish before placing your finger on the sensor.",
                     font=ctk.CTkFont(size=13), text_color=C_TEXT_DIM,
                     justify="center").pack(pady=(0, 30))

        ctk.CTkButton(f, text="Get Started  →",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=C_ACCENT, hover_color="#2980b9",
                      width=220, height=48,
                      command=self.show_name_entry).pack(pady=(0, 40))

        self._swap_frame(f)

    # ─────────────────────────────────────────
    #  SCREEN 2 — Name Entry
    # ─────────────────────────────────────────
    def show_name_entry(self):
        self._set_end_btn(True)
        self.sidebar_status.configure(text="Patient Details")

        f = ctk.CTkFrame(self.main_container, fg_color=C_PANEL, corner_radius=20)
        ctk.CTkFrame(f, fg_color=C_ACCENT, height=6, corner_radius=3).pack(fill="x")

        ctk.CTkLabel(f, text="👤", font=ctk.CTkFont(size=52)).pack(pady=(50, 10))

        ctk.CTkLabel(f, text="Please enter your name",
                     font=ctk.CTkFont(family="Georgia", size=24, weight="bold"),
                     text_color=C_TEXT_MAIN).pack(pady=(0, 6))

        ctk.CTkLabel(f, text="Your name will appear on the printed report.",
                     font=ctk.CTkFont(size=13), text_color=C_TEXT_DIM).pack(pady=(0, 24))

        name_var = ctk.StringVar()
        entry = ctk.CTkEntry(f, textvariable=name_var,
                             placeholder_text="First and Last Name",
                             width=320, height=48,
                             font=ctk.CTkFont(size=15))
        entry.pack(pady=(0, 8))
        
        self.active_entry = entry
        entry.bind("<FocusIn>", self._show_keyboard)
        entry.bind("<Button-1>", self._show_keyboard)

        err_label = ctk.CTkLabel(f, text="", text_color=C_RED,
                                 font=ctk.CTkFont(size=12))
        err_label.pack()

        def proceed():
            name = name_var.get().strip()
            if len(name) < 2:
                err_label.configure(text="Please enter a valid name (at least 2 characters).")
                return
            self._hide_keyboard()
            self.patient_name = name
            self.results = {}
            self.current_step = 0
            self.show_step()

        entry.bind("<Return>", lambda e: proceed())

        ctk.CTkButton(f, text="Begin Measurements  →",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=C_ACCENT, hover_color="#2980b9",
                      width=260, height=48,
                      command=proceed).pack(pady=24)

        self._swap_frame(f)
        
        entry.focus()
        self.after(400, self._show_keyboard)

    # ─────────────────────────────────────────
    #  SCREEN 3 — Guided Step
    # ─────────────────────────────────────────
    def show_step(self):
        if self.current_step >= len(STEPS):
            self.show_results()
            return

        step = STEPS[self.current_step]
        self._set_end_btn(False)
        self.sidebar_status.configure(text=f"Measuring…\n({self.current_step+1}/{len(STEPS)})")
        progress_lines = []
        for i in range(len(STEPS)):
            icon = '✅' if i < self.current_step else ('▶' if i == self.current_step else '○')
            key_data = STEPS[i]['key']
            if isinstance(key_data, list):
                label_name = " & ".join(k.replace('_', ' ').title() for k in key_data)
            else:
                label_name = key_data.replace('_', ' ').title()
                
            progress_lines.append(f"{icon} {label_name}")
            
        self.progress_label.configure(text="\n".join(progress_lines))

        f = ctk.CTkFrame(self.main_container, fg_color=C_PANEL, corner_radius=20)
        ctk.CTkFrame(f, fg_color=C_ACCENT_LIGHT, height=6, corner_radius=3).pack(fill="x")

        ctk.CTkLabel(f, text=step["icon"], font=ctk.CTkFont(size=56)).pack(pady=(40, 6))

        ctk.CTkLabel(f, text=step["title"],
                     font=ctk.CTkFont(family="Georgia", size=20, weight="bold"),
                     text_color=C_ACCENT_LIGHT).pack(pady=(0, 4))

        ctk.CTkLabel(f, text=step["instruction"],
                     font=ctk.CTkFont(size=15), text_color=C_TEXT_MAIN,
                     justify="center").pack(pady=(4, 30))

        prog_bar = ctk.CTkProgressBar(f, width=400, height=18,
                                       progress_color=C_ACCENT_LIGHT,
                                       fg_color="#2b2b2b")
        prog_bar.pack(pady=(0, 8))
        prog_bar.set(0)

        status_lbl = ctk.CTkLabel(f, text="Press the button below to start this measurement.",
                                  font=ctk.CTkFont(size=13), text_color=C_TEXT_DIM)
        status_lbl.pack(pady=(0, 20))

        reading_lbl = ctk.CTkLabel(f, text="",
                                   font=ctk.CTkFont(size=38, weight="bold"),
                                   text_color=C_ACCENT)
        reading_lbl.pack()

        unit_lbl = ctk.CTkLabel(f, text="",
                                 font=ctk.CTkFont(size=14), text_color=C_TEXT_DIM)
        unit_lbl.pack(pady=(0, 10))

        measure_btn = ctk.CTkButton(
            f, text="Start Measurement",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=C_ACCENT, hover_color="#2980b9",
            width=220, height=44)
        measure_btn.pack(pady=16)

        self._swap_frame(f)

        def do_measure():
            measure_btn.configure(state="disabled", text="Measuring…")
            status_lbl.configure(text="Please remain still…", text_color=C_ACCENT_LIGHT)
            
            result_container = []

            def background_task():
                val = step["reader"]()
                result_container.append(val)

            thread = threading.Thread(target=background_task)
            thread.start()

            expected_duration = step.get("duration", 5)
            increment = 0.2 / expected_duration

            def check_thread():
                if thread.is_alive():
                    current_prog = prog_bar.get()
                    if current_prog < 0.95:
                        prog_bar.set(current_prog + increment)
                    f.after(200, check_thread)
                else:
                    prog_bar.set(1.0)
                    value = result_container[0]
                    
                    if isinstance(step["key"], list):
                        self.results[step["key"][0]] = value[0] 
                        self.results[step["key"][1]] = value[1] 
                        display_text = f"{value[0]}  |  {value[1]}"
                    elif isinstance(value, tuple):
                        formatted_bp = f"{value[0]}/{value[1]}"
                        self.results[step["key"]] = formatted_bp
                        display_text = formatted_bp
                    else:
                        self.results[step["key"]] = value
                        display_text = value
                    
                    reading_lbl.configure(text=display_text)
                    unit_lbl.configure(text=step["unit"])
                    status_lbl.configure(text="✅  Reading complete!", text_color=C_GREEN)
                    
                    measure_btn.configure(
                        state="normal",
                        text="Next  →" if self.current_step < len(STEPS) - 1 else "View Results  →",
                        fg_color=C_GREEN, hover_color="#388e3c",
                        command=next_step)

            check_thread()

        def next_step():
            self.current_step += 1
            self.show_step()

        measure_btn.configure(command=do_measure)

    # ─────────────────────────────────────────
    #  SCREEN 4 — Results
    # ─────────────────────────────────────────
    def show_results(self):
        self._set_end_btn(True)
        self.sidebar_status.configure(text="Results Ready")
        self.progress_label.configure(text="✅ All readings complete")

        f = ctk.CTkFrame(self.main_container, fg_color=C_PANEL, corner_radius=20)
        ctk.CTkFrame(f, fg_color=C_GREEN, height=6, corner_radius=3).pack(fill="x")

        ctk.CTkLabel(f, text=f"Results for {self.patient_name}",
                     font=ctk.CTkFont(family="Georgia", size=22, weight="bold"),
                     text_color=C_TEXT_MAIN).pack(pady=(28, 4))

        import datetime
        ts = datetime.datetime.now().strftime("%d %b %Y  %H:%M")
        ctk.CTkLabel(f, text=ts, font=ctk.CTkFont(size=12),
                     text_color=C_TEXT_DIM).pack(pady=(0, 18))

        cards_frame = ctk.CTkFrame(f, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=24)
        cards_frame.grid_columnconfigure((0, 1), weight=1)
        cards_frame.grid_rowconfigure((0, 1), weight=1)

        display_map = [
            ("Temperature",    self.results.get("temperature", "—"),    "°C",   0, 0, "🌡️"),
            ("Heart Rate",     self.results.get("heart_rate", "—"),     "BPM",  0, 1, "❤️"),
            ("SpO₂",           self.results.get("spo2", "—"),           "%",    1, 0, "💓"),
            ("Blood Pressure", self.results.get("blood_pressure", "—"), "mmHg", 1, 1, "🩺"),
        ]

        for name, val, unit, row, col, icon in display_map:
            card = ctk.CTkFrame(cards_frame, fg_color=C_CARD, corner_radius=14)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=24)).pack(pady=(14, 0))
            ctk.CTkLabel(card, text=name,
                         font=ctk.CTkFont(size=13, slant="italic"),
                         text_color=C_TEXT_DIM).pack()
            ctk.CTkLabel(card, text=val,
                         font=ctk.CTkFont(size=34, weight="bold"),
                         text_color=C_ACCENT_LIGHT).pack(expand=True)
            ctk.CTkLabel(card, text=unit,
                         font=ctk.CTkFont(size=12),
                         text_color=C_TEXT_DIM).pack(pady=(0, 14))

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(pady=18)

        ctk.CTkButton(btn_row, text="🖨️  Print Results",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color=C_ACCENT, hover_color="#2980b9",
                      width=200, height=44,
                      command=self._confirm_print).pack(side="left", padx=12)

        ctk.CTkButton(btn_row, text="New Session",
                      font=ctk.CTkFont(size=14),
                      fg_color="transparent", border_width=2,
                      border_color=C_ACCENT_LIGHT, text_color=C_ACCENT_LIGHT,
                      hover_color="#0d2a45",
                      width=160, height=44,
                      command=self.show_name_entry).pack(side="left", padx=12)

        self._swap_frame(f)

    # ─────────────────────────────────────────
    #  Print Confirmation Dialog
    # ─────────────────────────────────────────
    def _confirm_print(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Print Confirmation")
        dialog.configure(fg_color=C_PANEL)
        dialog.resizable(False, False)

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 420) // 2
        y = self.winfo_y() + (self.winfo_height() - 240) // 2
        dialog.geometry(f"420x240+{x}+{y}")

        dialog.wait_visibility()
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="🖨️  Print Results?",
                     font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
                     text_color=C_TEXT_MAIN).pack(pady=(28, 8))

        ctk.CTkLabel(dialog,
                     text="The results will be sent to the thermal printer.\n"
                          "Make sure there is paper loaded before confirming.",
                     font=ctk.CTkFont(size=13), text_color=C_TEXT_DIM,
                     justify="center").pack(pady=(0, 22))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack()

        def do_print():
            dialog.destroy()
            self._do_print()

        ctk.CTkButton(btn_row, text="Yes, Print",
                      fg_color=C_ACCENT, hover_color="#2980b9",
                      width=140, height=40, command=do_print).pack(side="left", padx=10)

        ctk.CTkButton(btn_row, text="No, Go Back",
                      fg_color="transparent", border_width=2,
                      border_color=C_TEXT_DIM, text_color=C_TEXT_DIM,
                      hover_color="#2b2b2b",
                      width=140, height=40, command=dialog.destroy).pack(side="left", padx=10)

    # ─────────────────────────────────────────
    #  Actual Print Execution
    # ─────────────────────────────────────────
    def _do_print(self):
        self._set_end_btn(False)
        self.sidebar_status.configure(text="🖨️ Printing…", text_color=C_ACCENT_LIGHT)

        threading.Thread(target=hw_printer.print_receipt, args=(self.patient_name, self.results)).start()

        def finish_print():
            self._set_end_btn(True)
            self.sidebar_status.configure(text="Print complete ✅", text_color=C_GREEN)
            self.after(2500, self.show_goodbye)

        self.after(2500, finish_print)

    # ─────────────────────────────────────────
    #  SCREEN 5 — Goodbye
    # ─────────────────────────────────────────
    def show_goodbye(self, reason="user"):
        self.session_active = False
        if self._inactivity_job:
            self.after_cancel(self._inactivity_job)

        self._set_end_btn(False)
        self.sidebar_status.configure(text="Session Ended", text_color=C_TEXT_DIM)
        self.progress_label.configure(text="")

        f = ctk.CTkFrame(self.main_container, fg_color=C_PANEL, corner_radius=20)
        ctk.CTkFrame(f, fg_color=C_ACCENT, height=6, corner_radius=3).pack(fill="x")

        ctk.CTkLabel(f, text="👋", font=ctk.CTkFont(size=72)).pack(pady=(60, 16))

        ctk.CTkLabel(f, text="Goodbye!",
                     font=ctk.CTkFont(family="Georgia", size=36, weight="bold"),
                     text_color=C_TEXT_MAIN).pack(pady=(0, 10))

        if reason == "inactivity":
            msg = "This session ended automatically due to inactivity.\nPlease collect your printed results if applicable."
        else:
            msg = "Thank you for using the Health Kiosk.\nPlease collect your printed results."

        ctk.CTkLabel(f, text=msg,
                     font=ctk.CTkFont(size=15), text_color=C_TEXT_DIM,
                     justify="center").pack(pady=(0, 40))

        ctk.CTkButton(f, text="Close",
                      font=ctk.CTkFont(size=14),
                      fg_color=C_RED, hover_color="#a00030",
                      width=160, height=44,
                      command=self.destroy).pack(pady=(0, 40))

        self._swap_frame(f)

        if reason == "inactivity":
            self.after(30_000, self._shutdown_pi)
        else:
            self.after(30_000, self.destroy)
    
    def _shutdown_pi(self):
        """Executes a system-level halt."""
        print("[System] Inactivity timeout reached. Shutting down Raspberry Pi...")
        subprocess.run(["sudo", "shutdown", "-h", "now"])


# ─────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("Initializing Medical Kiosk System…")
    app = MedicalKioskApp()
    app.mainloop()
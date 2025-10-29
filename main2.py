import tkinter as tk
from tkinter import ttk, messagebox
import serial, serial.tools.list_ports
import json, math, os, time
import copy

# MOD: Import SerialException for more specific error handling
from serial.serialutil import SerialException

# This should be in a separate file named `drum_patterns.py`
# For this example, it's included here.
DRUM_PARTS = ["Kick", "Snare", "HiHat", "Cymbal", "Tom1", "Tom2", "Tom3", "Perc1", "Perc2"]
PATTERN_COLS = 16
drum_pattern_array = [[0] * PATTERN_COLS for _ in range(len(DRUM_PARTS))]

# ── MetallicKnob Widget ─────────────────────────────────────
class MetallicKnob(tk.Canvas):
    def __init__(self, master, size=80, min_value=0, max_value=100, label="Knob", **kwargs):
        # Get parent background color and set canvas background to match
        parent_bg = master.cget('bg') if hasattr(master, 'cget') else "#333333"
        # Increased canvas height to accommodate label above knob
        super().__init__(master, width=size, height=size+25, bg=parent_bg, highlightthickness=0, **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = size // 2 - 12
        self.min_value = min_value
        self.max_value = max_value
        self.label_text = label
        self.value = min_value
        self.last_y = None
        self.change_callback = None
        self._draw_static_elements()
        self._draw_dynamic_elements()
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._update_needle()

    def _draw_static_elements(self):
        # Offset all knob elements down by 20 pixels to make room for label
        offset_y = 20
        
        for i in range(8):
            gray = 48 + int(170 * (i / 7))
            color = f"#{gray:02x}{gray:02x}{gray:02x}"
            self.create_oval(8 + i, 8 + i + offset_y, self.size - 8 - i, self.size - 8 - i + offset_y, fill=color, outline="")

        self.create_oval(6, 6 + offset_y, self.size - 6, self.size - 6 + offset_y, outline="#cfcfd4", width=2)
        self.create_oval(10, 10 + offset_y, self.size - 10, self.size - 10 + offset_y, outline="#949491", width=1)

        for t in range(0, 360, 18):
            rad = math.radians(t)
            x1 = self.center + (self.radius + 2) * math.sin(rad)
            y1 = self.center + (self.radius + 2) * math.cos(rad) + offset_y
            x2 = self.center + (self.radius - 4) * math.sin(rad)
            y2 = self.center + (self.radius - 4) * math.cos(rad) + offset_y
            color = "#eaeaf7" if t % 36 == 0 else "#aaa"
            self.create_line(x1, y1, x2, y2, fill=color, width=1)

        self.create_oval(18, 18 + offset_y, self.size - 18, self.size - 18 + offset_y, outline="#111", width=2)
        self.create_oval(self.center-6, self.center-6 + offset_y, self.center+6, self.center+6 + offset_y,
                        fill="#b8b9be", outline="#eaeaf7", width=1)
        self.create_oval(self.center-3, self.center-4 + offset_y, self.center+3, self.center-1 + offset_y,
                        fill="#fff", outline="", stipple="gray25")
        
        # Label positioned at top of canvas with proper margin
        self.label_master = self.create_text(self.center, 10, text=self.label_text, 
                                           font=("Segoe UI", 16, "bold"), fill="#fff")

    def _draw_dynamic_elements(self):
        offset_y = 20
        angle = self._value_to_angle(self.value)
        needle_shape = self._create_needle_shape(angle, offset_y)
        self.needle_glow = self.create_polygon(needle_shape, fill="#fc7070", outline="", width=0)
        self.needle = self.create_polygon(needle_shape, fill="#ff1212", outline="#fff", width=1)
        self.reflection = self.create_polygon(needle_shape, fill="#fff", outline="", stipple="gray12")
        # Value label with offset
        self.value_label = self.create_text(self.center, self.center + self.radius // 2 + offset_y,
                                          text=str(int(self.value)), font=("Segoe UI", 18, "bold"), fill="#ed3c3c")

    def _start_drag(self, event):
        self.last_y = event.y

    def _on_drag(self, event):
        if self.last_y is None:
            self.last_y = event.y
            return

        dy = self.last_y - event.y
        self.last_y = event.y
        sensitivity = 0.5
        new_value = self.value + (dy * sensitivity)
        self.value = max(self.min_value, min(self.max_value, new_value))
        self._update_needle()
        self.itemconfig(self.value_label, text=str(int(self.value)))
        
        # Trigger callback during drag for real-time updates
        if self.change_callback:
            self.change_callback()

    def _on_release(self, event):
        # Trigger callback on release for final value
        if self.change_callback:
            self.change_callback()

    def set_change_callback(self, callback):
        """Set callback function to be called when knob value changes"""
        self.change_callback = callback

    def _value_to_angle(self, value):
        return 180 + ((value - self.min_value) * 360.0) / (self.max_value - self.min_value)

    def _create_needle_shape(self, angle_degrees=180, offset_y=0):
        rad = math.radians(angle_degrees)
        center_y = self.center + offset_y
        tip_x = self.center + self.radius * math.sin(rad)
        tip_y = center_y - self.radius * math.cos(rad)
        base_rad_l = math.radians(angle_degrees - 8)
        base_xl = self.center + 8 * math.sin(base_rad_l)
        base_yl = center_y - 8 * math.cos(base_rad_l)
        base_rad_r = math.radians(angle_degrees + 8)
        base_xr = self.center + 8 * math.sin(base_rad_r)
        base_yr = center_y - 8 * math.cos(base_rad_r)
        return [base_xl, base_yl, tip_x, tip_y, base_xr, base_yr, self.center, center_y]

    def _update_needle(self):
        offset_y = 20
        angle = self._value_to_angle(self.value)
        shape = self._create_needle_shape(angle, offset_y)
        shape_glow = [c + (1 if i == 2 else 0) if i % 2 == 0 else c + (1 if i == 3 else 0) for i, c in enumerate(shape)]
        self.coords(self.needle_glow, *shape_glow)
        self.coords(self.needle, *shape)
        shape_reflection = [c - 1 for c in shape]
        self.coords(self.reflection, *shape_reflection)

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = max(self.min_value, min(self.max_value, value))
        self._update_needle()
        self.itemconfig(self.value_label, text=str(int(self.value)))

# ── ScrollableFrame Widget for horizontal scrolling ─────────────────
class ScrollableFrame(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, bg="#333333", highlightthickness=0, height=120)
        self.scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#333333")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(xscrollcommand=self.scrollbar.set)
        
        # Horizontal scrolling with mouse wheel when mouse is over effects area
        self._bind_mousewheel()
        
        self.canvas.pack(side="top", fill="both", expand=True)
        self.scrollbar.pack(side="bottom", fill="x")
    
    def _bind_mousewheel(self):
        """Bind mouse wheel events for horizontal scrolling"""
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        
    def _on_enter(self, event):
        """Enable horizontal mouse wheel scrolling when mouse enters"""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        
    def _on_leave(self, event):
        """Disable horizontal mouse wheel scrolling when mouse leaves"""
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
        
    def _on_mousewheel(self, event):
        # Handle horizontal mouse wheel scrolling
        if event.delta:
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self.canvas.xview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.xview_scroll(1, "units")

# ── App Constants ─────────────────────────────────────
STATE_FILE = "jam_state.json"
PRESETS_FILE = "presets.json"
DEVICE_NAME = "JamMate_BL"

BG = "#222222"
PANEL = "#333333"
FG = "#FFFFFF"
ACCENT = "#00B0B0"
GREEN = "#66ff66"  # Lighter green color
ORANGE = "#FFA500"
RED = "#FF4444"

def set_dark_theme(root: tk.Tk):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    
    style.configure("TFrame", background=PANEL)
    style.configure("TLabel", background=PANEL, foreground=FG, font=("Segoe UI", 14))
    style.configure("TButton", background=ACCENT, foreground="#000",
                   font=("Segoe UI", 14), padding=6, relief="flat")
    style.map("TButton", background=[("active", "#009090"), ("disabled", "#555")])
    
    style.configure("TCheckbutton", background=PANEL, foreground=FG,
                   font=("Segoe UI", 14))
    
    style.configure("Large.TCombobox",
                   font=("Segoe UI", 16),
                   fieldbackground="#444",
                   selectbackground=ACCENT,
                   foreground=FG,
                   padding=(6, 4),
                   relief="flat")
    style.map("Large.TCombobox",
              fieldbackground=[("readonly", "#444"), ("focus", "#555")],
              selectbackground=[("readonly", ACCENT)],
              foreground=[("readonly", FG)])

    root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 14))
    root.option_add("*TCombobox*Listbox.background", "#444")
    root.option_add("*TCombobox*Listbox.foreground", FG)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "#000")

class GuitarFXApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JamMate_BL Effects Controller")
        # FIXED: Changed to proper phone portrait aspect ratio
        self.geometry("390x844")  # iPhone 12 Pro dimensions for realistic phone size
        set_dark_theme(self)
        
        self.pending_send = {}
        
        # Create all effects including special ones
        self.all_effects = self._create_all_effects()
        
        self.presets = self._load_presets()
        self.DrumPatEnab = 0
        self.serial_port = None
        self.bt_connected = False
        self.is_connecting = False
        self.connection_check_job = None
        self.tab_state = self._load_state()
        self.current_effect = None
        self.effect_widgets = {}
        self.bypass_enabled = False
        
        self.style_options = ["Rock", "Blues", "Jazz", "Shuffle", "Pop", "Metal", "Latin", "R&B", "Country", "Funk"]
        self.fill_options = ["None", "x1", "x4", "x12", "x16"]
        self.number_options = [str(i) for i in range(1, 11)]
        
        # Create UI layout
        self._create_topbar()
        self._create_preset_bar()
        self._create_effects_bar()
        self._create_main_area()
        self._create_statusbar()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Select first effect by default
        if self.all_effects:
            self._select_effect(0)

    def _create_all_effects(self):
        """Create all effects including regular effects and special modules"""
        all_effects = []
        
        # Load regular effects from config or create defaults
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                regular_effects = cfg.get("tabs", [])[:16]  # Limit to 16 regular effects
                
                # Ensure all effects have 'type' key
                for effect in regular_effects:
                    effect_copy = copy.deepcopy(effect)
                    if 'type' not in effect_copy:
                        effect_copy['type'] = 'effect'
                    all_effects.append(effect_copy)
                    
            except:
                regular_effects = []
        
        # If no config or failed to load, create default effects
        if not all_effects:
            all_effects = [
                {"title": f"Effect {i+1}", "short_name": f"FX{i+1:02d}", "type": "effect",
                 "params": {"knobs": ["Gain", "Tone", "Level"], "checkbox": True, "dropdowns": []}}
                for i in range(16)
            ]
        
        # Add special modules
        special_effects = [
            {"title": "Drum", "short_name": "DRUM", "type": "drum",
             "params": {"knobs": ["Level"], "checkbox": True, "dropdowns": ["style", "number", "fill"]}},
            {"title": "Metronome", "short_name": "METR", "type": "metronome",
             "params": {"knobs": ["Volume", "BPM"], "checkbox": True, "dropdowns": ["sound"]}},
            {"title": "Looper", "short_name": "LOOP", "type": "looper",
             "params": {"knobs": ["Mix", "Feedback"], "checkbox": True, "dropdowns": ["mode"]}},
            {"title": "Tuner", "short_name": "TUNR", "type": "tuner",
             "params": {"knobs": ["Sensitivity"], "checkbox": True, "dropdowns": ["reference"]}},
            {"title": "Setup", "short_name": "SETP", "type": "setup",
             "params": {"knobs": [], "checkbox": False, "dropdowns": ["input_gain", "output_mode"]}}  # FIXED: No enable checkbox for setup
        ]
        
        all_effects.extend(special_effects)
        return all_effects

    def _create_topbar(self):
        # Increased top bar height for knob labels and alignment
        bar = tk.Frame(self, bg=PANEL, height=180)
        bar.pack(fill="x", padx=5, pady=3)
        bar.pack_propagate(False)
        
        # Left - Connection status and single toggle button
        conn_frame = tk.Frame(bar, bg=PANEL)
        conn_frame.pack(side="left", padx=8)
        
        self.status_led = tk.Canvas(conn_frame, width=20, height=20, bg=PANEL, highlightthickness=0)
        self.status_led.create_oval(2, 2, 18, 18, fill="#C33", tags="led")
        self.status_led.pack()
        
        tk.Label(conn_frame, text=DEVICE_NAME, fg=ACCENT, bg=PANEL,
                font=("Segoe UI", 10)).pack()
        
        self.status_text = tk.Label(conn_frame, text="Disconnected", fg="#C33", bg=PANEL,
                                   font=("Segoe UI", 8))
        self.status_text.pack()
        
        self.btn_connect_toggle = tk.Button(conn_frame, text="Connect", bg=ACCENT, fg="#000",
                                           font=("Segoe UI", 12),
                                           command=self._toggle_connection, width=8, height=3)
        self.btn_connect_toggle.pack(pady=3)
        
        # Center - Master knobs
        master_frame = tk.Frame(bar, bg=PANEL)
        master_frame.pack(side="left", expand=True, padx=15)
        
        # Align knobs at bottom of top bar
        knobs_container = tk.Frame(master_frame, bg=PANEL)
        knobs_container.pack(side="bottom", pady=10)
        
        # Create master knobs horizontally
        self.perm_knobs = {}
        labels = ["Master", "BPM", "BL_Vol"]
        
        for i, label in enumerate(labels):
            default_val = 127 if label == "BPM" else 50
            max_val = 255 if label == "BPM" else 100
            
            knob = MetallicKnob(knobs_container,
                              size=100,
                              min_value=0,
                              max_value=max_val,
                              label=label)
            knob.set_value(default_val)
            knob.pack(side="left", padx=10, pady=3)
            self.perm_knobs[label] = knob
        
        # Right - Bypass button
        bypass_frame = tk.Frame(bar, bg=PANEL)
        bypass_frame.pack(side="right", padx=8)
        
        self.bypass_btn = tk.Button(bypass_frame, text="BYPASS", bg="#666", fg=FG,
                                   font=("Segoe UI", 12),
                                   command=self._toggle_bypass, width=8, height=3)
        self.bypass_btn.pack()

    def _create_preset_bar(self):
        # Preset bar with larger fonts
        preset_bar = tk.Frame(self, bg=PANEL, height=80)
        preset_bar.pack(fill="x", padx=5, pady=2)
        preset_bar.pack_propagate(False)
        
        # Center the preset controls
        preset_container = tk.Frame(preset_bar, bg=PANEL)
        preset_container.pack(expand=True)
        
        # Bank dropdown
        bank_items = ["Clean", "Crunch", "Overdrive", "Distortion", "Modulated", "Custom1", "Custom2"]
        self.bank_var = tk.StringVar(value=bank_items[0])
        
        tk.Label(preset_container, text="Bank:", fg=FG, bg=PANEL, 
                font=("Segoe UI", 16)).pack(side="left", padx=5)
        bank_combo = ttk.Combobox(preset_container, textvariable=self.bank_var, values=bank_items,
                                 state="readonly", width=12, font=("Segoe UI", 16))
        bank_combo.pack(side="left", padx=3)
        
        # Num dropdown
        num_items = ["1", "2", "3", "4", "5"]
        self.num_var = tk.StringVar(value=num_items[0])
        
        tk.Label(preset_container, text="Num:", fg=FG, bg=PANEL, 
                font=("Segoe UI", 16)).pack(side="left", padx=(10, 5))
        num_combo = ttk.Combobox(preset_container, textvariable=self.num_var, values=num_items,
                                state="readonly", width=8, font=("Segoe UI", 16))
        num_combo.pack(side="left", padx=3)
        
        # Update button
        update_btn = tk.Button(preset_container, text="Update Preset", command=self._on_update_preset,
                              bg=ACCENT, fg="#000", font=("Segoe UI", 16))
        update_btn.pack(side="left", padx=(15, 5))
        
        bank_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)
        num_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)

    def _create_effects_bar(self):
        # Effects bar with returned effect rect size
        effects_bar = tk.Frame(self, bg=PANEL, height=130)
        effects_bar.pack(fill="x", padx=5, pady=2)
        effects_bar.pack_propagate(False)
        
        # Adjusted scrollable frame
        scroll_container = tk.Frame(effects_bar, bg=PANEL)
        scroll_container.pack(fill="both", expand=True, padx=3, pady=3)
        
        self.effects_scroll = ScrollableFrame(scroll_container)
        self.effects_scroll.pack(fill="both", expand=True)
        
        self.effect_buttons = []
        self._create_effect_buttons()

    def _create_effect_buttons(self):
        for btn in self.effect_buttons:
            btn.destroy()
        self.effect_buttons = []
        
        # Create effect buttons with enable checkboxes
        for i, effect_info in enumerate(self.all_effects):
            # Create effect container
            effect_container = tk.Frame(self.effects_scroll.scrollable_frame, bg="#444", relief="ridge", bd=1)
            effect_container.pack(side="left", padx=2, pady=3, fill="y")
            
            # Effect button
            btn = tk.Button(effect_container,
                           text=effect_info["title"],
                           width=12, height=3,
                           bg="#555", fg=FG,
                           font=("Segoe UI", 12),
                           relief="raised", bd=1,
                           command=lambda idx=i: self._select_effect(idx))
            btn.pack(pady=2, padx=2)
            self.effect_buttons.append(btn)
            
            # FIXED: Only add enable checkbox if effect has checkbox parameter set to True
            params = effect_info.get("params", {})
            if params.get("checkbox", True):  # Default to True, but respect False for setup
                enable_var = tk.IntVar(value=1)
                chk = ttk.Checkbutton(effect_container, text="Enable", variable=enable_var)
                chk.pack(pady=1)
                
                # Store the enable variable
                if not hasattr(self, 'effect_enables'):
                    self.effect_enables = {}
                self.effect_enables[i] = enable_var
                
                # Proper binding for enable change
                enable_var.trace_add("write", lambda *_, idx=i: self._on_effect_enable_changed(idx))

    def _create_main_area(self):
        # Main working area for current effect controls
        self.main_area = tk.Frame(self, bg=PANEL, relief="ridge", bd=2)
        self.main_area.pack(fill="both", expand=True, padx=10, pady=3)
        
        # Title for current effect
        self.current_title = tk.Label(self.main_area, text="Select an Effect", fg=ACCENT, bg=PANEL,
                                     font=("Segoe UI", 18))
        self.current_title.pack(pady=15)
        
        # Scrollable content area for effect controls
        self.content_canvas = tk.Canvas(self.main_area, bg=PANEL, highlightthickness=0)
        self.content_scrollbar = ttk.Scrollbar(self.main_area, orient="vertical", command=self.content_canvas.yview)
        self.scrollable_content = tk.Frame(self.content_canvas, bg=PANEL)
        
        self.scrollable_content.bind(
            "<Configure>",
            lambda e: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        )
        
        self.content_canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        
        # Enable mouse wheel scrolling for main area
        self.content_canvas.bind("<MouseWheel>", self._on_main_mousewheel)
        self.content_canvas.bind("<Button-4>", self._on_main_mousewheel)
        self.content_canvas.bind("<Button-5>", self._on_main_mousewheel)
        
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_scrollbar.pack(side="right", fill="y")

    def _on_main_mousewheel(self, event):
        if event.delta:
            self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif event.num == 4:
            self.content_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.content_canvas.yview_scroll(1, "units")

    def _select_effect(self, effect_idx):
        self.current_effect = effect_idx
        self._update_effect_buttons()
        
        # Clear current content
        for widget in self.scrollable_content.winfo_children():
            widget.destroy()
        
        effect = self.all_effects[effect_idx]
        self.current_title.config(text=effect["title"])
        
        # Build content based on effect type
        if effect["type"] == "drum":
            self._build_drum_content()
        elif effect["type"] == "metronome":
            self._build_metronome_content()
        elif effect["type"] == "looper":
            self._build_looper_content()
        elif effect["type"] == "tuner":
            self._build_tuner_content()
        elif effect["type"] == "setup":
            self._build_setup_content()
        else:
            self._build_regular_effect_content(effect)

    def _build_regular_effect_content(self, effect):
        """Build content for regular guitar effects"""
        # Dropdowns if any
        params = effect.get("params", {})
        dropdown_names = params.get("dropdowns", [])
        
        if dropdown_names:
            dd_frame = tk.Frame(self.scrollable_content, bg=PANEL)
            dd_frame.pack(pady=12)
            
            for dropdown_name in dropdown_names:
                # Create dropdown with sample values
                sample_values = ["Option 1", "Option 2", "Option 3", "Option 4"]
                var = tk.StringVar(value=sample_values[0])
                
                tk.Label(dd_frame, text=f"{dropdown_name.title()}:", fg=FG, bg=PANEL,
                        font=("Segoe UI", 14)).pack(pady=3)
                
                combo = ttk.Combobox(dd_frame, textvariable=var,
                                   values=sample_values, state="readonly", width=30,
                                   style="Large.TCombobox")
                combo.pack(pady=3)
        
        # Effect knobs
        knob_names = params.get("knobs", [])
        if knob_names:
            knobs_frame = tk.Frame(self.scrollable_content, bg=PANEL)
            knobs_frame.pack(pady=20)
            
            # Arrange knobs in rows of 3 with tighter spacing
            for i, knob_name in enumerate(knob_names):
                knob = MetallicKnob(knobs_frame,
                                  size=120,
                                  min_value=0,
                                  max_value=100,
                                  label=knob_name)
                knob.set_value(50)
                
                row = i // 3
                col = i % 3
                knob.grid(row=row, column=col, padx=20, pady=15)

    def _build_drum_content(self):
        """Build drum sequencer content"""
        # Level knob
        level_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        level_frame.pack(pady=15)
        
        self.drum_level_knob = MetallicKnob(level_frame, size=120, min_value=0, max_value=255, label="Level")
        self.drum_level_knob.set_value(127)
        self.drum_level_knob.pack()
        
        # Set callback for drum level knob to trigger sending data
        self.drum_level_knob.set_change_callback(lambda: self._send_drum_data(trigger="Level"))
        
        # Drum controls with tighter spacing
        controls_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        controls_frame.pack(pady=15, padx=40)
        
        # Style dropdown
        self.drum_style_var = tk.StringVar(value=self.style_options[0])
        tk.Label(controls_frame, text="Style:", fg=FG, bg=PANEL, font=("Segoe UI", 14)).pack(pady=3)
        style_dd = ttk.Combobox(controls_frame, textvariable=self.drum_style_var,
                               values=self.style_options, state="readonly", width=30,
                               style="Large.TCombobox")
        style_dd.pack(pady=3)
        
        # Number dropdown
        self.drum_number_var = tk.StringVar(value=self.number_options[0])
        tk.Label(controls_frame, text="Number:", fg=FG, bg=PANEL, font=("Segoe UI", 14)).pack(pady=3)
        number_dd = ttk.Combobox(controls_frame, textvariable=self.drum_number_var,
                                values=self.number_options, state="readonly", width=30,
                                style="Large.TCombobox")
        number_dd.pack(pady=3)
        
        # Fill dropdown
        self.drum_fill_var = tk.StringVar(value=self.fill_options[0])
        tk.Label(controls_frame, text="Fill:", fg=FG, bg=PANEL, font=("Segoe UI", 14)).pack(pady=3)
        fill_dd = ttk.Combobox(controls_frame, textvariable=self.drum_fill_var,
                              values=self.fill_options, state="readonly", width=30,
                              style="Large.TCombobox")
        fill_dd.pack(pady=3)
        
        # Drum pattern grid
        pattern_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        pattern_frame.pack(pady=20)
        
        tk.Label(pattern_frame, text="Drum Pattern", fg=ACCENT, bg=PANEL,
                font=("Segoe UI", 16)).pack(pady=8)
        
        self._create_drum_pattern_grid(pattern_frame)
        
        # Bindings
        number_dd.bind("<<ComboboxSelected>>", lambda e: self._send_drum_data(trigger="Number"))
        style_dd.bind("<<ComboboxSelected>>", lambda e: self._handle_drum_style_change(trigger="Style"))
        fill_dd.bind("<<ComboboxSelected>>", lambda e: self._handle_drum_style_change(trigger="Fill"))

    def _create_drum_pattern_grid(self, parent):
        grid_frame = tk.Frame(parent, bg=PANEL)
        grid_frame.pack()
        
        # Create grid for first 3 drum parts (Kick, Snare, HiHat) and 16 beats
        parts_to_show = ["Kick", "Snare", "HiHat"]
        
        # Beat numbers header
        for col in range(16):
            lbl = tk.Label(grid_frame, text=str(col+1), bg="#555", fg="#fff",
                          font=("Segoe UI", 10), width=3, height=1)
            lbl.grid(row=0, column=col+1, padx=1, pady=1)
        
        # Drum pattern grid
        self.drum_grid = []
        for row, part in enumerate(parts_to_show):
            # Part label
            tk.Label(grid_frame, text=part, bg="#666", fg="#eee",
                    font=("Segoe UI", 12), width=8, height=2).grid(row=row+1, column=0, padx=2, pady=1)
            
            row_buttons = []
            for col in range(16):
                # Get actual drum part index
                part_idx = DRUM_PARTS.index(part) if part in DRUM_PARTS else row
                state = drum_pattern_array[part_idx][col] if part_idx < len(drum_pattern_array) else 0
                
                btn = tk.Button(grid_frame, text="", width=3, height=1,
                              bg="#0f0" if state else "#333",
                              command=lambda r=part_idx, c=col: self._toggle_drum_beat(r, c))
                btn.grid(row=row+1, column=col+1, padx=1, pady=1)
                row_buttons.append(btn)
            self.drum_grid.append(row_buttons)

    def _toggle_drum_beat(self, row, col):
        if row < len(drum_pattern_array) and col < len(drum_pattern_array[row]):
            drum_pattern_array[row][col] = 1 - drum_pattern_array[row][col]
            
            # Update button color
            if row < len(self.drum_grid) and col < len(self.drum_grid[row]):
                color = "#0f0" if drum_pattern_array[row][col] else "#333"
                self.drum_grid[row][col].config(bg=color)
            
            # Send pattern data
            self.DrumPatEnab = 1
            self._send_drmp_pattern()

    def _build_metronome_content(self):
        """Build metronome content"""
        tk.Label(self.scrollable_content, text="Metronome Controls", fg=FG, bg=PANEL,
                font=("Segoe UI", 16)).pack(pady=40)
        
        knobs_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        knobs_frame.pack(pady=15)
        
        vol_knob = MetallicKnob(knobs_frame, size=120, min_value=0, max_value=100, label="Volume")
        vol_knob.pack(side="left", padx=25)
        vol_knob.set_value(75)
        
        bpm_knob = MetallicKnob(knobs_frame, size=120, min_value=60, max_value=200, label="BPM")
        bpm_knob.pack(side="left", padx=25)
        bpm_knob.set_value(120)

    def _build_looper_content(self):
        """Build looper content"""
        tk.Label(self.scrollable_content, text="Looper Controls", fg=FG, bg=PANEL,
                font=("Segoe UI", 16)).pack(pady=40)
        
        controls_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        controls_frame.pack(pady=15)
        
        record_btn = tk.Button(controls_frame, text="RECORD", bg=RED, fg=FG,
                              font=("Segoe UI", 14), width=12, height=2)
        record_btn.pack(pady=8)
        
        play_btn = tk.Button(controls_frame, text="PLAY", bg=GREEN, fg="#000",
                            font=("Segoe UI", 14), width=12, height=2)
        play_btn.pack(pady=8)
        
        stop_btn = tk.Button(controls_frame, text="STOP", bg="#666", fg=FG,
                            font=("Segoe UI", 14), width=12, height=2)
        stop_btn.pack(pady=8)

    def _build_tuner_content(self):
        """Build tuner content"""
        tk.Label(self.scrollable_content, text="Tuner", fg=FG, bg=PANEL,
                font=("Segoe UI", 16)).pack(pady=40)
        
        tuner_display = tk.Frame(self.scrollable_content, bg="#000", width=400, height=200)
        tuner_display.pack(pady=15)
        tuner_display.pack_propagate(False)
        
        tk.Label(tuner_display, text="E", fg=GREEN, bg="#000",
                font=("Segoe UI", 48)).pack(expand=True)

    def _build_setup_content(self):
        """Build setup content"""
        tk.Label(self.scrollable_content, text="System Setup", fg=FG, bg=PANEL,
                font=("Segoe UI", 16)).pack(pady=40)
        
        setup_frame = tk.Frame(self.scrollable_content, bg=PANEL)
        setup_frame.pack(pady=15, padx=40)
        
        # Input gain
        tk.Label(setup_frame, text="Input Gain:", fg=FG, bg=PANEL, font=("Segoe UI", 14)).pack(pady=3)
        gain_combo = ttk.Combobox(setup_frame, values=["Low", "Medium", "High"], state="readonly", width=30)
        gain_combo.set("Medium")
        gain_combo.pack(pady=3)
        
        # Output mode
        tk.Label(setup_frame, text="Output Mode:", fg=FG, bg=PANEL, font=("Segoe UI", 14)).pack(pady=3)
        output_combo = ttk.Combobox(setup_frame, values=["Stereo", "Mono", "Headphones"], state="readonly", width=30)
        output_combo.set("Stereo")
        output_combo.pack(pady=3)

    def _update_effect_buttons(self):
        """Update effect button colors based on selection and enable state"""
        for i, btn in enumerate(self.effect_buttons):
            if i == self.current_effect:
                btn.config(bg=ACCENT, fg="#000")  # Selected effect
            elif hasattr(self, 'effect_enables') and i in self.effect_enables and self.effect_enables[i].get():
                btn.config(bg=GREEN, fg="#000")  # Enabled effect with lighter green
            else:
                btn.config(bg="#555", fg=FG)  # Disabled/normal effect

    def _on_effect_enable_changed(self, effect_idx):
        """Handle effect enable/disable with proper color update"""
        self._update_effect_buttons()  # This ensures color changes happen
        effect_name = self.all_effects[effect_idx]["title"]
        enabled = self.effect_enables[effect_idx].get()
        status = "ENABLED" if enabled else "DISABLED"
        self._update_status(f"{effect_name}: {status}")

    def _toggle_bypass(self):
        """Toggle global bypass"""
        self.bypass_enabled = not self.bypass_enabled
        if self.bypass_enabled:
            self.bypass_btn.config(bg=RED, text="BYPASSED")
        else:
            self.bypass_btn.config(bg="#666", text="BYPASS")
        
        status = "BYPASSED" if self.bypass_enabled else "ACTIVE"
        self._update_status(f"Global bypass: {status}")

    def _create_statusbar(self):
        self.status_bar = tk.Frame(self, bg=PANEL, height=25)
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)
        
        self.status_message = tk.StringVar(value="Ready")
        tk.Label(self.status_bar, textvariable=self.status_message,
                fg=FG, bg=PANEL, font=("Segoe UI", 10)).pack(side="left", padx=8, pady=2)

    def _update_status(self, message):
        if self.winfo_exists():
            self.status_message.set(message)
            print(f"STATUS: {message}")

    # Single toggle connection method
    def _toggle_connection(self):
        if self.bt_connected:
            self._disconnect()
        else:
            self._connect()

    def _find_port(self):
        for p in serial.tools.list_ports.comports():
            if p.description and DEVICE_NAME.upper() in p.description.upper():
                return p.device
        return None

    def _connect(self):
        if self.is_connecting:
            return
        
        self.is_connecting = True
        self.status_led.itemconfig("led", fill=ORANGE)
        self.status_text.config(text="Connecting...", fg=ORANGE)
        self.btn_connect_toggle.config(text="Connecting...", state="disabled")
        self.after(100, self._attempt_connection)

    def _attempt_connection(self):
        try:
            port = self._find_port()
            if not port:
                self._simulate_connection()  # Demo mode
                return
            
            self.serial_port = serial.Serial(port, 115200, timeout=1)
            self.bt_connected = True
            self.is_connecting = False
            
            self.status_led.itemconfig("led", fill=GREEN)
            self.status_text.config(text="Connected", fg=GREEN)
            self.btn_connect_toggle.config(text="Disconnect", state="normal")
            
            self._update_status(f"Connected to {DEVICE_NAME}")
            
        except Exception as e:
            self._simulate_connection()  # Fallback to demo mode

    def _simulate_connection(self):
        """Demo mode for testing UI"""
        self.bt_connected = True
        self.is_connecting = False
        
        self.status_led.itemconfig("led", fill=GREEN)
        self.status_text.config(text="Demo Mode", fg=GREEN)
        self.btn_connect_toggle.config(text="Disconnect", state="normal")
        
        self._update_status("Demo Mode - UI Functional")

    def _disconnect(self):
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None
        
        self.bt_connected = False
        self.is_connecting = False
        
        if self.winfo_exists():
            self.status_led.itemconfig("led", fill="#C33")
            self.status_text.config(text="Disconnected", fg="#C33")
            self.btn_connect_toggle.config(text="Connect", state="normal")
            self._update_status("Disconnected")

    # Communication methods (simplified for demo)
    def _send_17_byte_packet(self, data):
        if not self.bt_connected:
            self._update_status("Send Failed: Not connected")
            return
        
        packet_name = data[:4].decode('ascii', errors='ignore')
        self._update_status(f"Sent {packet_name} packet")

    def _send_drum_data(self, trigger="unknown"):
        # Show current drum level knob value in status
        level_value = int(self.drum_level_knob.get_value()) if hasattr(self, 'drum_level_knob') else 127
        self._update_status(f"Drum send: {trigger} - Level: {level_value}")
        
    def _send_drmp_pattern(self):
        self._update_status("DRMP pattern sent")

    def _handle_drum_style_change(self, trigger="unknown"):
        self.DrumPatEnab = 0
        self._send_drum_data(trigger=trigger)

    # Preset management methods
    def _on_preset_changed(self, event=None):
        bank = self.bank_var.get()
        num = self.num_var.get()
        preset_key = f"{bank}_{num}"
        preset = self.presets.get(preset_key, None)
        if preset:
            self._apply_preset(preset)
            self._update_status(f"Loaded preset: {preset_key}")
        else:
            self._update_status(f"No preset found for: {preset_key}")

    def _on_update_preset(self):
        bank = self.bank_var.get()
        num = self.num_var.get()
        preset_key = f"{bank}_{num}"
        preset_data = self._collect_current_state()
        self.presets[preset_key] = preset_data
        self.presets["last_used"] = preset_key
        self._save_presets()
        self._update_status(f"Preset {preset_key} updated")

    def _collect_current_state(self):
        # Simplified state collection for demo
        state = {}
        state["perm_knobs"] = {
            "Master": int(self.perm_knobs["Master"].get_value()),
            "BPM": int(self.perm_knobs["BPM"].get_value()),
            "BL_Vol": int(self.perm_knobs["BL_Vol"].get_value())
        }
        return state

    def _apply_preset(self, preset):
        # Simplified preset application for demo
        perm = preset.get("perm_knobs", {})
        if "Master" in self.perm_knobs: 
            self.perm_knobs["Master"].set_value(perm.get("Master", 50))
        if "BPM" in self.perm_knobs: 
            self.perm_knobs["BPM"].set_value(perm.get("BPM", 127))
        if "BL_Vol" in self.perm_knobs: 
            self.perm_knobs["BL_Vol"].set_value(perm.get("BL_Vol", 50))

    # State management methods
    def _load_presets(self):
        if not os.path.exists(PRESETS_FILE):
            return {"last_used": None}
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"last_used": None}

    def _save_presets(self):
        try:
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            print(f"Error saving presets: {e}")

    def _load_state(self):
        if not os.path.exists(STATE_FILE):
            return {}
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _save_state(self):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tab_state, f, indent=2)
        except Exception as e:
            print("Could not save state:", e)

    def _on_close(self):
        self._save_state()
        self._disconnect()
        self.destroy()

if __name__ == "__main__":
    app = GuitarFXApp()
    if app.winfo_exists():
        app.mainloop()

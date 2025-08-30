import tkinter as tk
from tkinter import ttk, messagebox
import json
import asyncio
import threading
import time
import websockets
import numpy as np

# Próba importu ikpy z obsługą błędów
try:
    import ikpy.chain
    from ikpy.link import DHLink, OriginLink
    IKPY_AVAILABLE = True
except ImportError:
    IKPY_AVAILABLE = False

PI = np.pi

# Lista obsługiwanych komend i ich parametry
COMMANDS = {
    "ping": {},
    "home": {"ms": 800, "led": 128, "rgb": {"r": 0, "g": 255, "b": 0}},
    "led": {"val": 64},
    "rgb": {"r": 255, "g": 0, "b": 0},
    "freq": {"hz": 50.0},
    "config": {"ch": 0, "min_us": 1000, "max_us": 2000, "offset_us": 0, "invert": False},
    "frame": {"deg": [10, -20, 15, -5, 30], "ms": 1000, "led": 200, "rgb": {"r": 0, "g": 0, "b": 255}},
    "status": {},
    "rt_frame": {"deg": [20, -10, 0, 15, -25], "ms": 100},
    "trajectory": {"points": [
        {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 255, "g": 0, "b": 0}},
        {"deg": [30, -20, 15, -10, 25], "ms": 500, "rgb": {"r": 0, "g": 255, "b": 0}},
        {"deg": [0, 0, 0, 0, 0], "ms": 300, "rgb": {"r": 0, "g": 0, "b": 255}}
    ]},
    "stream_start": {"freq": 10},
    "stream_stop": {},
}

HOST = "192.168.4.1"
PORT = 81

class RobotKinematics:
    """Klasa do obsługi kinematyki odwrotnej robota"""
    def __init__(self):
        if not IKPY_AVAILABLE:
            self.chain = None
            return
            
        # Parametry robota
        self.L1, self.L2, self.L3, self.L4, self.L5 = 1, 1, 1, 1, 1
        self.alpha1, self.alpha2, self.alpha3, self.alpha4, self.alpha5 = PI/2, 0, -PI/2, 0, PI/2
        self.lam1, self.lam2, self.lam3, self.lam4, self.lam5 = self.L1, self.L2, 0, 0, self.L3
        self.del1, self.del2, self.del3, self.del4, self.del5 = self.L1, 0, self.L3, self.L4, 0
        
        # Definicja łańcucha kinematycznego
        try:
            self.chain = ikpy.chain.Chain([
                OriginLink(),
                DHLink(name="joint_1", d=self.del1, a=self.lam1, alpha=self.alpha1, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_2", d=self.del2, a=self.lam2, alpha=self.alpha2, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_3", d=self.del3, a=self.lam3, alpha=self.alpha3, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_4", d=self.del4, a=self.lam4, alpha=self.alpha4, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_5", d=self.del5, a=self.lam5, alpha=self.alpha5, bounds=(-PI/2, PI/2))
            ])
        except Exception as e:
            print(f"Błąd inicjalizacji łańcucha kinematycznego: {e}")
            self.chain = None
    
    def calculate_inverse_kinematics(self, target_position):
        """Oblicza kinematykę odwrotną dla zadanej pozycji"""
        if not self.chain:
            raise Exception("Łańcuch kinematyczny nie został zainicjalizowany")
        
        initial_position = [0, 0, 0, 0, 0, 0]  # OriginLink + 5 jointów
        
        joint_angles = self.chain.inverse_kinematics(
            target_position, 
            initial_position=initial_position
        )
        
        # Konwersja na stopnie i zwrócenie tylko kątów przegubów (bez OriginLink)
        joint_angles_deg = [np.degrees(angle) for angle in joint_angles[1:]]
        
        # Weryfikacja rozwiązania
        result_position = self.chain.forward_kinematics(joint_angles)
        error = np.linalg.norm(np.array(target_position) - result_position[:3, 3])
        
        return joint_angles_deg, error, result_position[:3, 3]

class WebSocketClient:
    def __init__(self, host, port, output_callback, connection_callback):
        self.host = host
        self.port = port
        self.output_callback = output_callback
        self.connection_callback = connection_callback
        self.loop = asyncio.new_event_loop()
        self.ws = None
        self.connected = False
        self.last_ping_time = 0
        self.ping_running = False

    def send_command(self, cmd, params):
        threading.Thread(target=self._send_command_thread, args=(cmd, params)).start()

    def send_ping(self):
        """Wysyła ping bez wyświetlania w logach"""
        if not self.ping_running:
            self.ping_running = True
            threading.Thread(target=self._ping_thread).start()

    def _ping_thread(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._send_ping())
        self.ping_running = False

    def _send_command_thread(self, cmd, params):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._send(cmd, params))

    async def _send_ping(self):
        """Wysyła ping bez logowania odpowiedzi"""
        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri, ping_timeout=3, close_timeout=3) as ws:
                self.ws = ws
                if not self.connected:
                    self.connected = True
                    self.connection_callback(True)
                
                ping_cmd = {"cmd": "ping"}
                await ws.send(json.dumps(ping_cmd, separators=(",", ":")))
                
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                self.last_ping_time = time.time()
                
                try:
                    response_data = json.loads(response)
                    if response_data.get("pong") == True:
                        pass
                except:
                    pass
                
        except Exception as e:
            if self.connected:
                self.connected = False
                self.connection_callback(False)

    async def _send(self, cmd, params):
        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri, ping_timeout=5, close_timeout=5) as ws:
                self.ws = ws
                if not self.connected:
                    self.connected = True
                    self.connection_callback(True)
                
                try:
                    welcome = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    self.output_callback(f"Wiadomość powitalna: {welcome}")
                except asyncio.TimeoutError:
                    pass
                
                if params:
                    obj = {"cmd": cmd}
                    obj.update(params)
                else:
                    obj = {"cmd": cmd}
                await ws.send(json.dumps(obj, separators=(",", ":")))
                
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    self.output_callback(f"Odpowiedź: {response}")
                except asyncio.TimeoutError:
                    self.output_callback("Brak odpowiedzi (timeout)")
                    
        except Exception as e:
            if self.connected:
                self.connected = False
                self.connection_callback(False)
            self.output_callback(f"Błąd połączenia: {e}")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ESP32 RoboArm - Klient WebSocket + Kinematyka Odwrotna")
        self.geometry("900x800")
        self.client = WebSocketClient(HOST, PORT, self.show_output, self.update_connection_status)
        self.robot_kinematics = RobotKinematics()
        self.param_vars = {}
        self.ping_timer = None
        self.create_widgets()
        self.start_ping_timer()

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Connection status frame
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill="x", pady=(0, 10))
        
        # Connection indicator
        self.connection_label = ttk.Label(status_frame, text="🔴 ROZŁĄCZONY", foreground="red", font=("TkDefaultFont", 12, "bold"))
        self.connection_label.pack(side="left")
        
        # Connection details
        self.connection_details = ttk.Label(status_frame, text=f"ESP32: {HOST}:{PORT}", foreground="gray")
        self.connection_details.pack(side="left", padx=(20, 0))
        
        # Manual ping button
        self.ping_btn = ttk.Button(status_frame, text="🏓 Test Ping", command=self.manual_ping)
        self.ping_btn.pack(side="right")
        
        # Last ping info
        self.last_ping_label = ttk.Label(status_frame, text="Auto-ping: co 10s", foreground="gray", font=("TkDefaultFont", 9))
        self.last_ping_label.pack(side="right", padx=(0, 10))

        # ========== NOWA SEKCJA - KINEMATYKA ODWROTNA ==========
        # Inverse kinematics frame
        ik_frame = ttk.LabelFrame(main_frame, text="🤖 Kinematyka Odwrotna - Sterowanie Pozycją", padding=10)
        ik_frame.pack(fill="x", pady=(0, 10))
        
        if not IKPY_AVAILABLE:
            error_label = ttk.Label(ik_frame, text="⚠️ Moduł ikpy nie jest dostępny. Zainstaluj: pip install ikpy", 
                                  foreground="red", font=("TkDefaultFont", 10, "bold"))
            error_label.pack(pady=10)
        else:
            # Target position inputs
            target_frame = ttk.Frame(ik_frame)
            target_frame.pack(fill="x", pady=(0, 10))
            
            ttk.Label(target_frame, text="Pozycja docelowa [m]:", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
            
            ttk.Label(target_frame, text="X:").grid(row=1, column=0, padx=(0, 5))
            self.target_x = tk.StringVar(value="0.5")
            ttk.Entry(target_frame, textvariable=self.target_x, width=10).grid(row=1, column=1, padx=(0, 20))
            
            ttk.Label(target_frame, text="Y:").grid(row=1, column=2, padx=(0, 5))
            self.target_y = tk.StringVar(value="0.2")
            ttk.Entry(target_frame, textvariable=self.target_y, width=10).grid(row=1, column=3, padx=(0, 20))
            
            ttk.Label(target_frame, text="Z:").grid(row=1, column=4, padx=(0, 5))
            self.target_z = tk.StringVar(value="0.8")
            ttk.Entry(target_frame, textvariable=self.target_z, width=10).grid(row=1, column=5)
            
            # Calculate and send buttons
            button_frame = ttk.Frame(ik_frame)
            button_frame.pack(fill="x", pady=(10, 0))
            
            self.calc_ik_btn = ttk.Button(button_frame, text="🧮 Oblicz Kąty", command=self.calculate_inverse_kinematics)
            self.calc_ik_btn.pack(side="left", padx=(0, 10))
            
            self.send_ik_btn = ttk.Button(button_frame, text="🚀 Wyślij na Robot", command=self.send_inverse_kinematics, state="disabled")
            self.send_ik_btn.pack(side="left", padx=(0, 10))
            
            # Results display
            self.ik_result_label = ttk.Label(button_frame, text="Oblicz kąty aby zobaczyć wyniki", foreground="gray")
            self.ik_result_label.pack(side="left", padx=(20, 0))
            
            # Store calculated angles
            self.calculated_angles = None
        
        # Command selection frame (existing code...)
        cmd_frame = ttk.LabelFrame(main_frame, text="Wybór komendy i parametry", padding=10)
        cmd_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create horizontal layout: commands on left, parameters on right
        cmd_content = ttk.Frame(cmd_frame)
        cmd_content.pack(fill="both", expand=True)
        
        # Left side - Command selection
        cmd_left = ttk.Frame(cmd_content)
        cmd_left.pack(side="left", fill="y", padx=(0, 20))
        
        ttk.Label(cmd_left, text="Dostępne komendy:").pack(anchor="w", pady=(0, 5))
        
        cmd_listbox_frame = ttk.Frame(cmd_left)
        cmd_listbox_frame.pack(fill="y", expand=True)
        
        self.cmd_listbox = tk.Listbox(cmd_listbox_frame, height=len(COMMANDS), width=15, exportselection=False)
        self.cmd_listbox.pack(side="left", fill="y")
        
        cmd_scrollbar = ttk.Scrollbar(cmd_listbox_frame, orient="vertical", command=self.cmd_listbox.yview)
        self.cmd_listbox.configure(yscrollcommand=cmd_scrollbar.set)
        
        for cmd in COMMANDS.keys():
            self.cmd_listbox.insert(tk.END, cmd)
        
        self.cmd_listbox.selection_set(0)
        self.cmd_listbox.bind("<<ListboxSelect>>", self.on_cmd_change)
        
        # Right side - Parameters
        params_right = ttk.Frame(cmd_content)
        params_right.pack(side="left", fill="both", expand=True)
        
        ttk.Label(params_right, text="Parametry wybranej komendy:").pack(anchor="w", pady=(0, 10))
        
        # Parameters frame (scrollable)
        params_canvas_frame = ttk.Frame(params_right)
        params_canvas_frame.pack(fill="both", expand=True)
        
        # Canvas for scrollable parameters
        self.params_canvas = tk.Canvas(params_canvas_frame, highlightthickness=0)
        params_scrollbar = ttk.Scrollbar(params_canvas_frame, orient="vertical", command=self.params_canvas.yview)
        self.params_scrollable_frame = ttk.Frame(self.params_canvas)
        
        self.params_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.params_canvas.configure(scrollregion=self.params_canvas.bbox("all"))
        )
        
        self.params_canvas.create_window((0, 0), window=self.params_scrollable_frame, anchor="nw")
        self.params_canvas.configure(yscrollcommand=params_scrollbar.set)
        
        self.params_canvas.pack(side="left", fill="both", expand=True)
        params_scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            self.params_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.params_canvas.bind("<MouseWheel>", _on_mousewheel)
        
        self.params_frame = self.params_scrollable_frame
        
        # Send button frame
        send_frame = ttk.Frame(main_frame)
        send_frame.pack(fill="x", pady=(0, 10))
        
        self.send_btn = ttk.Button(send_frame, text="🚀 WYŚLIJ KOMENDĘ", command=self.send_command, state="disabled")
        self.send_btn.pack(side="left", padx=(0, 10))
        
        self.status_label = ttk.Label(send_frame, text="Oczekiwanie na połączenie...", foreground="orange")
        self.status_label.pack(side="left")
        
        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Odpowiedzi z ESP32", padding=10)
        output_frame.pack(fill="both", expand=True)
        
        text_frame = ttk.Frame(output_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.output_text = tk.Text(text_frame, height=12, wrap="word", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        
        self.output_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        clear_btn = ttk.Button(output_frame, text="Wyczyść logi", command=self.clear_output)
        clear_btn.pack(pady=(10, 0))
        
        # Initialize parameters for first command
        self.update_parameters()

    def calculate_inverse_kinematics(self):
        """Oblicza kinematykę odwrotną dla wprowadzonej pozycji"""
        if not IKPY_AVAILABLE or not self.robot_kinematics.chain:
            messagebox.showerror("Błąd", "Kinematyka odwrotna nie jest dostępna!")
            return
        
        try:
            # Pobierz pozycję docelową
            x = float(self.target_x.get())
            y = float(self.target_y.get())
            z = float(self.target_z.get())
            target_position = [x, y, z]
            
            # Oblicz kinematykę odwrotną
            angles_deg, error, actual_pos = self.robot_kinematics.calculate_inverse_kinematics(target_position)
            
            # Zapisz obliczone kąty
            self.calculated_angles = angles_deg
            
            # Wyświetl wyniki
            if error < 0.01:  # błąd < 1cm
                self.ik_result_label.config(
                    text=f"✅ Sukces! Kąty: {[f'{a:.1f}°' for a in angles_deg]} | Błąd: {error:.4f}m", 
                    foreground="green"
                )
                self.send_ik_btn.config(state="normal")
            else:
                self.ik_result_label.config(
                    text=f"⚠️ Duży błąd! Kąty: {[f'{a:.1f}°' for a in angles_deg]} | Błąd: {error:.4f}m", 
                    foreground="orange"
                )
                self.send_ik_btn.config(state="normal")
            
            # Wyświetl szczegóły w logach
            self.show_output(f"=== KINEMATYKA ODWROTNA ===")
            self.show_output(f"Pozycja docelowa: [{x:.3f}, {y:.3f}, {z:.3f}]")
            self.show_output(f"Pozycja osiągnięta: [{actual_pos[0]:.3f}, {actual_pos[1]:.3f}, {actual_pos[2]:.3f}]")
            self.show_output(f"Błąd pozycjonowania: {error:.6f}m")
            for i, angle in enumerate(angles_deg):
                self.show_output(f"θ{i+1} = {angle:.2f}°")
            
        except ValueError as e:
            messagebox.showerror("Błąd", f"Nieprawidłowe wartości pozycji: {e}")
        except Exception as e:
            messagebox.showerror("Błąd", f"Błąd obliczania kinematyki: {e}")

    def send_inverse_kinematics(self):
        """Wysyła obliczone kąty na robot"""
        if not self.calculated_angles:
            messagebox.showwarning("Błąd", "Najpierw oblicz kąty!")
            return
        
        if not self.client.connected:
            messagebox.showwarning("Brak połączenia", "Nie można wysłać - brak połączenia z ESP32!")
            return
        
        # Przygotuj parametry komendy frame
        params = {
            "deg": self.calculated_angles,
            "ms": 2000,  # 2 sekundy na ruch
            "led": 150,
            "rgb": {"r": 0, "g": 255, "b": 100}  # Zielony - ruch z kinematyki odwrotnej
        }
        
        # Wyślij komendę
        self.show_output(f">>> Wysyłam kąty z kinematyki odwrotnej: {self.calculated_angles}")
        self.client.send_command("frame", params)
        
        # Zablokuj przycisk na chwilę
        self.send_ik_btn.config(state="disabled")
        self.after(3000, lambda: self.send_ik_btn.config(state="normal") if self.calculated_angles else None)

    # Reszta metod pozostaje bez zmian...
    def create_param_widgets(self, params):
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        
        self.param_vars.clear()
        
        if not params:
            no_params_label = ttk.Label(self.params_frame, text="Ta komenda nie wymaga parametrów", 
                                       font=("TkDefaultFont", 10, "italic"), foreground="gray")
            no_params_label.pack(pady=20)
            return
        
        container = ttk.Frame(self.params_frame)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        row = 0
        for key, value in params.items():
            if key == "deg" and isinstance(value, list):
                servo_label = ttk.Label(container, text="Kąty serw (deg):", font=("TkDefaultFont", 10, "bold"))
                servo_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=(5, 2))
                
                servo_frame = ttk.Frame(container)
                servo_frame.grid(row=row, column=1, sticky="w", pady=(5, 2))
                
                self.param_vars[key] = []
                for i, angle in enumerate(value):
                    servo_row = i // 3
                    servo_col = i % 3
                    
                    ttk.Label(servo_frame, text=f"S{i}:").grid(row=servo_row, column=servo_col*2, padx=(0, 5), pady=2)
                    var = tk.StringVar(value=str(angle))
                    entry = ttk.Entry(servo_frame, textvariable=var, width=8)
                    entry.grid(row=servo_row, column=servo_col*2+1, padx=(0, 15), pady=2)
                    self.param_vars[key].append(var)
                
            elif key == "rgb" and isinstance(value, dict):
                rgb_label = ttk.Label(container, text="RGB LED:", font=("TkDefaultFont", 10, "bold"))
                rgb_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=(5, 2))
                
                rgb_frame = ttk.Frame(container)
                rgb_frame.grid(row=row, column=1, sticky="w", pady=(5, 2))
                
                self.param_vars[key] = {}
                colors = [("r", "Czerwony", "red"), ("g", "Zielony", "green"), ("b", "Niebieski", "blue")]
                for i, (color, label, fg_color) in enumerate(colors):
                    ttk.Label(rgb_frame, text=f"{label}:", foreground=fg_color).grid(row=i, column=0, sticky="w", padx=(0, 5), pady=1)
                    var = tk.StringVar(value=str(value.get(color, 0)))
                    entry = ttk.Entry(rgb_frame, textvariable=var, width=8)
                    entry.grid(row=i, column=1, padx=(0, 10), pady=1)
                    self.param_vars[key][color] = var
                    
            elif key == "points":
                points_label = ttk.Label(container, text="Punkty trajektorii:", font=("TkDefaultFont", 10, "bold"))
                points_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=(5, 2))
                
                points_info = ttk.Label(container, text="(używa predefiniowanych punktów)\n3 punkty z RGB i czasem", 
                                      foreground="gray", font=("TkDefaultFont", 9))
                points_info.grid(row=row, column=1, sticky="w", pady=(5, 2))
                self.param_vars[key] = value
                
            else:
                label_text = self.get_param_label(key)
                param_label = ttk.Label(container, text=f"{label_text}:", font=("TkDefaultFont", 10))
                param_label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(5, 2))
                
                var = tk.StringVar(value=str(value))
                entry = ttk.Entry(container, textvariable=var, width=25)
                entry.grid(row=row, column=1, sticky="w", pady=(5, 2))
                self.param_vars[key] = var
                
                help_text = self.get_param_help(key)
                if help_text:
                    help_label = ttk.Label(container, text=help_text, foreground="gray", font=("TkDefaultFont", 8))
                    help_label.grid(row=row, column=2, sticky="w", padx=(10, 0), pady=(5, 2))
            
            row += 1
        
        container.update_idletasks()
        self.params_canvas.configure(scrollregion=self.params_canvas.bbox("all"))

    def get_param_label(self, key):
        labels = {
            "ms": "Czas (ms)",
            "val": "Wartość LED (0-255)",
            "hz": "Częstotliwość (Hz)",
            "ch": "Kanał serwa (0-4)",
            "min_us": "Min impulsu (μs)",
            "max_us": "Max impulsu (μs)", 
            "offset_us": "Offset (μs)",
            "invert": "Inwersja (true/false)",
            "led": "LED (0-255)",
            "freq": "Częstotliwość stream (Hz)",
            "r": "Czerwony (0-255)",
            "g": "Zielony (0-255)",
            "b": "Niebieski (0-255)"
        }
        return labels.get(key, key.capitalize())

    def get_param_help(self, key):
        help_texts = {
            "ms": "Czas wykonania ruchu",
            "val": "Jasność LED",
            "hz": "40-60 Hz dla serw",
            "ch": "Numer serwa",
            "min_us": "Minimalna szerokość impulsu",
            "max_us": "Maksymalna szerokość impulsu",
            "offset_us": "Korekta środkowej pozycji",
            "invert": "Odwrócenie kierunku",
            "led": "Jasność LED na PCA9685",
            "freq": "Częstotliwość aktualizacji"
        }
        return help_texts.get(key, "")

    def on_cmd_change(self, event=None):
        self.update_parameters()

    def update_parameters(self):
        selection = self.cmd_listbox.curselection()
        if not selection:
            return
        
        cmd = list(COMMANDS.keys())[selection[0]]
        params = COMMANDS[cmd]
        self.create_param_widgets(params)

    def collect_parameters(self):
        params = {}
        
        for key, var in self.param_vars.items():
            if key == "deg" and isinstance(var, list):
                angles = []
                for angle_var in var:
                    try:
                        angles.append(float(angle_var.get()))
                    except ValueError:
                        angles.append(0.0)
                params[key] = angles
                
            elif key == "rgb" and isinstance(var, dict):
                rgb = {}
                for color, color_var in var.items():
                    try:
                        rgb[color] = int(color_var.get())
                    except ValueError:
                        rgb[color] = 0
                params[key] = rgb
                
            elif key == "points":
                params[key] = var
                
            else:
                value_str = var.get()
                try:
                    if key in ["ms", "val", "ch", "min_us", "max_us", "offset_us", "led", "freq", "r", "g", "b"]:
                        if key == "hz":
                            params[key] = float(value_str)
                        else:
                            params[key] = int(value_str)
                    elif key == "invert":
                        params[key] = value_str.lower() in ("true", "1", "yes", "on")
                    else:
                        params[key] = value_str
                except ValueError:
                    if key == "hz":
                        params[key] = 50.0
                    else:
                        params[key] = 0
        
        return params

    def send_command(self):
        selection = self.cmd_listbox.curselection()
        if not selection:
            messagebox.showwarning("Błąd", "Wybierz komendę!")
            return
        
        if not self.client.connected:
            messagebox.showwarning("Brak połączenia", 
                                 "Nie można wysłać komendy - brak połączenia z ESP32.\n"
                                 "Sprawdź czy ESP32 jest włączony i podłączony do sieci WiFi.")
            return
            
        cmd = list(COMMANDS.keys())[selection[0]]
        params = self.collect_parameters()
        
        self.status_label.config(text="Wysyłanie...", foreground="orange")
        self.send_btn.config(state="disabled")
        
        if params:
            send_obj = {"cmd": cmd, **params}
        else:
            send_obj = {"cmd": cmd}
            
        self.show_output(f">>> Wysyłam: {json.dumps(send_obj, indent=2)}")
        
        self.client.send_command(cmd, params)
        self.after(1000, self.reset_send_button)

    def reset_send_button(self):
        if self.client.connected:
            self.send_btn.config(state="normal")
            self.status_label.config(text="Gotowy do wysłania", foreground="green")
        else:
            self.send_btn.config(state="disabled")
            self.status_label.config(text="Brak połączenia - nie można wysłać", foreground="red")

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)

    def show_output(self, msg):
        self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)

    def update_connection_status(self, connected):
        if connected:
            self.connection_label.config(text="🟢 POŁĄCZONY", foreground="green")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✓ Aktywny", foreground="green")
            self.ping_btn.config(state="normal")
            self.send_btn.config(state="normal")
            self.status_label.config(text="Gotowy do wysłania", foreground="green")
            current_time = time.strftime("%H:%M:%S")
            self.last_ping_label.config(text=f"Ostatni ping: {current_time}", foreground="green")
        else:
            self.connection_label.config(text="🔴 ROZŁĄCZONY", foreground="red")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✗ Niedostępny", foreground="red")
            self.ping_btn.config(state="normal")
            self.send_btn.config(state="disabled")
            self.status_label.config(text="Brak połączenia - nie można wysłać", foreground="red")
            self.last_ping_label.config(text="Brak połączenia", foreground="red")

    def manual_ping(self):
        self.ping_btn.config(state="disabled", text="Pingowanie...")
        self.client.send_command("ping", {})
        self.after(2000, self.reset_ping_button)

    def reset_ping_button(self):
        self.ping_btn.config(state="normal", text="🏓 Test Ping")

    def start_ping_timer(self):
        self.auto_ping()
        self.update_ping_countdown(10)
        self.ping_timer = self.after(10000, self.start_ping_timer)

    def update_ping_countdown(self, seconds_left):
        if seconds_left > 0:
            if hasattr(self, 'last_ping_label') and self.client.connected:
                current_time = time.strftime("%H:%M:%S")
                self.last_ping_label.config(text=f"Ostatni ping: {current_time} (następny za {seconds_left}s)")
            self.after(1000, lambda: self.update_ping_countdown(seconds_left - 1))

    def auto_ping(self):
        if hasattr(self.client, 'send_ping'):
            self.client.send_ping()

    def on_closing(self):
        if self.ping_timer:
            self.after_cancel(self.ping_timer)
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

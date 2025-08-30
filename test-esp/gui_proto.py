import tkinter as tk
from tkinter import ttk, messagebox
import json
import asyncio
import threading
import time
import websockets

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
                
                # Wyślij ping
                ping_cmd = {"cmd": "ping"}
                await ws.send(json.dumps(ping_cmd, separators=(",", ":")))
                
                # Odbierz odpowiedź (ale nie loguj)
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                self.last_ping_time = time.time()
                
                # Sprawdź czy odpowiedź zawiera pong
                try:
                    response_data = json.loads(response)
                    if response_data.get("pong") == True:
                        # Ping successful, connection is good
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
                
                # Odbierz powitalną wiadomość (tylko przy pierwszym połączeniu)
                try:
                    welcome = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    self.output_callback(f"Wiadomość powitalna: {welcome}")
                except asyncio.TimeoutError:
                    pass  # Może być już połączony
                
                # Przygotuj komendę
                if params:
                    obj = {"cmd": cmd}
                    obj.update(params)
                else:
                    obj = {"cmd": cmd}
                await ws.send(json.dumps(obj, separators=(",", ":")))
                
                # Odbierz odpowiedź
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
        self.title("ESP32 RoboArm - Klient WebSocket")
        self.geometry("800x700")
        self.client = WebSocketClient(HOST, PORT, self.show_output, self.update_connection_status)
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
        
        # Command selection frame
        cmd_frame = ttk.LabelFrame(main_frame, text="Wybór komendy i parametry", padding=10)
        cmd_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create horizontal layout: commands on left, parameters on right
        cmd_content = ttk.Frame(cmd_frame)
        cmd_content.pack(fill="both", expand=True)
        
        # Left side - Command selection
        cmd_left = ttk.Frame(cmd_content)
        cmd_left.pack(side="left", fill="y", padx=(0, 20))
        
        ttk.Label(cmd_left, text="Dostępne komendy:").pack(anchor="w", pady=(0, 5))
        
        # Lista komend bez scrolla - używamy Listbox z odpowiednim height
        cmd_listbox_frame = ttk.Frame(cmd_left)
        cmd_listbox_frame.pack(fill="y", expand=True)
        
        self.cmd_listbox = tk.Listbox(cmd_listbox_frame, height=len(COMMANDS), width=15, exportselection=False)
        self.cmd_listbox.pack(side="left", fill="y")
        
        # Scrollbar for commands (just in case)
        cmd_scrollbar = ttk.Scrollbar(cmd_listbox_frame, orient="vertical", command=self.cmd_listbox.yview)
        self.cmd_listbox.configure(yscrollcommand=cmd_scrollbar.set)
        # Only show scrollbar if needed
        
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
        
        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            self.params_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.params_canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Parameters will be created in this frame
        self.params_frame = self.params_scrollable_frame
        
        # Send button frame
        send_frame = ttk.Frame(main_frame)
        send_frame.pack(fill="x", pady=(0, 10))
        
        self.send_btn = ttk.Button(send_frame, text="🚀 WYŚLIJ KOMENDĘ", command=self.send_command, state="disabled")
        self.send_btn.pack(side="left", padx=(0, 10))
        
        # Status info
        self.status_label = ttk.Label(send_frame, text="Oczekiwanie na połączenie...", foreground="orange")
        self.status_label.pack(side="left")
        
        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Odpowiedzi z ESP32", padding=10)
        output_frame.pack(fill="both", expand=True)
        
        # Scrollable text with scrollbar
        text_frame = ttk.Frame(output_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.output_text = tk.Text(text_frame, height=15, wrap="word", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=scrollbar.set)
        
        self.output_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Clear button
        clear_btn = ttk.Button(output_frame, text="Wyczyść logi", command=self.clear_output)
        clear_btn.pack(pady=(10, 0))
        
        # Initialize parameters for first command
        self.update_parameters()

    def create_param_widgets(self, params):
        # Clear existing parameter widgets
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        
        self.param_vars.clear()
        
        if not params:
            no_params_label = ttk.Label(self.params_frame, text="Ta komenda nie wymaga parametrów", 
                                       font=("TkDefaultFont", 10, "italic"), foreground="gray")
            no_params_label.pack(pady=20)
            return
        
        # Create a container for better spacing
        container = ttk.Frame(self.params_frame)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        row = 0
        for key, value in params.items():
            if key == "deg" and isinstance(value, list):
                # Special handling for servo angles
                servo_label = ttk.Label(container, text="Kąty serw (deg):", font=("TkDefaultFont", 10, "bold"))
                servo_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=(5, 2))
                
                servo_frame = ttk.Frame(container)
                servo_frame.grid(row=row, column=1, sticky="w", pady=(5, 2))
                
                self.param_vars[key] = []
                for i, angle in enumerate(value):
                    servo_row = i // 3  # 3 servos per row
                    servo_col = i % 3
                    
                    ttk.Label(servo_frame, text=f"S{i}:").grid(row=servo_row, column=servo_col*2, padx=(0, 5), pady=2)
                    var = tk.StringVar(value=str(angle))
                    entry = ttk.Entry(servo_frame, textvariable=var, width=8)
                    entry.grid(row=servo_row, column=servo_col*2+1, padx=(0, 15), pady=2)
                    self.param_vars[key].append(var)
                
            elif key == "rgb" and isinstance(value, dict):
                # Special handling for RGB values
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
                # Special handling for trajectory points - simplified
                points_label = ttk.Label(container, text="Punkty trajektorii:", font=("TkDefaultFont", 10, "bold"))
                points_label.grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=(5, 2))
                
                points_info = ttk.Label(container, text="(używa predefiniowanych punktów)\n3 punkty z RGB i czasem", 
                                      foreground="gray", font=("TkDefaultFont", 9))
                points_info.grid(row=row, column=1, sticky="w", pady=(5, 2))
                self.param_vars[key] = value  # Keep original value
                
            else:
                # Standard parameter
                label_text = self.get_param_label(key)
                param_label = ttk.Label(container, text=f"{label_text}:", font=("TkDefaultFont", 10))
                param_label.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(5, 2))
                
                var = tk.StringVar(value=str(value))
                entry = ttk.Entry(container, textvariable=var, width=25)
                entry.grid(row=row, column=1, sticky="w", pady=(5, 2))
                self.param_vars[key] = var
                
                # Add helper text for some parameters
                help_text = self.get_param_help(key)
                if help_text:
                    help_label = ttk.Label(container, text=help_text, foreground="gray", font=("TkDefaultFont", 8))
                    help_label.grid(row=row, column=2, sticky="w", padx=(10, 0), pady=(5, 2))
            
            row += 1
        
        # Update canvas scroll region
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
        """Zwraca tekst pomocy dla parametru"""
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
                # Collect servo angles
                angles = []
                for angle_var in var:
                    try:
                        angles.append(float(angle_var.get()))
                    except ValueError:
                        angles.append(0.0)
                params[key] = angles
                
            elif key == "rgb" and isinstance(var, dict):
                # Collect RGB values
                rgb = {}
                for color, color_var in var.items():
                    try:
                        rgb[color] = int(color_var.get())
                    except ValueError:
                        rgb[color] = 0
                params[key] = rgb
                
            elif key == "points":
                # Use predefined trajectory points
                params[key] = var
                
            else:
                # Standard parameter
                value_str = var.get()
                try:
                    # Try to parse as appropriate type
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
        
        # Sprawdź połączenie
        if not self.client.connected:
            messagebox.showwarning("Brak połączenia", 
                                 "Nie można wysłać komendy - brak połączenia z ESP32.\n"
                                 "Sprawdź czy ESP32 jest włączony i podłączony do sieci WiFi.")
            return
            
        cmd = list(COMMANDS.keys())[selection[0]]
        params = self.collect_parameters()
        
        self.status_label.config(text="Wysyłanie...", foreground="orange")
        self.send_btn.config(state="disabled")
        
        # Show what we're sending
        if params:
            send_obj = {"cmd": cmd, **params}
        else:
            send_obj = {"cmd": cmd}
            
        self.show_output(f">>> Wysyłam: {json.dumps(send_obj, indent=2)}")
        
        self.client.send_command(cmd, params)
        
        # Re-enable button after short delay
        self.after(1000, self.reset_send_button)

    def reset_send_button(self):
        # Przywróć przycisk tylko jeśli jest połączenie
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
        """Aktualizuje wskaźnik połączenia"""
        if connected:
            self.connection_label.config(text="🟢 POŁĄCZONY", foreground="green")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✓ Aktywny", foreground="green")
            self.ping_btn.config(state="normal")
            # Włącz przycisk wysyłania
            self.send_btn.config(state="normal")
            self.status_label.config(text="Gotowy do wysłania", foreground="green")
            # Aktualizuj informację o ostatnim pingu
            current_time = time.strftime("%H:%M:%S")
            self.last_ping_label.config(text=f"Ostatni ping: {current_time}", foreground="green")
        else:
            self.connection_label.config(text="🔴 ROZŁĄCZONY", foreground="red")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✗ Niedostępny", foreground="red")
            self.ping_btn.config(state="normal")
            # Zablokuj przycisk wysyłania
            self.send_btn.config(state="disabled")
            self.status_label.config(text="Brak połączenia - nie można wysłać", foreground="red")
            self.last_ping_label.config(text="Brak połączenia", foreground="red")

    def manual_ping(self):
        """Ręczny test ping"""
        self.ping_btn.config(state="disabled", text="Pingowanie...")
        self.client.send_command("ping", {})
        self.after(2000, self.reset_ping_button)

    def reset_ping_button(self):
        """Przywraca przycisk ping"""
        self.ping_btn.config(state="normal", text="🏓 Test Ping")

    def start_ping_timer(self):
        """Uruchamia automatyczny ping co 10 sekund"""
        self.auto_ping()
        self.update_ping_countdown(10)
        self.ping_timer = self.after(10000, self.start_ping_timer)  # 10 sekund

    def update_ping_countdown(self, seconds_left):
        """Aktualizuje odliczanie do następnego pingu"""
        if seconds_left > 0:
            if hasattr(self, 'last_ping_label') and self.client.connected:
                current_time = time.strftime("%H:%M:%S")
                self.last_ping_label.config(text=f"Ostatni ping: {current_time} (następny za {seconds_left}s)")
            self.after(1000, lambda: self.update_ping_countdown(seconds_left - 1))

    def auto_ping(self):
        """Automatyczny ping (bez logowania)"""
        if hasattr(self.client, 'send_ping'):
            self.client.send_ping()

    def on_closing(self):
        """Obsługa zamykania aplikacji"""
        if self.ping_timer:
            self.after_cancel(self.ping_timer)
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

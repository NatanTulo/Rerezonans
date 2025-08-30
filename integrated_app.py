#!/usr/bin/env python3
"""
🎨 REREZONANS - Integrowana aplikacja do malowania światłem
Hackaton 2025 - Projekt ramienia robotycznego PUMA z przetwarzaniem obrazu

Funkcjonalności:
1. 🖼️  Przetwarzanie obrazu - wykrywanie konturów i krawędzi
2. 🧮  Kinematyka odwrotna - obliczanie kątów serw
3. 🤖  Komunikacja z ESP32 - WebSocket control
4. 🎨  Generowanie ścieżek dla light painting
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import asyncio
import threading
import time
import numpy as np
import cv2 as cv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import websockets

# Próba importu ikpy z obsługą błędów
try:
    import ikpy.chain
    from ikpy.link import DHLink, OriginLink
    IKPY_AVAILABLE = True
except ImportError:
    IKPY_AVAILABLE = False
    print("⚠️ UWAGA: Biblioteka ikpy niedostępna - kinematyka odwrotna wyłączona")

PI = np.pi

# Konfiguracja ESP32
HOST = "192.168.4.1"
PORT = 81

# Lista obsługiwanych komend ESP32
ESP32_COMMANDS = {
    "ping": {},
    "home": {"ms": 800, "led": 128, "rgb": {"r": 0, "g": 255, "b": 0}},
    "frame": {"deg": [0, 0, 0, 0, 0], "ms": 1000, "led": 200, "rgb": {"r": 255, "g": 0, "b": 0}},
    "rt_frame": {"deg": [0, 0, 0, 0, 0], "ms": 100},
    "trajectory": {"points": []},
    "status": {},
}

class RobotKinematics:
    """Klasa do obsługi kinematyki odwrotnej robota PUMA"""
    
    def __init__(self):
        self.chain = None
        if not IKPY_AVAILABLE:
            return
            
        # Parametry robota PUMA (z calcDegrees.py)
        self.L1, self.L2, self.L3, self.L4, self.L5 = 1, 1, 1, 1, 1
        self.alpha1, self.alpha2, self.alpha3, self.alpha4, self.alpha5 = PI/2, 0, -PI/2, 0, PI/2
        self.lam1, self.lam2, self.lam3, self.lam4, self.lam5 = self.L1, self.L2, 0, 0, self.L3
        self.del1, self.del2, self.del3, self.del4, self.del5 = self.L1, 0, self.L3, self.L4, 0
        
        try:
            # Definicja łańcucha kinematycznego
            self.chain = ikpy.chain.Chain([
                OriginLink(),
                DHLink(name="joint_1", d=self.del1, a=self.lam1, alpha=self.alpha1, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_2", d=self.del2, a=self.lam2, alpha=self.alpha2, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_3", d=self.del3, a=self.lam3, alpha=self.alpha3, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_4", d=self.del4, a=self.lam4, alpha=self.alpha4, bounds=(-PI/2, PI/2)),
                DHLink(name="joint_5", d=self.del5, a=self.lam5, alpha=self.alpha5, bounds=(-PI/2, PI/2))
            ])
        except Exception as e:
            print(f"❌ Błąd inicjalizacji łańcucha kinematycznego: {e}")
            self.chain = None
    
    def calculate_inverse_kinematics(self, target_position):
        """Oblicza kinematykę odwrotną dla zadanej pozycji"""
        if not self.chain:
            return None, None, "Kinematyka niedostępna"
        
        initial_position = [0, 0, 0, 0, 0, 0]  # OriginLink + 5 jointów
        
        try:
            joint_angles = self.chain.inverse_kinematics(
                target_position, 
                initial_position=initial_position
            )
            
            # Konwersja na stopnie i zwrócenie tylko kątów przegubów (bez OriginLink)
            joint_angles_deg = [np.degrees(angle) for angle in joint_angles[1:]]
            
            # Weryfikacja rozwiązania
            result_position = self.chain.forward_kinematics(joint_angles)
            error = np.linalg.norm(np.array(target_position) - result_position[:3, 3])
            
            return joint_angles_deg, result_position[:3, 3], f"Błąd: {error:.4f}m"
            
        except Exception as e:
            return None, None, f"Błąd obliczeń: {e}"

class ImageProcessor:
    """Klasa do przetwarzania obrazów - wykrywanie konturów i krawędzi"""
    
    def __init__(self):
        self.current_image = None
        self.contours = []
        self.edge_paths = []
        
    def load_image(self, image_path):
        """Wczytuje obraz z pliku"""
        try:
            self.current_image = cv.imread(image_path)
            if self.current_image is None:
                return False, "Nie można wczytać obrazu"
            return True, "Obraz wczytany pomyślnie"
        except Exception as e:
            return False, f"Błąd wczytywania: {e}"
    
    def process_image_interactive(self):
        """Interaktywne przetwarzanie obrazu (z kontury.py)"""
        if self.current_image is None:
            return False, "Brak wczytanego obrazu"
        
        try:
            # Zmienne do interaktywnego rysowania
            all_contours = []
            current = []
            drawing = False
            temp = self.current_image.copy()
            
            def on_mouse(evt, x, y, flags, param):
                nonlocal drawing, current, temp
                if evt == cv.EVENT_LBUTTONDOWN:
                    drawing = True
                    current = [(x, y)]
                elif evt == cv.EVENT_MOUSEMOVE and drawing:
                    current.append((x, y))
                    cv.circle(temp, (x, y), 2, (0, 0, 255), -1)
                    cv.line(temp, current[-2], current[-1], (0, 255, 0), 2)
                elif evt == cv.EVENT_LBUTTONUP:
                    drawing = False
                    if len(current) > 2:
                        all_contours.append(np.array(current, dtype=np.int32))
            
            cv.namedWindow("Rysuj kontury (ENTER=OK, BACKSPACE=usuń)")
            cv.setMouseCallback("Rysuj kontury (ENTER=OK, BACKSPACE=usuń)", on_mouse)
            
            while True:
                cv.imshow("Rysuj kontury (ENTER=OK, BACKSPACE=usuń)", temp)
                k = cv.waitKey(1) & 0xFF
                if k == 13:    # ENTER
                    break
                elif k == 8:   # BACKSPACE
                    if all_contours:
                        all_contours.pop()
                        temp = self.current_image.copy()
                        for cnt in all_contours:
                            for i in range(1, len(cnt)):
                                cv.line(temp, tuple(cnt[i-1]), tuple(cnt[i]), (0,255,0), 2)
                                cv.circle(temp, tuple(cnt[i]), 2, (0,0,255), -1)
            
            cv.destroyAllWindows()
            
            # Przetwarzanie konturów na krawędzie
            mask = np.zeros(self.current_image.shape[:2], np.uint8)
            for cnt in all_contours:
                cv.fillPoly(mask, [cnt], 255)
            
            roi = cv.bitwise_and(self.current_image, self.current_image, mask=mask)
            roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
            edges = cv.Canny(roi_gray, 100, 200)
            
            # Wyciąganie konturów jako sekwencji punktów
            conts, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)
            self.edge_paths = [[tuple(pt[0]) for pt in cnt] for cnt in conts]
            
            return True, f"Wykryto {len(self.edge_paths)} ścieżek krawędzi"
            
        except Exception as e:
            return False, f"Błąd przetwarzania: {e}"
    
    def convert_to_robot_coordinates(self, scale_factor=0.01, offset_x=0, offset_y=0, offset_z=1.0):
        """Konwertuje piksele obrazu na współrzędne robota"""
        robot_paths = []
        
        for path in self.edge_paths:
            robot_path = []
            for x, y in path:
                # Konwersja pikseli na metry z offsetem
                robot_x = (x * scale_factor) + offset_x
                robot_y = (y * scale_factor) + offset_y
                robot_z = offset_z  # Stała wysokość dla rysowania
                
                robot_path.append([robot_x, robot_y, robot_z])
            
            robot_paths.append(robot_path)
        
        return robot_paths

class WebSocketClient:
    """Klient WebSocket do komunikacji z ESP32"""
    
    def __init__(self, host, port, output_callback, connection_callback):
        self.host = host
        self.port = port
        self.output_callback = output_callback
        self.connection_callback = connection_callback
        self.loop = asyncio.new_event_loop()
        self.ws = None
        self.connected = False
        
    def send_command(self, cmd, params):
        """Wysyła komendę do ESP32"""
        threading.Thread(target=self._send_command_thread, args=(cmd, params)).start()
    
    def _send_command_thread(self, cmd, params):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._send(cmd, params))
    
    async def _send(self, cmd, params):
        uri = f"ws://{self.host}:{self.port}"
        try:
            async with websockets.connect(uri, ping_timeout=5, close_timeout=5) as ws:
                self.ws = ws
                if not self.connected:
                    self.connected = True
                    self.connection_callback(True)
                
                # Przygotuj komendę
                if params:
                    obj = {"cmd": cmd}
                    obj.update(params)
                else:
                    obj = {"cmd": cmd}
                    
                await ws.send(json.dumps(obj, separators=(",", ":")))
                
                # Odbierz odpowiedź (dla niektórych komend)
                if cmd not in ["rt_frame"]:  # rt_frame nie ma odpowiedzi
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                        self.output_callback(f"✅ Odpowiedź: {response}")
                    except asyncio.TimeoutError:
                        self.output_callback("⏰ Brak odpowiedzi (timeout)")
                else:
                    self.output_callback(f"🚀 Wysłano: {cmd}")
                        
        except Exception as e:
            if self.connected:
                self.connected = False
                self.connection_callback(False)
            self.output_callback(f"❌ Błąd połączenia: {e}")

class IntegratedApp(tk.Tk):
    """Główna aplikacja integrująca wszystkie funkcjonalności"""
    
    def __init__(self):
        super().__init__()
        self.title("🎨 REREZONANS - Light Painting Robot")
        self.geometry("1200x900")
        
        # Inicjalizacja komponentów
        self.kinematics = RobotKinematics()
        self.image_processor = ImageProcessor()
        self.esp32_client = WebSocketClient(HOST, PORT, self.log_message, self.update_connection_status)
        
        # Zmienne stanu
        self.current_robot_paths = []
        self.trajectory_points = []
        
        self.create_widgets()
        
    def create_widgets(self):
        """Tworzy interfejs użytkownika"""
        
        # ===== GÓRNA SEKCJA - STATUS I POŁĄCZENIE =====
        status_frame = ttk.LabelFrame(self, text="📡 Status systemu", padding=10)
        status_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Status połączenia
        conn_frame = ttk.Frame(status_frame)
        conn_frame.pack(fill="x")
        
        self.connection_label = ttk.Label(conn_frame, text="🔴 ROZŁĄCZONY", foreground="red", 
                                         font=("TkDefaultFont", 12, "bold"))
        self.connection_label.pack(side="left")
        
        self.connection_details = ttk.Label(conn_frame, text=f"ESP32: {HOST}:{PORT}", foreground="gray")
        self.connection_details.pack(side="left", padx=(20, 0))
        
        # Przyciski testowe
        test_frame = ttk.Frame(conn_frame)
        test_frame.pack(side="right")
        
        ttk.Button(test_frame, text="🏓 Test Ping", command=self.test_connection).pack(side="left", padx=5)
        ttk.Button(test_frame, text="🏠 Home", command=self.send_home).pack(side="left", padx=5)
        
        # ===== GŁÓWNY OBSZAR - ZAKŁADKI =====
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # ZAKŁADKA 1: Przetwarzanie obrazu
        self.create_image_tab(notebook)
        
        # ZAKŁADKA 2: Kinematyka i planowanie ścieżek
        self.create_kinematics_tab(notebook)
        
        # ZAKŁADKA 3: Sterowanie robotem
        self.create_control_tab(notebook)
        
        # ===== DOLNA SEKCJA - LOGI =====
        log_frame = ttk.LabelFrame(self, text="📝 Logi systemu", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        # Obszar logów
        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.log_text = tk.Text(text_frame, height=8, wrap="word", font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")
        
        # Przycisk czyszczenia logów
        ttk.Button(log_frame, text="🗑️ Wyczyść logi", command=self.clear_logs).pack(pady=(10, 0))
        
        # Powitanie
        self.log_message("🎨 REREZONANS - System Light Painting uruchomiony!")
        if IKPY_AVAILABLE:
            self.log_message("✅ Kinematyka odwrotna dostępna")
        else:
            self.log_message("⚠️ Kinematyka odwrotna niedostępna - brak biblioteki ikpy")
    
    def create_image_tab(self, parent):
        """Tworzy zakładkę przetwarzania obrazu"""
        tab = ttk.Frame(parent)
        parent.add(tab, text="🖼️ Obraz")
        
        # Sekcja wczytywania obrazu
        load_frame = ttk.LabelFrame(tab, text="Wczytywanie obrazu", padding=10)
        load_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(load_frame, text="📁 Wybierz obraz", command=self.load_image).pack(side="left", padx=5)
        self.image_status_label = ttk.Label(load_frame, text="Brak wczytanego obrazu", foreground="gray")
        self.image_status_label.pack(side="left", padx=20)
        
        # Sekcja przetwarzania
        process_frame = ttk.LabelFrame(tab, text="Przetwarzanie", padding=10)
        process_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(process_frame, text="✏️ Rysuj kontury", command=self.process_image_interactive).pack(side="left", padx=5)
        ttk.Button(process_frame, text="🔄 Auto-wykrywanie", command=self.process_image_auto).pack(side="left", padx=5)
        
        self.process_status_label = ttk.Label(process_frame, text="Oczekiwanie na przetwarzanie", foreground="gray")
        self.process_status_label.pack(side="left", padx=20)
        
        # Sekcja parametrów konwersji
        params_frame = ttk.LabelFrame(tab, text="Parametry konwersji na współrzędne robota", padding=10)
        params_frame.pack(fill="x", padx=10, pady=10)
        
        # Pierwsza linia parametrów
        params_line1 = ttk.Frame(params_frame)
        params_line1.pack(fill="x", pady=5)
        
        ttk.Label(params_line1, text="Skala (m/piksel):").pack(side="left")
        self.scale_var = tk.StringVar(value="0.01")
        ttk.Entry(params_line1, textvariable=self.scale_var, width=10).pack(side="left", padx=(5, 20))
        
        ttk.Label(params_line1, text="Offset X (m):").pack(side="left")
        self.offset_x_var = tk.StringVar(value="0.0")
        ttk.Entry(params_line1, textvariable=self.offset_x_var, width=10).pack(side="left", padx=(5, 20))
        
        ttk.Label(params_line1, text="Offset Y (m):").pack(side="left")
        self.offset_y_var = tk.StringVar(value="0.0")
        ttk.Entry(params_line1, textvariable=self.offset_y_var, width=10).pack(side="left", padx=(5, 20))
        
        ttk.Label(params_line1, text="Wysokość Z (m):").pack(side="left")
        self.offset_z_var = tk.StringVar(value="1.0")
        ttk.Entry(params_line1, textvariable=self.offset_z_var, width=10).pack(side="left", padx=(5, 20))
        
        ttk.Button(params_frame, text="🧮 Konwertuj na współrzędne robota", 
                  command=self.convert_to_robot_coordinates).pack(pady=10)
    
    def create_kinematics_tab(self, parent):
        """Tworzy zakładkę kinematyki"""
        tab = ttk.Frame(parent)
        parent.add(tab, text="🧮 Kinematyka")
        
        # Sekcja testowania pojedynczych punktów
        test_frame = ttk.LabelFrame(tab, text="Test pojedynczego punktu", padding=10)
        test_frame.pack(fill="x", padx=10, pady=10)
        
        # Wprowadzanie pozycji docelowej
        pos_frame = ttk.Frame(test_frame)
        pos_frame.pack(fill="x", pady=5)
        
        ttk.Label(pos_frame, text="Pozycja docelowa [X, Y, Z] (m):").pack(side="left")
        self.target_x_var = tk.StringVar(value="0.5")
        self.target_y_var = tk.StringVar(value="0.2")
        self.target_z_var = tk.StringVar(value="0.8")
        
        ttk.Entry(pos_frame, textvariable=self.target_x_var, width=8).pack(side="left", padx=(10, 2))
        ttk.Entry(pos_frame, textvariable=self.target_y_var, width=8).pack(side="left", padx=2)
        ttk.Entry(pos_frame, textvariable=self.target_z_var, width=8).pack(side="left", padx=2)
        
        ttk.Button(pos_frame, text="🧮 Oblicz kąty", command=self.calculate_angles).pack(side="left", padx=20)
        
        # Wyniki obliczeń
        self.kinematics_result = tk.Text(test_frame, height=6, wrap="word", font=("Consolas", 10))
        self.kinematics_result.pack(fill="x", pady=10)
        
        # Sekcja planowania ścieżek
        path_frame = ttk.LabelFrame(tab, text="Planowanie ścieżek z obrazu", padding=10)
        path_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        control_frame = ttk.Frame(path_frame)
        control_frame.pack(fill="x", pady=5)
        
        ttk.Button(control_frame, text="🗺️ Generuj ścieżki dla robota", 
                  command=self.generate_robot_paths).pack(side="left", padx=5)
        ttk.Button(control_frame, text="📊 Podgląd ścieżek", 
                  command=self.preview_paths).pack(side="left", padx=5)
        
        self.path_status_label = ttk.Label(control_frame, text="Brak wygenerowanych ścieżek", foreground="gray")
        self.path_status_label.pack(side="left", padx=20)
        
        # Lista ścieżek
        self.paths_listbox = tk.Listbox(path_frame, height=8)
        self.paths_listbox.pack(fill="both", expand=True, pady=10)
    
    def create_control_tab(self, parent):
        """Tworzy zakładkę sterowania robotem"""
        tab = ttk.Frame(parent)
        parent.add(tab, text="🤖 Sterowanie")
        
        # Sekcja trajektorii
        traj_frame = ttk.LabelFrame(tab, text="Wykonywanie trajektorii", padding=10)
        traj_frame.pack(fill="x", padx=10, pady=10)
        
        control_frame = ttk.Frame(traj_frame)
        control_frame.pack(fill="x", pady=5)
        
        ttk.Button(control_frame, text="🚀 Wykonaj Light Painting", 
                  command=self.execute_light_painting).pack(side="left", padx=5)
        ttk.Button(control_frame, text="⏸️ Stop", 
                  command=self.stop_execution).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🏠 Powrót Home", 
                  command=self.send_home).pack(side="left", padx=5)
        
        # Parametry wykonania
        params_frame = ttk.Frame(traj_frame)
        params_frame.pack(fill="x", pady=10)
        
        ttk.Label(params_frame, text="Czas ruchu (ms):").pack(side="left")
        self.move_time_var = tk.StringVar(value="1000")
        ttk.Entry(params_frame, textvariable=self.move_time_var, width=10).pack(side="left", padx=(5, 20))
        
        ttk.Label(params_frame, text="Jasność LED:").pack(side="left")
        self.led_brightness_var = tk.StringVar(value="255")
        ttk.Entry(params_frame, textvariable=self.led_brightness_var, width=10).pack(side="left", padx=(5, 20))
        
        # Sekcja ręcznego sterowania
        manual_frame = ttk.LabelFrame(tab, text="Ręczne sterowanie", padding=10)
        manual_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Kontrola kątów serw
        servo_frame = ttk.Frame(manual_frame)
        servo_frame.pack(fill="x", pady=10)
        
        self.servo_vars = []
        for i in range(5):
            ttk.Label(servo_frame, text=f"Serwo {i+1}:").grid(row=i//3, column=(i%3)*2, padx=(0,5), pady=2, sticky="w")
            var = tk.StringVar(value="0")
            entry = ttk.Entry(servo_frame, textvariable=var, width=8)
            entry.grid(row=i//3, column=(i%3)*2+1, padx=(0,15), pady=2)
            self.servo_vars.append(var)
        
        # Przyciski sterowania
        button_frame = ttk.Frame(manual_frame)
        button_frame.pack(fill="x", pady=10)
        
        ttk.Button(button_frame, text="📤 Wyślij pozycję", command=self.send_manual_position).pack(side="left", padx=5)
        ttk.Button(button_frame, text="🎨 Test RGB", command=self.test_rgb).pack(side="left", padx=5)
        ttk.Button(button_frame, text="📊 Status", command=self.get_status).pack(side="left", padx=5)
    
    # ===== METODY OBSŁUGI OBRAZU =====
    
    def load_image(self):
        """Wczytuje obraz z pliku"""
        file_path = filedialog.askopenfilename(
            title="Wybierz obraz",
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("Wszystkie pliki", "*.*")]
        )
        
        if file_path:
            success, message = self.image_processor.load_image(file_path)
            if success:
                self.image_status_label.config(text=f"✅ {message}", foreground="green")
                self.log_message(f"📁 Wczytano obraz: {file_path}")
            else:
                self.image_status_label.config(text=f"❌ {message}", foreground="red")
                self.log_message(f"❌ Błąd wczytywania obrazu: {message}")
    
    def process_image_interactive(self):
        """Uruchamia interaktywne przetwarzanie obrazu"""
        self.log_message("✏️ Uruchamianie interaktywnego rysowania konturów...")
        success, message = self.image_processor.process_image_interactive()
        
        if success:
            self.process_status_label.config(text=f"✅ {message}", foreground="green")
            self.log_message(f"✅ {message}")
        else:
            self.process_status_label.config(text=f"❌ {message}", foreground="red")
            self.log_message(f"❌ {message}")
    
    def process_image_auto(self):
        """Automatyczne wykrywanie konturów (do implementacji)"""
        self.log_message("🔄 Automatyczne wykrywanie konturów - w trakcie implementacji")
        messagebox.showinfo("Info", "Automatyczne wykrywanie będzie dodane w przyszłej wersji")
    
    def convert_to_robot_coordinates(self):
        """Konwertuje ścieżki obrazu na współrzędne robota"""
        try:
            scale = float(self.scale_var.get())
            offset_x = float(self.offset_x_var.get())
            offset_y = float(self.offset_y_var.get())
            offset_z = float(self.offset_z_var.get())
            
            self.current_robot_paths = self.image_processor.convert_to_robot_coordinates(
                scale, offset_x, offset_y, offset_z
            )
            
            total_points = sum(len(path) for path in self.current_robot_paths)
            self.log_message(f"🧮 Konwersja zakończona: {len(self.current_robot_paths)} ścieżek, {total_points} punktów")
            
        except ValueError as e:
            self.log_message(f"❌ Błąd konwersji: {e}")
    
    # ===== METODY KINEMATYKI =====
    
    def calculate_angles(self):
        """Oblicza kąty dla zadanej pozycji"""
        try:
            target_x = float(self.target_x_var.get())
            target_y = float(self.target_y_var.get())
            target_z = float(self.target_z_var.get())
            
            target_position = [target_x, target_y, target_z]
            
            angles, actual_pos, error_msg = self.kinematics.calculate_inverse_kinematics(target_position)
            
            result_text = f"Pozycja docelowa: [{target_x:.3f}, {target_y:.3f}, {target_z:.3f}] m\\n\\n"
            
            if angles is not None:
                result_text += "Kąty przegubów (stopnie):\\n"
                for i, angle in enumerate(angles):
                    result_text += f"  θ{i+1} = {angle:8.2f}°\\n"
                result_text += f"\\nRzeczywista pozycja: [{actual_pos[0]:.3f}, {actual_pos[1]:.3f}, {actual_pos[2]:.3f}] m\\n"
                result_text += f"Status: {error_msg}"
                
                # Aktualizuj pola serw
                for i, angle in enumerate(angles):
                    if i < len(self.servo_vars):
                        self.servo_vars[i].set(f"{angle:.1f}")
            else:
                result_text += f"❌ Błąd obliczeń: {error_msg}"
            
            self.kinematics_result.delete(1.0, tk.END)
            self.kinematics_result.insert(tk.END, result_text)
            
        except ValueError as e:
            self.log_message(f"❌ Błąd wprowadzonych danych: {e}")
    
    def generate_robot_paths(self):
        """Generuje ścieżki robota z kinematyką odwrotną"""
        if not self.current_robot_paths:
            self.log_message("❌ Brak ścieżek do przetworzenia - najpierw przetwórz obraz")
            return
        
        if not IKPY_AVAILABLE:
            self.log_message("❌ Kinematyka niedostępna - brak biblioteki ikpy")
            return
        
        self.trajectory_points = []
        failed_points = 0
        
        self.log_message("🗺️ Generowanie trajektorii z kinematyką odwrotną...")
        
        for path_idx, robot_path in enumerate(self.current_robot_paths):
            for point_idx, position in enumerate(robot_path):
                angles, actual_pos, error_msg = self.kinematics.calculate_inverse_kinematics(position)
                
                if angles is not None:
                    # Generuj kolor na podstawie pozycji w ścieżce
                    progress = point_idx / max(1, len(robot_path) - 1)
                    r = int(255 * progress)
                    g = int(255 * (1 - progress))
                    b = 128
                    
                    trajectory_point = {
                        "deg": [round(angle, 1) for angle in angles],
                        "ms": int(self.move_time_var.get()),
                        "rgb": {"r": r, "g": g, "b": b}
                    }
                    
                    self.trajectory_points.append(trajectory_point)
                else:
                    failed_points += 1
        
        # Aktualizuj listę ścieżek
        self.paths_listbox.delete(0, tk.END)
        for i, point in enumerate(self.trajectory_points):
            angles_str = ', '.join([f"{a:.1f}°" for a in point["deg"]])
            rgb_str = f"RGB({point['rgb']['r']},{point['rgb']['g']},{point['rgb']['b']})"
            self.paths_listbox.insert(tk.END, f"Punkt {i+1}: [{angles_str}] {rgb_str}")
        
        success_points = len(self.trajectory_points)
        self.path_status_label.config(
            text=f"✅ {success_points} punktów, {failed_points} błędów", 
            foreground="green" if failed_points == 0 else "orange"
        )
        
        self.log_message(f"🗺️ Trajektoria gotowa: {success_points} punktów, {failed_points} błędów")
    
    def preview_paths(self):
        """Podgląd ścieżek (do implementacji)"""
        self.log_message("📊 Podgląd ścieżek - w trakcie implementacji")
        messagebox.showinfo("Info", "Podgląd 3D będzie dodany w przyszłej wersji")
    
    # ===== METODY STEROWANIA ESP32 =====
    
    def test_connection(self):
        """Testuje połączenie z ESP32"""
        self.log_message("🏓 Testowanie połączenia z ESP32...")
        self.esp32_client.send_command("ping", {})
    
    def send_home(self):
        """Wysyła robota do pozycji domowej"""
        self.log_message("🏠 Wysyłanie do pozycji domowej...")
        home_params = {
            "ms": 2000,
            "led": 64,
            "rgb": {"r": 0, "g": 255, "b": 0}
        }
        self.esp32_client.send_command("home", home_params)
    
    def execute_light_painting(self):
        """Wykonuje light painting na podstawie trajektorii"""
        if not self.trajectory_points:
            self.log_message("❌ Brak trajektorii do wykonania - najpierw wygeneruj ścieżki")
            messagebox.showwarning("Błąd", "Brak trajektorii do wykonania!")
            return
        
        if not self.esp32_client.connected:
            self.log_message("❌ Brak połączenia z ESP32")
            messagebox.showwarning("Błąd", "Brak połączenia z ESP32!")
            return
        
        # Ograniczenie do pierwszych 20 punktów (limit ESP32)
        points_to_send = self.trajectory_points[:20]
        
        trajectory_params = {"points": points_to_send}
        
        self.log_message(f"🎨 Rozpoczynanie Light Painting: {len(points_to_send)} punktów")
        self.esp32_client.send_command("trajectory", trajectory_params)
    
    def stop_execution(self):
        """Zatrzymuje wykonywanie trajektorii"""
        self.log_message("⏸️ Zatrzymywanie wykonania...")
        # Wyślij komendę home jako zatrzymanie
        self.send_home()
    
    def send_manual_position(self):
        """Wysyła ręcznie ustawioną pozycję"""
        try:
            angles = []
            for var in self.servo_vars:
                angles.append(float(var.get()))
            
            frame_params = {
                "deg": angles,
                "ms": int(self.move_time_var.get()),
                "led": int(self.led_brightness_var.get()),
                "rgb": {"r": 255, "g": 255, "b": 255}
            }
            
            self.log_message(f"📤 Wysyłanie pozycji: {angles}")
            self.esp32_client.send_command("frame", frame_params)
            
        except ValueError as e:
            self.log_message(f"❌ Błąd danych serw: {e}")
    
    def test_rgb(self):
        """Testuje diodę RGB"""
        import random
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        
        rgb_params = {"r": r, "g": g, "b": b}
        self.log_message(f"🎨 Test RGB: ({r}, {g}, {b})")
        self.esp32_client.send_command("rgb", rgb_params)
    
    def get_status(self):
        """Pobiera status robota"""
        self.log_message("📊 Pobieranie statusu robota...")
        self.esp32_client.send_command("status", {})
    
    # ===== METODY POMOCNICZE =====
    
    def update_connection_status(self, connected):
        """Aktualizuje status połączenia"""
        if connected:
            self.connection_label.config(text="🟢 POŁĄCZONY", foreground="green")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✓", foreground="green")
        else:
            self.connection_label.config(text="🔴 ROZŁĄCZONY", foreground="red")
            self.connection_details.config(text=f"ESP32: {HOST}:{PORT} ✗", foreground="red")
    
    def log_message(self, message):
        """Dodaje wiadomość do logów"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.insert(tk.END, formatted_message + "\\n")
        self.log_text.see(tk.END)
        
        # Ogranicz liczbę linii w logach
        lines = self.log_text.get(1.0, tk.END).split('\\n')
        if len(lines) > 1000:
            self.log_text.delete(1.0, f"{len(lines) - 500}.0")
    
    def clear_logs(self):
        """Czyści logi"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("🗑️ Logi wyczyszczone")

if __name__ == "__main__":
    # Sprawdź czy wszystkie wymagane biblioteki są dostępne
    missing_libs = []
    
    try:
        import cv2
    except ImportError:
        missing_libs.append("opencv-python")
    
    try:
        import websockets
    except ImportError:
        missing_libs.append("websockets")
    
    try:
        import matplotlib
    except ImportError:
        missing_libs.append("matplotlib")
    
    if missing_libs:
        print(f"❌ Brakuje bibliotek: {', '.join(missing_libs)}")
        print("Zainstaluj je poleceniem: pip install " + " ".join(missing_libs))
        exit(1)
    
    # Uruchom aplikację
    print("🎨 Uruchamianie REREZONANS - Light Painting Robot")
    app = IntegratedApp()
    app.mainloop()

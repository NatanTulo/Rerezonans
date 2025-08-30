#!/usr/bin/env python3
"""
🎨 REREZONANS - Light Painting Simulator
Symulacja kompletnego systemu light painting bez ESP32

Bazuje na pracy zespołu z hackatonu:
- ikpy_vis.py (wizualizacja 3D robota)
- kontury.py (interaktywne rysowanie konturów)
- calcDegrees.py (kinematyka odwrotna)

Dodatkowo symuluje kropki light painting z długim naświetlaniem
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import cv2 as cv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import time
import threading
from matplotlib.patches import Circle
import colorsys

# Próba importu ikpy
try:
    import ikpy.chain
    from ikpy.link import DHLink, OriginLink
    IKPY_AVAILABLE = True
except ImportError:
    IKPY_AVAILABLE = False
    print("⚠️ UWAGA: Biblioteka ikpy niedostępna - używamy prostszej kinematyki")

PI = np.pi

# ===== STAŁE KONFIGURACYJNE =====
# Dokładność przetwarzania - im mniejsza wartość, tym więcej punktów
CONTOUR_APPROXIMATION_FACTOR = 0.05  # Oryginalnie 0.02 - zwiększone dla uproszczenia
EDGE_POINT_STEP = 1  # Co ile punktów brać z konturów (1 = wszystkie, 3 = co trzeci)
MAX_POINTS_PER_PATH = 1000  # Maksymalna liczba punktów na ścieżkę

class RobotKinematics:
    """Kinematyka robota PUMA (z calcDegrees.py i ikpy_vis.py)"""
    
    def __init__(self):
        self.chain = None
        
        # Parametry robota z istniejących plików
        self.L1, self.L2, self.L3, self.L4, self.L5 = 1, 1, 1, 1, 1
        self.alpha1, self.alpha2, self.alpha3, self.alpha4, self.alpha5 = PI/2, 0, -PI/2, 0, PI/2
        self.lam1, self.lam2, self.lam3, self.lam4, self.lam5 = 0, self.L2, 0, 0, self.L3
        self.del1, self.del2, self.del3, self.del4, self.del5 = self.L1, 0, self.L3, self.L4, 0
        
        if IKPY_AVAILABLE:
            try:
                # Definicja łańcucha (z ikpy_vis.py)
                self.chain = ikpy.chain.Chain([
                    OriginLink(),
                    DHLink(name="joint_1", d=self.del1, a=self.lam1, alpha=self.alpha1, bounds=(-PI/2, PI/2)),
                    DHLink(name="joint_2", d=self.del2, a=self.lam2, alpha=self.alpha2, bounds=(-PI/2, PI/2)),
                    DHLink(name="joint_3", d=self.del3, a=self.lam3, alpha=self.alpha3, bounds=(-PI/2, PI/2)),
                    DHLink(name="joint_4", d=self.del4, a=self.lam4, alpha=self.alpha4, bounds=(-PI/2, PI/2)),
                    DHLink(name="joint_5", d=self.del5, a=self.lam5, alpha=self.alpha5, bounds=(-PI/2, PI/2))
                ])
            except Exception as e:
                print(f"❌ Błąd ikpy: {e}")
                self.chain = None
    
    def get_joint_positions_manual(self, angles):
        """Ręczne obliczanie pozycji przegubów (z ikpy_vis.py)"""
        positions = []
        current_transform = np.eye(4)
        
        # Pozycja bazowa
        positions.append(current_transform[:3, 3].copy())
        
        # Parametry DH dla każdego jointa
        dh_params = [
            (self.del1, self.lam1, self.alpha1),  # joint 1
            (self.del2, self.lam2, self.alpha2),  # joint 2
            (self.del3, self.lam3, self.alpha3),  # joint 3
            (self.del4, self.lam4, self.alpha4),  # joint 4
            (self.del5, self.lam5, self.alpha5)   # joint 5
        ]
        
        for i, (d, a, alpha) in enumerate(dh_params):
            if i + 1 < len(angles):  # Pomijamy OriginLink
                theta = angles[i + 1]
                
                # Ręczna macierz DH
                cos_theta = np.cos(theta)
                sin_theta = np.sin(theta)
                cos_alpha = np.cos(alpha)
                sin_alpha = np.sin(alpha)
                
                dh_matrix = np.array([
                    [cos_theta, -sin_theta * cos_alpha,  sin_theta * sin_alpha, a * cos_theta],
                    [sin_theta,  cos_theta * cos_alpha, -cos_theta * sin_alpha, a * sin_theta],
                    [0,          sin_alpha,             cos_alpha,             d],
                    [0,          0,                     0,                     1]
                ])
                
                current_transform = current_transform @ dh_matrix
                positions.append(current_transform[:3, 3].copy())
        
        return np.array(positions)
    
    def calculate_inverse_kinematics(self, target_position):
        """Oblicza kinematykę odwrotną"""
        if self.chain is not None:
            # Użyj ikpy jeśli dostępne
            initial_position = [0, 0, 0, 0, 0, 0]
            try:
                joint_angles = self.chain.inverse_kinematics(target_position, initial_position=initial_position)
                angles_deg = [np.degrees(angle) for angle in joint_angles[1:]]
                result_position = self.chain.forward_kinematics(joint_angles)
                error = np.linalg.norm(np.array(target_position) - result_position[:3, 3])
                return angles_deg, result_position[:3, 3], error
            except Exception as e:
                return None, None, f"Błąd ikpy: {e}"
        else:
            # Prosta aproksymacja geometryczna
            x, y, z = target_position
            
            # Proste przybliżenie kątów (dla demonstracji)
            theta1 = np.degrees(np.arctan2(y, x))
            r = np.sqrt(x**2 + y**2)
            theta2 = np.degrees(np.arctan2(z - self.L1, r))
            theta3 = np.degrees(-np.pi/4)  # Przykładowy kąt
            theta4 = np.degrees(np.pi/6)   # Przykładowy kąt
            theta5 = np.degrees(0)         # Przykładowy kąt
            
            angles = [theta1, theta2, theta3, theta4, theta5]
            
            # Przybliżona pozycja końcowa
            approx_pos = [x * 0.9, y * 0.9, z * 0.9]  # Nie idealnie dokładne
            error = np.linalg.norm(np.array(target_position) - np.array(approx_pos))
            
            return angles, approx_pos, error

class ImageProcessor:
    """Przetwarzanie obrazu (z kontury.py)"""
    
    def __init__(self):
        self.current_image = None
        self.contours = []
        self.edge_paths = []
        self.edge_colors = []  # Kolory dla każdej ścieżki krawędzi
        
    def load_image(self, image_path):
        """Wczytuje obraz"""
        try:
            self.current_image = cv.imread(image_path)
            if self.current_image is None:
                return False, "Nie można wczytać obrazu"
            return True, "Obraz wczytany pomyślnie"
        except Exception as e:
            return False, f"Błąd: {e}"
    
    def process_image_interactive(self):
        """Interaktywne rysowanie konturów (z kontury.py) z obsługą błędów"""
        if self.current_image is None:
            return False, "Brak wczytanego obrazu"
        
        try:
            # Sprawdź czy można utworzyć okno OpenCV
            try:
                # Test okna
                test_img = np.zeros((100, 100, 3), dtype=np.uint8)
                cv.namedWindow("test_window", cv.WINDOW_NORMAL)
                cv.imshow("test_window", test_img)
                cv.waitKey(1)
                cv.destroyWindow("test_window")
            except Exception as e:
                # Fallback - użyj prostego automatycznego wykrywania
                return self.process_image_auto_fallback()
            
            # Kod z kontury.py - interaktywne rysowanie
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
                    if len(current) > 1:
                        cv.line(temp, current[-2], current[-1], (0, 255, 0), 2)
                elif evt == cv.EVENT_LBUTTONUP:
                    drawing = False
                    if len(current) > 2:
                        all_contours.append(np.array(current, dtype=np.int32))
            
            # Różne próby utworzenia okna
            window_name = "🎨 Rysuj kontury (ENTER=OK, BACKSPACE=usuń)"
            try:
                cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                cv.setMouseCallback(window_name, on_mouse)
            except:
                # Spróbuj prostszą nazwę okna
                window_name = "Rysuj kontury"
                cv.namedWindow(window_name, cv.WINDOW_AUTOSIZE)
                cv.setMouseCallback(window_name, on_mouse)
            
            while True:
                cv.imshow(window_name, temp)
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
                elif k == 27:  # ESC - wyjście
                    break
            
            cv.destroyAllWindows()
            
            # Przetwarzanie konturów (z kontury.py)
            mask = np.zeros(self.current_image.shape[:2], np.uint8)
            for cnt in all_contours:
                cv.fillPoly(mask, [cnt], 255)
            
            roi = cv.bitwise_and(self.current_image, self.current_image, mask=mask)
            roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
            edges = cv.Canny(roi_gray, 100, 200)
            
            # Wyciąganie konturów jako sekwencji punktów z uproszczeniem
            conts, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            
            # Uprość kontury i ogranicz liczbę punktów
            simplified_edge_paths = []
            simplified_edge_colors = []
            
            for cnt in conts:
                # Uprość kontur
                simplified = cv.approxPolyDP(cnt, CONTOUR_APPROXIMATION_FACTOR * cv.arcLength(cnt, True), True)
                points = [tuple(pt[0]) for pt in simplified]
                
                # Ogranicz liczbę punktów
                if len(points) > MAX_POINTS_PER_PATH:
                    step = max(1, len(points) // MAX_POINTS_PER_PATH)
                    points = points[::step]
                
                # Zastosuj dodatkowy krok dla dalszego uproszczenia
                points = points[::EDGE_POINT_STEP]
                
                if len(points) > 2:  # Tylko jeśli ma sens
                    simplified_edge_paths.append(points)
                    
                    # Pobierz kolory z oryginalnego obrazka dla każdego punktu
                    path_colors = []
                    for x, y in points:
                        # Upewnij się, że współrzędne są w granicach obrazka
                        x = max(0, min(x, self.current_image.shape[1] - 1))
                        y = max(0, min(y, self.current_image.shape[0] - 1))
                        
                        # Pobierz kolor BGR z obrazka i zamień na RGB (0-1)
                        bgr_color = self.current_image[y, x]
                        rgb_color = (bgr_color[2] / 255.0, bgr_color[1] / 255.0, bgr_color[0] / 255.0)
                        path_colors.append(rgb_color)
                    
                    simplified_edge_colors.append(path_colors)
            
            self.edge_paths = simplified_edge_paths
            self.edge_colors = simplified_edge_colors
            
            return True, f"Wykryto {len(self.edge_paths)} ścieżek krawędzi"
            
        except Exception as e:
            return False, f"Błąd przetwarzania: {e}"
    
    def process_image_auto_fallback(self):
        """Automatyczne wykrywanie konturów jako fallback"""
        if self.current_image is None:
            # Ostateczny fallback - prosty kwadrat w rozmiarze 640x480
            square_points = [
                (160, 120), (480, 120), 
                (480, 360), (160, 360), (160, 120)
            ]
            self.edge_paths = [square_points]
            return True, "Użyto prostego kształtu jako fallback (brak obrazu)"
            
        try:
            # Konwersja do skali szarości
            gray = cv.cvtColor(self.current_image, cv.COLOR_BGR2GRAY)
            
            # Zastosuj rozmycie Gaussa
            blurred = cv.GaussianBlur(gray, (5, 5), 0)
            
            # Wykrywanie krawędzi metodą Canny
            edges = cv.Canny(blurred, 50, 150)
            
            # Znajdź kontury
            contours, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            
            # Filtruj małe kontury
            min_area = 500
            filtered_contours = [cnt for cnt in contours if cv.contourArea(cnt) > min_area]
            
            # Konwertuj do formatu używanego w aplikacji z uproszczeniem
            result_contours = []
            for cnt in filtered_contours:
                # Użyj globalnej stałej dla uproszczenia
                simplified = cv.approxPolyDP(cnt, CONTOUR_APPROXIMATION_FACTOR * cv.arcLength(cnt, True), True)
                points = [(int(point[0][0]), int(point[0][1])) for point in simplified]
                
                # Ogranicz liczbę punktów jeśli za dużo
                if len(points) > MAX_POINTS_PER_PATH:
                    step = max(1, len(points) // MAX_POINTS_PER_PATH)
                    points = points[::step]
                
                result_contours.append(np.array(points, dtype=np.int32))
            
            # Przetwarzanie jak w oryginalnej metodzie
            mask = np.zeros(self.current_image.shape[:2], np.uint8)
            for cnt in result_contours:
                cv.fillPoly(mask, [cnt], 255)
            
            roi = cv.bitwise_and(self.current_image, self.current_image, mask=mask)
            roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
            edges = cv.Canny(roi_gray, 100, 200)
            
            # Wyciąganie konturów jako sekwencji punktów z uproszczeniem
            conts, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            
            # Uprość kontury i ogranicz liczbę punktów (jak wyżej)
            simplified_edge_paths = []
            simplified_edge_colors = []
            
            for cnt in conts:
                # Uprość kontur
                simplified = cv.approxPolyDP(cnt, CONTOUR_APPROXIMATION_FACTOR * cv.arcLength(cnt, True), True)
                points = [tuple(pt[0]) for pt in simplified]
                
                # Ogranicz liczbę punktów
                if len(points) > MAX_POINTS_PER_PATH:
                    step = max(1, len(points) // MAX_POINTS_PER_PATH)
                    points = points[::step]
                
                # Zastosuj dodatkowy krok dla dalszego uproszczenia
                points = points[::EDGE_POINT_STEP]
                
                if len(points) > 2:  # Tylko jeśli ma sens
                    simplified_edge_paths.append(points)
                    
                    # Pobierz kolory z oryginalnego obrazka dla każdego punktu
                    path_colors = []
                    for x, y in points:
                        # Upewnij się, że współrzędne są w granicach obrazka
                        x = max(0, min(x, self.current_image.shape[1] - 1))
                        y = max(0, min(y, self.current_image.shape[0] - 1))
                        
                        # Pobierz kolor BGR z obrazka i zamień na RGB (0-1)
                        bgr_color = self.current_image[y, x]
                        rgb_color = (bgr_color[2] / 255.0, bgr_color[1] / 255.0, bgr_color[0] / 255.0)
                        path_colors.append(rgb_color)
                    
                    simplified_edge_colors.append(path_colors)
            
            self.edge_paths = simplified_edge_paths
            self.edge_colors = simplified_edge_colors
            
            print(f"Automatycznie wykryto {len(self.edge_paths)} ścieżek krawędzi")
            return True, f"Automatycznie wykryto {len(self.edge_paths)} ścieżek"
            
        except Exception as e:
            print(f"Błąd podczas automatycznego wykrywania: {e}")
            # Ostateczny fallback - prosty kwadrat
            h, w = self.current_image.shape[:2] if self.current_image is not None else (480, 640)
            square_points = [
                (w//4, h//4), (3*w//4, h//4), 
                (3*w//4, 3*h//4), (w//4, 3*h//4), (w//4, h//4)
            ]
            self.edge_paths = [square_points]
            # Domyślne kolory dla fallback
            default_colors = [(1.0, 1.0, 1.0)] * len(square_points)  # Białe kropki
            self.edge_colors = [default_colors]
            return True, "Użyto prostego kształtu jako fallback"
    
    def convert_to_robot_coordinates(self, scale_factor=0.01, offset_x=0, offset_y=0, offset_z=0.5):
        """Konwertuje piksele na współrzędne robota wraz z kolorami"""
        robot_paths = []
        robot_colors = []
        
        for path_idx, path in enumerate(self.edge_paths):
            robot_path = []
            path_colors = self.edge_colors[path_idx] if path_idx < len(self.edge_colors) else []
            
            for point_idx, (x, y) in enumerate(path):
                # Konwersja na płaszczyznę pionową XZ (obraz rysowany pionowo przed robotem)
                robot_x = (x * scale_factor) + offset_x  # X pozostaje bez zmian
                robot_y = offset_y  # Y to stała odległość od robota (przed nim)
                robot_z = -(y * scale_factor) + offset_z  # Y z obrazka staje się Z (odwrócone dla prawidłowej orientacji)
                
                robot_path.append([robot_x, robot_y, robot_z])
            
            robot_paths.append(robot_path)
            robot_colors.append(path_colors)
        
        return robot_paths, robot_colors

class LightPaintingSimulator(tk.Tk):
    """Główna aplikacja symulatora light painting"""
    
    def __init__(self):
        super().__init__()
        self.title("🎨 REREZONANS - Light Painting Simulator (bez ESP32)")
        self.geometry("1400x1000")
        
        # Komponenty
        self.kinematics = RobotKinematics()
        self.image_processor = ImageProcessor()
        
        # Stan symulacji
        self.robot_paths = []
        self.robot_colors = []  # Kolory dla każdej ścieżki
        self.trajectory_points = []
        self.light_painting_dots = []  # Kropki light painting (2D)
        self.light_painting_3d_dots = []  # Kropki light painting (3D)
        self.light_painting_lines_2d = []  # Linie light painting (2D)
        self.light_painting_lines_3d = []  # Linie light painting (3D)
        self.simulation_running = False
        self.animation = None
        
        # Matplotlib figures
        self.robot_fig = None
        self.robot_ax = None
        self.painting_fig = None
        self.painting_ax = None
        
        self.create_widgets()
        self.setup_robot_visualization()
        self.setup_light_painting_canvas()
        
    def create_widgets(self):
        """Tworzy interfejs użytkownika"""
        
        # ===== GÓRNA SEKCJA - KONTROLE =====
        control_frame = ttk.LabelFrame(self, text="🎮 Kontrole symulacji", padding=10)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        # Przycisk wczytywania obrazu
        ttk.Button(control_frame, text="📁 Wczytaj obraz", command=self.load_image).pack(side="left", padx=5)
        ttk.Button(control_frame, text="✏️ Rysuj kontury", command=self.process_image).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🚀 Start Light Painting", command=self.start_simulation).pack(side="left", padx=5)
        ttk.Button(control_frame, text="⏸️ Stop", command=self.stop_simulation).pack(side="left", padx=5)
        ttk.Button(control_frame, text="🗑️ Wyczyść", command=self.clear_simulation).pack(side="left", padx=5)
        
        # Status
        self.status_label = ttk.Label(control_frame, text="Gotowy do rozpoczęcia", foreground="green")
        self.status_label.pack(side="right", padx=20)
        
        # ===== PARAMETRY KONWERSJI =====
        params_frame = ttk.LabelFrame(self, text="⚙️ Parametry", padding=10)
        params_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Linia parametrów
        param_line = ttk.Frame(params_frame)
        param_line.pack(fill="x")
        
        ttk.Label(param_line, text="Skala:").pack(side="left")
        self.scale_var = tk.StringVar(value="0.005")
        ttk.Entry(param_line, textvariable=self.scale_var, width=8).pack(side="left", padx=(5, 15))
        
        ttk.Label(param_line, text="Offset X:").pack(side="left")
        self.offset_x_var = tk.StringVar(value="0.5")
        ttk.Entry(param_line, textvariable=self.offset_x_var, width=8).pack(side="left", padx=(5, 15))
        
        ttk.Label(param_line, text="Offset Y (odległość):").pack(side="left")
        self.offset_y_var = tk.StringVar(value="1.5")
        ttk.Entry(param_line, textvariable=self.offset_y_var, width=8).pack(side="left", padx=(5, 15))
        
        ttk.Label(param_line, text="Wysokość Z (centrum):").pack(side="left")
        self.offset_z_var = tk.StringVar(value="2.0")
        ttk.Entry(param_line, textvariable=self.offset_z_var, width=8).pack(side="left", padx=(5, 15))
        
        # Szybkie ustawienia pozycji
        quick_pos_frame = ttk.Frame(param_line)
        quick_pos_frame.pack(side="left", padx=(10, 15))
        ttk.Label(quick_pos_frame, text="Szybkie pozycje:").pack(side="top")
        quick_buttons_frame = ttk.Frame(quick_pos_frame)
        quick_buttons_frame.pack(side="top")
        
        ttk.Button(quick_buttons_frame, text="Blisko", width=6, 
                  command=lambda: self.set_quick_position(0.2)).pack(side="left", padx=1)
        ttk.Button(quick_buttons_frame, text="Średnio", width=6,
                  command=lambda: self.set_quick_position(0.5)).pack(side="left", padx=1)
        ttk.Button(quick_buttons_frame, text="Daleko", width=6,
                  command=lambda: self.set_quick_position(1.0)).pack(side="left", padx=1)
        
        ttk.Label(param_line, text="Prędkość:").pack(side="left")
        self.speed_var = tk.StringVar(value="50")
        ttk.Entry(param_line, textvariable=self.speed_var, width=8).pack(side="left", padx=(5, 15))
        
        ttk.Label(param_line, text="Dokładność:").pack(side="left")
        self.accuracy_var = tk.StringVar(value="Normalna")
        accuracy_combo = ttk.Combobox(param_line, textvariable=self.accuracy_var, width=10, values=["Wysoka", "Normalna", "Niska"])
        accuracy_combo.pack(side="left", padx=(5, 15))
        accuracy_combo.bind("<<ComboboxSelected>>", self.on_accuracy_changed)
        
        # ===== GŁÓWNY OBSZAR - WIZUALIZACJE =====
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Lewa strona - Robot 3D
        left_frame = ttk.LabelFrame(main_frame, text="🤖 Symulacja robota 3D", padding=5)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Prawa strona - Light Painting Canvas
        right_frame = ttk.LabelFrame(main_frame, text="🎨 Light Painting (długie naświetlanie)", padding=5)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # Kontenery dla matplotlib
        self.robot_container = left_frame
        self.painting_container = right_frame
        
        # ===== DOLNA SEKCJA - LOGI =====
        log_frame = ttk.LabelFrame(self, text="📝 Logi symulacji", padding=10)
        log_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.log_text = tk.Text(log_frame, height=8, wrap="word", font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")
        
        # Wiadomość powitalna
        self.log_message("🎨 Light Painting Simulator uruchomiony!")
        if IKPY_AVAILABLE:
            self.log_message("✅ Używamy pełnej kinematyki ikpy")
        else:
            self.log_message("⚠️ Używamy uproszczonej kinematyki (brak ikpy)")
    
    def on_accuracy_changed(self, event=None):
        """Obsługuje zmianę poziomu dokładności"""
        global CONTOUR_APPROXIMATION_FACTOR, EDGE_POINT_STEP, MAX_POINTS_PER_PATH
        
        accuracy = self.accuracy_var.get()
        
        if accuracy == "Wysoka":
            CONTOUR_APPROXIMATION_FACTOR = 0.02
            EDGE_POINT_STEP = 1
            MAX_POINTS_PER_PATH = 200
            self.log_message("🔧 Ustawiono wysoką dokładność (więcej punktów, wolniej)")
        elif accuracy == "Normalna":
            CONTOUR_APPROXIMATION_FACTOR = 0.05
            EDGE_POINT_STEP = 3
            MAX_POINTS_PER_PATH = 100
            self.log_message("🔧 Ustawiono normalną dokładność")
        elif accuracy == "Niska":
            CONTOUR_APPROXIMATION_FACTOR = 0.1
            EDGE_POINT_STEP = 5
            MAX_POINTS_PER_PATH = 50
            self.log_message("🔧 Ustawiono niską dokładność (mniej punktów, szybciej)")
    
    def set_quick_position(self, z_value):
        """Szybkie ustawienie pozycji Z"""
        self.offset_z_var.set(str(z_value))
        position_names = {0.2: "blisko", 0.5: "średnio", 1.0: "daleko"}
        name = position_names.get(z_value, "niestandardowo")
        self.log_message(f"📍 Ustawiono pozycję {name} przed robotem (Z = {z_value})")
    
    def setup_robot_visualization(self):
        """Konfiguruje wizualizację 3D robota (z ikpy_vis.py)"""
        # Tworzenie matplotlib figure dla robota
        self.robot_fig = Figure(figsize=(8, 8), dpi=100)
        self.robot_ax = self.robot_fig.add_subplot(111, projection='3d')
        
        # Ustawienia osi (z ikpy_vis.py)
        self.robot_ax.set_xlim(-3, 3)
        self.robot_ax.set_ylim(-3, 3)
        self.robot_ax.set_zlim(-1, 4)
        self.robot_ax.set_xlabel('X [m]')
        self.robot_ax.set_ylabel('Y [m]')
        self.robot_ax.set_zlabel('Z [m]')
        self.robot_ax.view_init(elev=10, azim=0)  # Widok z przodu dla pionowej płaszczyzny XZ
        
        # Elementy wizualizacji robota
        self.robot_links, = self.robot_ax.plot([], [], [], 'b-', linewidth=4, label='Robot links')
        self.robot_joints, = self.robot_ax.plot([], [], [], 'ro', markersize=8, label='Joints')
        self.end_effector, = self.robot_ax.plot([], [], [], 'go', markersize=12, label='End effector')
        
        # LED RGB jako punkt kolorowy
        self.led_point = self.robot_ax.scatter([], [], [], s=200, c='white', marker='*', label='LED RGB')
        
        # Light painting w 3D - zaczynamy z pustą kolekcją
        self.light_painting_3d_scatter = self.robot_ax.scatter([], [], [], s=30, alpha=0.8, label='Light Painting 3D')
        
        self.robot_ax.legend(loc='upper right')
        self.robot_ax.set_title("Robot PUMA - Symulacja 3D")
        
        # Embed w tkinter
        self.robot_canvas = FigureCanvasTkAgg(self.robot_fig, self.robot_container)
        self.robot_canvas.draw()
        self.robot_canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def setup_light_painting_canvas(self):
        """Konfiguruje canvas dla light painting"""
        # Tworzenie matplotlib figure dla light painting
        self.painting_fig = Figure(figsize=(8, 8), dpi=100, facecolor='black')
        self.painting_ax = self.painting_fig.add_subplot(111, facecolor='black')
        
        # Sprawdź czy painting_ax został utworzony
        if self.painting_ax is not None:
            self.painting_ax.set_xlim(-2, 2)  # X pozostaje bez zmian
            self.painting_ax.set_ylim(0, 4)   # Y to teraz Z (wysokość), zakres 0-4
            self.painting_ax.set_aspect('equal')
            self.painting_ax.axis('off')  # Bez osi - jak prawdziwe light painting
            self.painting_ax.set_title("Light Painting - Płaszczyzna pionowa (XZ)", color='white', fontsize=14)
            self.painting_ax.set_xlabel("X", color='white')
            self.painting_ax.set_ylabel("Z (wysokość)", color='white')
        
        # Embed w tkinter
        self.painting_canvas = FigureCanvasTkAgg(self.painting_fig, self.painting_container)
        self.painting_canvas.draw()
        self.painting_canvas.get_tk_widget().pack(fill="both", expand=True)
    
    def load_image(self):
        """Wczytuje obraz do przetwarzania"""
        file_path = filedialog.askopenfilename(
            title="Wybierz obraz do light painting",
            filetypes=[("Obrazy", "*.png *.jpg *.jpeg *.bmp *.tiff"), ("Wszystkie pliki", "*.*")]
        )
        
        if file_path:
            success, message = self.image_processor.load_image(file_path)
            if success:
                self.log_message(f"📁 {message}: {file_path}")
                self.status_label.config(text="Obraz wczytany - możesz rysować kontury", foreground="blue")
            else:
                self.log_message(f"❌ {message}")
                self.status_label.config(text=f"Błąd: {message}", foreground="red")
    
    def process_image(self):
        """Przetwarza obraz - rysowanie konturów (z kontury.py)"""
        if self.image_processor.current_image is None:
            messagebox.showwarning("Błąd", "Najpierw wczytaj obraz!")
            return
        
        self.log_message("✏️ Uruchamianie interaktywnego rysowania konturów...")
        self.status_label.config(text="Rysuj kontury na obrazie...", foreground="orange")
        
        # Uruchom w osobnym wątku żeby nie blokować GUI
        threading.Thread(target=self._process_image_thread, daemon=True).start()
    
    def _process_image_thread(self):
        """Przetwarzanie obrazu w osobnym wątku"""
        success, message = self.image_processor.process_image_interactive()
        
        # Powrót do głównego wątku GUI
        self.after(0, lambda: self._process_image_complete(success, message))
    
    def _process_image_complete(self, success, message):
        """Zakończenie przetwarzania obrazu"""
        if success:
            self.log_message(f"✅ {message}")
            self.convert_to_robot_paths()
            self.status_label.config(text="Kontury gotowe - możesz uruchomić symulację", foreground="green")
        else:
            self.log_message(f"❌ {message}")
            self.status_label.config(text=f"Błąd: {message}", foreground="red")
    
    def convert_to_robot_paths(self):
        """Konwertuje ścieżki obrazu na współrzędne robota"""
        try:
            scale = float(self.scale_var.get())
            offset_x = float(self.offset_x_var.get())
            offset_y = float(self.offset_y_var.get())
            offset_z = float(self.offset_z_var.get())
            
            self.robot_paths, self.robot_colors = self.image_processor.convert_to_robot_coordinates(
                scale, offset_x, offset_y, offset_z
            )
            
            # Generuj trajektorię z kinematyką odwrotną
            self.generate_trajectory()
            
            total_points = sum(len(path) for path in self.robot_paths)
            self.log_message(f"🧮 Konwersja zakończona: {len(self.robot_paths)} ścieżek, {total_points} punktów")
            
        except ValueError as e:
            self.log_message(f"❌ Błąd parametrów: {e}")
    
    def generate_trajectory(self):
        """Generuje trajektorię z kinematyką odwrotną"""
        self.trajectory_points = []
        failed_points = 0
        
        self.log_message("🗺️ Generowanie trajektorii z kinematyką odwrotną...")
        
        for path_idx, robot_path in enumerate(self.robot_paths):
            path_colors = self.robot_colors[path_idx] if path_idx < len(self.robot_colors) else []
            
            for point_idx, position in enumerate(robot_path):
                angles, actual_pos, error = self.kinematics.calculate_inverse_kinematics(position)
                
                if angles is not None and error < 0.1:  # Akceptuj tylko małe błędy
                    # Użyj koloru z obrazka jeśli dostępny, inaczej generuj kolor
                    if point_idx < len(path_colors):
                        color = path_colors[point_idx]
                    else:
                        # Fallback - generuj kolor na podstawie pozycji w ścieżce
                        progress = point_idx / max(1, len(robot_path) - 1)
                        hue = (path_idx * 0.3 + progress * 0.7) % 1.0  # Różne kolory dla ścieżek
                        color = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
                    
                    trajectory_point = {
                        "position": position,
                        "angles": angles,
                        "actual_pos": actual_pos,
                        "rgb": color,
                        "error": error,
                        "path_idx": path_idx,
                        "point_idx": point_idx
                    }
                    
                    self.trajectory_points.append(trajectory_point)
                else:
                    failed_points += 1
        
        success_points = len(self.trajectory_points)
        self.log_message(f"🗺️ Trajektoria gotowa: {success_points} punktów, {failed_points} błędów")
        
        if success_points == 0:
            self.log_message("❌ Brak punktów do wykonania - sprawdź parametry konwersji")
    
    def start_simulation(self):
        """Rozpoczyna symulację light painting"""
        if not self.trajectory_points:
            messagebox.showwarning("Błąd", "Brak trajektorii! Najpierw przetwórz obraz.")
            return
        
        if self.simulation_running:
            self.log_message("⚠️ Symulacja już działa")
            return
        
        self.log_message(f"🚀 Rozpoczynanie symulacji light painting: {len(self.trajectory_points)} punktów")
        self.status_label.config(text="Symulacja w toku...", foreground="orange")
        
        # Wyczyść poprzednie light painting
        self.light_painting_dots.clear()
        self.light_painting_3d_dots.clear()
        self.light_painting_lines_2d.clear()
        self.light_painting_lines_3d.clear()
        if self.painting_ax is not None:
            self.painting_ax.clear()
            self.painting_ax.set_xlim(-2, 2)
            self.painting_ax.set_ylim(0, 4)
            self.painting_ax.set_aspect('equal')
            self.painting_ax.axis('off')
            self.painting_ax.set_facecolor('black')
            self.painting_ax.set_title("Light Painting - Płaszczyzna pionowa (XZ)", color='white', fontsize=14)
        
        self.simulation_running = True
        self.current_point_index = 0
        
        # Uruchom animację
        self.run_animation()
    
    def run_animation(self):
        """Uruchamia animację symulacji"""
        if not self.simulation_running or self.current_point_index >= len(self.trajectory_points):
            self.finish_simulation()
            return
        
        # Pobierz aktualny punkt
        point = self.trajectory_points[self.current_point_index]
        
        # Aktualizuj wizualizację robota
        self.update_robot_visualization(point)
        
        # Dodaj kropkę light painting
        self.add_light_painting_dot(point)
        
        # Następny punkt
        self.current_point_index += 1
        
        # Progress
        progress = (self.current_point_index / len(self.trajectory_points)) * 100
        self.status_label.config(text=f"Symulacja: {progress:.1f}%", foreground="orange")
        
        # Zaplanuj następną klatkę
        speed = int(self.speed_var.get())
        delay = max(10, 200 - speed)  # Im większa prędkość, tym mniejsze opóźnienie
        self.after(delay, self.run_animation)
    
    def update_robot_visualization(self, point):
        """Aktualizuje wizualizację robota"""
        # Oblicz pozycje przegubów dla aktualnych kątów
        angles_rad = [0] + [np.radians(angle) for angle in point["angles"]]  # Dodaj origin
        joint_positions = self.kinematics.get_joint_positions_manual(angles_rad)
        
        # Aktualizuj linie i punkty robota
        self.robot_links.set_data(joint_positions[:, 0], joint_positions[:, 1])
        self.robot_links.set_3d_properties(joint_positions[:, 2])
        
        self.robot_joints.set_data(joint_positions[:, 0], joint_positions[:, 1])
        self.robot_joints.set_3d_properties(joint_positions[:, 2])
        
        # Aktualizuj end effector
        end_pos = joint_positions[-1]
        self.end_effector.set_data([end_pos[0]], [end_pos[1]])
        self.end_effector.set_3d_properties([end_pos[2]])
        
        # Aktualizuj LED RGB (punkt kolorowy)
        led_color = point["rgb"]
        self.led_point._offsets3d = ([end_pos[0]], [end_pos[1]], [end_pos[2]])
        self.led_point.set_color([led_color])
        
        # Odśwież canvas
        self.robot_canvas.draw_idle()
    
    def add_light_painting_dot(self, point):
        """Dodaje kropkę light painting (symulacja długiego naświetlania) i łączy liniami"""
        # Pozycja w przestrzeni 3D
        pos = point["actual_pos"]
        x, y, z = pos[0], pos[1], pos[2]
        
        # Kolor LED
        color = point["rgb"]
        
        # Informacje o ścieżce
        path_idx = point.get("path_idx", 0)
        point_idx = point.get("point_idx", 0)
        
        # 1. Dodaj kropkę do widoku 2D (projekcja XZ - płaszczyzna pionowa)
        circle = Circle((x, z), radius=0.02, color=color, alpha=0.8)  # Używamy X i Z
        if self.painting_ax is not None:
            self.painting_ax.add_patch(circle)
            
            # Dodaj też punkt dla lepszej widoczności
            self.painting_ax.scatter(x, z, s=20, c=[color], alpha=0.9)  # X i Z
        
        # Zapisz do historii 2D (teraz XZ)
        self.light_painting_dots.append((x, z, color, path_idx, point_idx))  # X i Z
        
        # 2. Rysuj linię do poprzedniego punktu tej samej ścieżki
        # Znajdź poprzedni punkt z tej samej ścieżki
        prev_point_2d = None
        prev_point_3d = None
        
        for prev_x, prev_z, prev_color, prev_path_idx, prev_point_idx in reversed(self.light_painting_dots[:-1]):
            if prev_path_idx == path_idx and prev_point_idx == point_idx - 1:
                prev_point_2d = (prev_x, prev_z, prev_color)
                break
        
        for prev_x3d, prev_y3d, prev_z3d, prev_color3d, prev_path_idx3d, prev_point_idx3d in reversed(self.light_painting_3d_dots):
            if prev_path_idx3d == path_idx and prev_point_idx3d == point_idx - 1:
                prev_point_3d = (prev_x3d, prev_y3d, prev_z3d, prev_color3d)
                break
        
        # Dodaj linię 2D jeśli znaleziono poprzedni punkt
        if prev_point_2d and self.painting_ax is not None:
            prev_x, prev_z, prev_color = prev_point_2d
            # Użyj średniego koloru dla linii
            avg_color = [(color[i] + prev_color[i]) / 2 for i in range(3)]
            self.painting_ax.plot([prev_x, x], [prev_z, z], color=avg_color, linewidth=2, alpha=0.7)
            self.light_painting_lines_2d.append(((prev_x, prev_z), (x, z), avg_color))
        
        # 3. Dodaj kropkę do widoku 3D
        self.light_painting_3d_dots.append((x, y, z, color, path_idx, point_idx))
        
        # Dodaj linię 3D jeśli znaleziono poprzedni punkt
        if prev_point_3d:
            prev_x3d, prev_y3d, prev_z3d, prev_color3d = prev_point_3d
            # Użyj średniego koloru dla linii
            avg_color_3d = [(color[i] + prev_color3d[i]) / 2 for i in range(3)]
            
            # Dodaj linię do widoku 3D
            self.robot_ax.plot([prev_x3d, x], [prev_y3d, y], [prev_z3d, z], 
                              color=avg_color_3d, linewidth=2, alpha=0.7)
            self.light_painting_lines_3d.append(((prev_x3d, prev_y3d, prev_z3d), (x, y, z), avg_color_3d))
        
        # Aktualizuj scatter 3D z wszystkimi dotychczasowymi kropkami
        if len(self.light_painting_3d_dots) > 0:
            xs, ys, zs, colors = [], [], [], []
            for x3d, y3d, z3d, color3d, _, _ in self.light_painting_3d_dots:
                xs.append(x3d)
                ys.append(y3d)
                zs.append(z3d)
                colors.append(color3d)
            
            # Usuń stary scatter i dodaj nowy z wszystkimi punktami
            self.light_painting_3d_scatter.remove()
            self.light_painting_3d_scatter = self.robot_ax.scatter(
                xs, ys, zs, s=30, c=colors, alpha=0.8, label='Light Painting 3D'
            )
        
        # Odśwież canvas
        self.painting_canvas.draw_idle()
        self.robot_canvas.draw_idle()
    
    def stop_simulation(self):
        """Zatrzymuje symulację"""
        if self.simulation_running:
            self.simulation_running = False
            self.log_message("⏸️ Symulacja zatrzymana")
            self.status_label.config(text="Symulacja zatrzymana", foreground="red")
    
    def finish_simulation(self):
        """Kończy symulację"""
        self.simulation_running = False
        dots_2d = len(self.light_painting_dots)
        dots_3d = len(self.light_painting_3d_dots)
        lines_2d = len(self.light_painting_lines_2d)
        lines_3d = len(self.light_painting_lines_3d)
        self.log_message(f"✅ Symulacja zakończona! Utworzono {dots_2d} kropek 2D, {dots_3d} kropek 3D, {lines_2d} linii 2D i {lines_3d} linii 3D")
        self.status_label.config(text="Symulacja zakończona", foreground="green")
    
    def clear_simulation(self):
        """Czyści symulację"""
        self.stop_simulation()
        
        # Wyczyść light painting
        self.light_painting_dots.clear()
        self.light_painting_3d_dots.clear()
        self.light_painting_lines_2d.clear()
        self.light_painting_lines_3d.clear()
        
        # Wyczyść 2D canvas
        if self.painting_ax is not None:
            self.painting_ax.clear()
            self.painting_ax.set_xlim(-2, 2)
            self.painting_ax.set_ylim(0, 4)
            self.painting_ax.set_aspect('equal')
            self.painting_ax.axis('off')
            self.painting_ax.set_facecolor('black')
            self.painting_ax.set_title("Light Painting - Płaszczyzna pionowa (XZ)", color='white', fontsize=14)
        self.painting_canvas.draw()
        
        # Wyczyść 3D light painting
        self.light_painting_3d_scatter.remove()
        self.light_painting_3d_scatter = self.robot_ax.scatter([], [], [], s=30, alpha=0.8, label='Light Painting 3D')
        
        # Reset robota do pozycji home
        self.reset_robot_to_home()
        
        self.log_message("🗑️ Symulacja wyczyszczona")
        self.status_label.config(text="Gotowy do rozpoczęcia", foreground="green")
    
    def reset_robot_to_home(self):
        """Resetuje robota do pozycji domowej"""
        home_angles = [0, 0, 0, 0, 0, 0]  # Pozycja home
        joint_positions = self.kinematics.get_joint_positions_manual(home_angles)
        
        # Aktualizuj wizualizację
        self.robot_links.set_data(joint_positions[:, 0], joint_positions[:, 1])
        self.robot_links.set_3d_properties(joint_positions[:, 2])
        
        self.robot_joints.set_data(joint_positions[:, 0], joint_positions[:, 1])
        self.robot_joints.set_3d_properties(joint_positions[:, 2])
        
        end_pos = joint_positions[-1]
        self.end_effector.set_data([end_pos[0]], [end_pos[1]])
        self.end_effector.set_3d_properties([end_pos[2]])
        
        # LED wyłączony (biały)
        self.led_point._offsets3d = ([end_pos[0]], [end_pos[1]], [end_pos[2]])
        self.led_point.set_color(['white'])
        
        self.robot_canvas.draw()
    
    def log_message(self, message):
        """Dodaje wiadomość do logów"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.insert(tk.END, formatted_message + "\n")
        self.log_text.see(tk.END)
        
        # Ogranicz liczbę linii
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 500:
            self.log_text.delete(1.0, f"{len(lines) - 300}.0")

if __name__ == "__main__":
    print("🎨 Uruchamianie Light Painting Simulator...")
    print("📋 Bazuje na pracy zespołu z hackatonu:")
    print("   - ikpy_vis.py (wizualizacja 3D)")
    print("   - kontury.py (interaktywne rysowanie)")
    print("   - calcDegrees.py (kinematyka)")
    print()
    
    # Sprawdź biblioteki
    missing_libs = []
    
    try:
        import cv2
    except ImportError:
        missing_libs.append("opencv-python")
    
    try:
        import matplotlib
    except ImportError:
        missing_libs.append("matplotlib")
    
    if missing_libs:
        print(f"❌ Brakuje bibliotek: {', '.join(missing_libs)}")
        print("Zainstaluj je poleceniem: pip install " + " ".join(missing_libs))
        exit(1)
    
    app = LightPaintingSimulator()
    
    # Ustaw pozycję domową robota na starcie
    app.after(500, app.reset_robot_to_home)
    
    app.mainloop()

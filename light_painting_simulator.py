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

try:
    from scipy import interpolate
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️ UWAGA: Biblioteka scipy niedostępna - używamy prostszej interpolacji")

# ===== STAŁE KONFIGURACYJNE =====
# Dokładność przetwarzania - im mniejsza wartość, tym więcej punktów
# CONTOUR_APPROXIMATION_FACTOR = 0.05  # Oryginalnie 0.02 - zwiększone dla uproszczenia
# EDGE_POINT_STEP = 1  # Co ile punktów brać z konturów (1 = wszystkie, 3 = co trzeci)
# MAX_POINTS_PER_PATH = 1000  # Maksymalna liczba punktów na ścieżkę

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
        """Interaktywne rysowanie konturów z gładkim przetwarzaniem krawędzi"""
        if self.current_image is None:
            return False, "Brak wczytanego obrazu"
        
        try:
            # Test OpenCV window capability
            try:
                test_img = np.zeros((100, 100, 3), dtype=np.uint8)
                cv.namedWindow("test_window", cv.WINDOW_NORMAL)
                cv.imshow("test_window", test_img)
                cv.waitKey(1)
                cv.destroyWindow("test_window")
            except Exception as e:
                return self.process_image_auto_fallback()
            
            # Interactive contour drawing (keep existing code)
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
            
            window_name = "Rysuj kontury (ENTER=OK, BACKSPACE=usuń)"
            try:
                cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                cv.setMouseCallback(window_name, on_mouse)
            except:
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
                elif k == 27:  # ESC
                    break
            
            cv.destroyAllWindows()
            
            # CHANGED: Improved edge processing
            mask = np.zeros(self.current_image.shape[:2], np.uint8)
            if all_contours:
                for cnt in all_contours:
                    cv.fillPoly(mask, [cnt], 255)
            else:
                mask.fill(255)  # Use entire image if no contours drawn
            
            # Process entire image with Canny
            gray = cv.cvtColor(self.current_image, cv.COLOR_BGR2GRAY)
            edges = cv.Canny(gray, 100, 200)
            
            # Apply mask to limit processing area
            masked_edges = cv.bitwise_and(edges, edges, mask=mask)
            
            # CHANGED: Use new smooth edge processing
            self.edge_paths, self.edge_colors = self.process_edges_with_interpolation(
                masked_edges, 
                target_point_density=2.0  # Adjust for smoothness vs performance
            )
            
            return True, f"Wykryto {len(self.edge_paths)} gładkich ścieżek krawędzi"
            
        except Exception as e:
            return False, f"Błąd przetwarzania: {e}"


    def calculate_path_length(self, points_array):
        """Calculate total length of path"""
        if len(points_array) < 2:
            return 0
        
        diffs = np.diff(points_array, axis=0)
        distances = np.sqrt(np.sum(diffs**2, axis=1))
        return np.sum(distances)

    def interpolate_smooth_path(self, points_array, target_point_count):
        """Create smooth interpolated path using spline interpolation"""
        if len(points_array) < 4:
            return points_array
        
        try:
            if SCIPY_AVAILABLE:
                # Calculate cumulative distance along path
                diffs = np.diff(points_array, axis=0)
                distances = np.sqrt(np.sum(diffs**2, axis=1))
                cumulative_distances = np.concatenate([[0], np.cumsum(distances)])
                
                total_length = cumulative_distances[-1]
                if total_length == 0:
                    return points_array
                
                t_original = cumulative_distances / total_length
                
                # Use spline interpolation
                k = min(3, len(points_array) - 1)
                tck, u = interpolate.splprep([points_array[:, 0], points_array[:, 1]], 
                                           s=len(points_array)*0.1, k=k)
                
                # Generate evenly spaced points
                t_new = np.linspace(0, 1, target_point_count)
                x_new, y_new = interpolate.splev(t_new, tck)
                
                smooth_path = np.column_stack([x_new, y_new])
                return smooth_path
            else:
                # Fallback: simple uniform sampling
                if len(points_array) <= target_point_count:
                    return points_array
                indices = np.linspace(0, len(points_array)-1, target_point_count, dtype=int)
                return points_array[indices]
                
        except Exception as e:
            print(f"Interpolation failed: {e}, using fallback")
            # Fallback: simple uniform sampling
            if len(points_array) <= target_point_count:
                return points_array
            indices = np.linspace(0, len(points_array)-1, target_point_count, dtype=int)
            return points_array[indices]

    def process_edges_with_interpolation(self, edges, target_point_density=3.0):
        """Process Canny edges with smooth interpolation instead of crude point deletion"""
        
        # Find contours from Canny edges
        contours, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)
        
        smooth_edge_paths = []
        smooth_edge_colors = []
        
        for cnt in contours:
            # Convert contour to simple point list
            points = [(int(pt[0][0]), int(pt[0][1])) for pt in cnt]
            
            # Skip very small contours
            if len(points) < 10:
                continue
                
            # Remove duplicate consecutive points
            cleaned_points = [points[0]]
            for i in range(1, len(points)):
                if points[i] != points[i-1]:
                    cleaned_points.append(points[i])
            
            if len(cleaned_points) < 3:
                continue
                
            # Convert to numpy arrays for processing
            points_array = np.array(cleaned_points)
            
            # Calculate path length and determine optimal number of points
            path_length = self.calculate_path_length(points_array)
            optimal_point_count = max(10, int(path_length / target_point_density))
            optimal_point_count = min(optimal_point_count, 300)  # Reasonable upper limit
            
            # Create smooth interpolated path
            smooth_path = self.interpolate_smooth_path(points_array, optimal_point_count)
            
            if smooth_path is not None and len(smooth_path) > 2:
                # Convert back to list of tuples
                smooth_points = [(int(x), int(y)) for x, y in smooth_path]
                smooth_edge_paths.append(smooth_points)
                
                # Extract colors from original image at interpolated points
                path_colors = []
                for x, y in smooth_points:
                    # Clamp coordinates to image bounds
                    x = max(0, min(x, self.current_image.shape[1] - 1))
                    y = max(0, min(y, self.current_image.shape[0] - 1))
                    
                    # Get BGR color and convert to RGB (0-1 range)
                    bgr_color = self.current_image[y, x]
                    rgb_color = (bgr_color[2] / 255.0, bgr_color[1] / 255.0, bgr_color[0] / 255.0)
                    path_colors.append(rgb_color)
                
                smooth_edge_colors.append(path_colors)
        
        return smooth_edge_paths, smooth_edge_colors
    def process_image_auto_fallback(self):
        """Automatyczne wykrywanie konturów z gładkim przetwarzaniem"""
        if self.current_image is None:
            # Create smooth ellipse as fallback
            t = np.linspace(0, 2*np.pi, 60)
            center_x, center_y = 320, 240
            radius_x, radius_y = 100, 80
            
            ellipse_points = [
                (int(center_x + radius_x * np.cos(angle)), 
                 int(center_y + radius_y * np.sin(angle))) 
                for angle in t
            ]
            
            self.edge_paths = [ellipse_points]
            default_colors = [(1.0, 1.0, 1.0)] * len(ellipse_points)
            self.edge_colors = [default_colors]
            return True, "Użyto gładkiej elipsy jako fallback"
            
        try:
            # Standard preprocessing
            gray = cv.cvtColor(self.current_image, cv.COLOR_BGR2GRAY)
            blurred = cv.GaussianBlur(gray, (5, 5), 0)
            edges = cv.Canny(blurred, 50, 150)
            
            # CHANGED: Use new smooth edge processing
            self.edge_paths, self.edge_colors = self.process_edges_with_interpolation(
                edges,
                target_point_density=3.0  # Slightly lower density for auto-detection
            )
            
            print(f"Automatycznie wykryto {len(self.edge_paths)} gładkich ścieżek")
            return True, f"Automatycznie wykryto {len(self.edge_paths)} gładkich ścieżek"
            
        except Exception as e:
            print(f"Błąd podczas automatycznego wykrywania: {e}")
            # Fallback to ellipse
            t = np.linspace(0, 2*np.pi, 60)
            center_x = self.current_image.shape[1] // 2
            center_y = self.current_image.shape[0] // 2
            radius_x, radius_y = 100, 80
            
            ellipse_points = [
                (int(center_x + radius_x * np.cos(angle)), 
                 int(center_y + radius_y * np.sin(angle))) 
                for angle in t
            ]
            
            self.edge_paths = [ellipse_points]
            default_colors = [(1.0, 1.0, 1.0)] * len(ellipse_points)
            self.edge_colors = [default_colors]
            return True, "Użyto gładkiej elipsy jako fallback"
        
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
        ttk.Button(control_frame, text="Pokaż wykryte krawędzie", command=self.show_edges).pack(side="left", padx=5)
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
                  command=lambda: self.set_quick_position(0.7)).pack(side="left", padx=1)
        ttk.Button(quick_buttons_frame, text="Średnio", width=6,
                  command=lambda: self.set_quick_position(1.0)).pack(side="left", padx=1)
        ttk.Button(quick_buttons_frame, text="Daleko", width=6,
                  command=lambda: self.set_quick_position(1.5)).pack(side="left", padx=1)
        
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
    
    def show_edges(self):
        """Interaktywny edytor krawędzi z wizualizacją kroków przetwarzania"""
        if self.image_processor.current_image is None:
            messagebox.showwarning("Błąd", "Najpierw wczytaj obraz!")
            return
        
        if not hasattr(self.image_processor, 'edge_paths') or not self.image_processor.edge_paths:
            messagebox.showwarning("Błąd", "Najpierw wykryj krawędzie!")
            return
        
        # Utwórz okno edytora
        self.edges_window = tk.Toplevel(self)
        self.edges_window.title("Interaktywny edytor krawędzi")
        self.edges_window.geometry("1200x800")
        
        # Zmienne stanu edytora
        self.current_step = 0
        self.edit_mode = "view"
        self.selected_edge = None
        self.selected_point = None
        self.show_drawing_order = False
        
        # Inicjalizuj dane
        self.final_edges = [path.copy() for path in self.image_processor.edge_paths]
        self.drawing_order = list(range(len(self.final_edges)))
        
        self.create_editor_interface()
        self.process_all_steps()
        self.show_step(0)  # Zacznij od pierwszego kroku

    def create_editor_interface(self):
        """Tworzy interfejs edytora krawędzi"""
        
        # Status przetwarzania na górze
        status_frame = ttk.Frame(self.edges_window)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        self.processing_status = ttk.Label(status_frame, text="Ładowanie danych...", foreground="orange")
        self.processing_status.pack()
        
        # Panel kontrolny górny
        top_control = ttk.Frame(self.edges_window)
        top_control.pack(fill="x", padx=10, pady=5)
        
        # Nawigacja kroków
        steps_frame = ttk.LabelFrame(top_control, text="Kroki przetwarzania", padding=5)
        steps_frame.pack(side="left", fill="x", expand=True)
        
        self.step_buttons = []
        step_names = ["1. Oryginalny", "2. Maska", "3. Canny", "4. Kontury", "5. Edycja"]
        
        for i, name in enumerate(step_names):
            btn = ttk.Button(steps_frame, text=name, 
                            command=lambda idx=i: self.show_step(idx))
            btn.pack(side="left", padx=2)
            self.step_buttons.append(btn)
        
        # Panel parametrów Canny
        canny_frame = ttk.LabelFrame(top_control, text="Parametry Canny", padding=5)
        canny_frame.pack(side="right", padx=(10, 0))
        
        ttk.Label(canny_frame, text="Dolny:").grid(row=0, column=0, sticky="w")
        self.canny_low_var = tk.IntVar(value=50)
        tk.Scale(canny_frame, from_=10, to=200, variable=self.canny_low_var, 
                orient="horizontal", length=100, command=self.update_canny).grid(row=0, column=1)
        
        ttk.Label(canny_frame, text="Górny:").grid(row=1, column=0, sticky="w")
        self.canny_high_var = tk.IntVar(value=150)
        tk.Scale(canny_frame, from_=50, to=400, variable=self.canny_high_var,
                orient="horizontal", length=100, command=self.update_canny).grid(row=1, column=1)
        
        # Główny obszar z dwoma panelami
        main_area = ttk.Frame(self.edges_window)
        main_area.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Lewy panel - wizualizacja
        viz_frame = ttk.LabelFrame(main_area, text="Wizualizacja", padding=5)
        viz_frame.pack(side="left", fill="both", expand=True)
        
        self.edges_fig = Figure(figsize=(10, 8))
        self.edges_ax = self.edges_fig.add_subplot(111)
        self.edges_canvas = FigureCanvasTkAgg(self.edges_fig, viz_frame)
        self.edges_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Obsługa zdarzeń myszy
        self.edges_canvas.mpl_connect('button_press_event', self.on_canvas_click)
        
        # Prawy panel - kontrole edycji
        edit_frame = ttk.LabelFrame(main_area, text="Edycja krawędzi", padding=5)
        edit_frame.pack(side="right", fill="y", padx=(5, 0))
        edit_frame.configure(width=250)
        
        # Status trybu
        self.mode_label = ttk.Label(edit_frame, text="Tryb: Podgląd", foreground="blue")
        self.mode_label.pack(pady=5)
        
        # Lista krawędzi
        ttk.Label(edit_frame, text="Lista krawędzi:").pack(anchor="w", pady=(10, 2))
        
        listbox_frame = ttk.Frame(edit_frame)
        listbox_frame.pack(fill="x", pady=2)
        
        self.edges_listbox = tk.Listbox(listbox_frame, height=6)
        scrollbar_edges = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.edges_listbox.yview)
        self.edges_listbox.configure(yscrollcommand=scrollbar_edges.set)
        
        self.edges_listbox.pack(side="left", fill="both", expand=True)
        scrollbar_edges.pack(side="right", fill="y")
        self.edges_listbox.bind('<<ListboxSelect>>', self.on_edge_select)
        
        # Przyciski zarządzania krawędziami
        edge_mgmt_frame = ttk.Frame(edit_frame)
        edge_mgmt_frame.pack(fill="x", pady=5)
        
        ttk.Button(edge_mgmt_frame, text="Nowa", width=8,
                command=self.add_new_edge).pack(side="left", padx=1)
        ttk.Button(edge_mgmt_frame, text="Usuń", width=8,
                command=self.delete_selected_edge).pack(side="right", padx=1)
        
        # Tryby edycji punktów
        ttk.Label(edit_frame, text="Tryby edycji:").pack(anchor="w", pady=(15, 2))
        
        modes_frame = ttk.Frame(edit_frame)
        modes_frame.pack(fill="x")
        
        ttk.Button(modes_frame, text="Podgląd", 
                command=lambda: self.set_edit_mode("view")).pack(fill="x", pady=1)
        ttk.Button(modes_frame, text="Dodaj punkt", 
                command=lambda: self.set_edit_mode("add_point")).pack(fill="x", pady=1)
        ttk.Button(modes_frame, text="Usuń punkt", 
                command=lambda: self.set_edit_mode("delete_point")).pack(fill="x", pady=1)
        ttk.Button(modes_frame, text="Wstaw między", 
                command=lambda: self.set_edit_mode("insert_point")).pack(fill="x", pady=1)
        
        # Panel kolejności
        order_frame = ttk.LabelFrame(edit_frame, text="Kolejność", padding=5)
        order_frame.pack(fill="x", pady=(15, 0))
        
        ttk.Button(order_frame, text="Pokaż kolejność", 
                command=self.toggle_order_display).pack(fill="x", pady=1)
        
        order_buttons = ttk.Frame(order_frame)
        order_buttons.pack(fill="x")
        
        ttk.Button(order_buttons, text="↑", width=3,
                command=self.move_selected_up).pack(side="left", padx=1)
        ttk.Button(order_buttons, text="↓", width=3,
                command=self.move_selected_down).pack(side="right", padx=1)
        
        # Dolny panel - zatwierdzenie
        bottom_frame = ttk.Frame(self.edges_window)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(bottom_frame, text="Przelicz ścieżki", 
                command=self.recalculate_paths).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Zatwierdź i zamknij", 
                command=self.confirm_and_close).pack(side="right", padx=5)
        
        # Status
        self.editor_status = ttk.Label(bottom_frame, text="Gotowy")
        self.editor_status.pack(side="right", padx=(0, 20))

    def process_all_steps(self):
        """Przetwarza wszystkie kroki algorytmu"""
        try:
            self.processing_status.config(text="Przetwarzanie kroków...", foreground="orange")
            
            if self.image_processor.current_image is None:
                self.processing_status.config(text="Błąd: Brak obrazu", foreground="red")
                return
            
            # Krok 1: Oryginalny obraz (już mamy)
            
            # Krok 2: Maska obszaru 
            self.area_mask = np.ones(self.image_processor.current_image.shape[:2], np.uint8) * 255
            if hasattr(self.image_processor, 'drawn_contours') and self.image_processor.drawn_contours:
                self.area_mask = np.zeros(self.image_processor.current_image.shape[:2], np.uint8)
                for contour in self.image_processor.drawn_contours:
                    cv.fillPoly(self.area_mask, [contour], 255)
            
            # Krok 3: Filtr Canny
            gray = cv.cvtColor(self.image_processor.current_image, cv.COLOR_BGR2GRAY)
            masked_gray = cv.bitwise_and(gray, gray, mask=self.area_mask)
            self.canny_edges = cv.Canny(masked_gray, self.canny_low_var.get(), self.canny_high_var.get())
            
            # Krok 4: Wykrywanie konturów
            contours, _ = cv.findContours(self.canny_edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            self.detected_contours = [[(int(pt[0][0]), int(pt[0][1])) for pt in cnt] for cnt in contours if len(cnt) > 3]
            
            self.processing_status.config(text=f"Przetworzono {len(self.detected_contours)} konturów", foreground="green")
            
        except Exception as e:
            self.processing_status.config(text=f"Błąd przetwarzania: {e}", foreground="red")
            print(f"Błąd w process_all_steps: {e}")

    def show_step(self, step):
        """Pokazuje określony krok przetwarzania"""
        self.current_step = step
        
        # Podświetl aktywny przycisk
        for i, btn in enumerate(self.step_buttons):
            btn.configure(style="TButton")
        self.step_buttons[step].configure(style="Accent.TButton")
        
        self.update_step_display()

    def update_step_display(self):
        """Aktualizuje wyświetlanie aktualnego kroku"""
        if not hasattr(self, 'edges_ax'):
            return
            
        self.edges_ax.clear()
        
        try:
            if self.current_step == 0:  # Oryginalny obraz
                img_rgb = cv.cvtColor(self.image_processor.current_image, cv.COLOR_BGR2RGB)
                self.edges_ax.imshow(img_rgb)
                self.edges_ax.set_title("Oryginalny obraz")
                
            elif self.current_step == 1:  # Maska obszaru
                if hasattr(self, 'area_mask'):
                    self.edges_ax.imshow(self.area_mask, cmap='gray')
                    self.edges_ax.set_title("Maska obszaru do przetwarzania")
                
            elif self.current_step == 2:  # Filtr Canny
                if hasattr(self, 'canny_edges'):
                    self.edges_ax.imshow(self.canny_edges, cmap='gray')
                    self.edges_ax.set_title(f"Filtr Canny ({self.canny_low_var.get()}, {self.canny_high_var.get()})")
                
            elif self.current_step == 3:  # Wykryte kontury
                if hasattr(self, 'detected_contours'):
                    img_rgb = cv.cvtColor(self.image_processor.current_image, cv.COLOR_BGR2RGB)
                    self.edges_ax.imshow(img_rgb, alpha=0.5)
                    
                    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown']
                    for i, contour in enumerate(self.detected_contours):
                        if len(contour) > 1:
                            x_coords = [p[0] for p in contour]
                            y_coords = [p[1] for p in contour]
                            color = colors[i % len(colors)]
                            self.edges_ax.plot(x_coords, y_coords, color=color, linewidth=2, 
                                            label=f'Kontur {i+1}' if i < 10 else None)
                    
                    self.edges_ax.set_title(f"Wykryte kontury ({len(self.detected_contours)})")
                    if len(self.detected_contours) <= 10:
                        self.edges_ax.legend()
                        
            elif self.current_step == 4:  # Finalne krawędzie
                self.display_final_edges()
            
            self.edges_ax.axis('equal')
            self.edges_ax.set_xlim(0, self.image_processor.current_image.shape[1])
            self.edges_ax.set_ylim(self.image_processor.current_image.shape[0], 0)
            
        except Exception as e:
            self.edges_ax.text(0.5, 0.5, f"Błąd wyświetlania: {e}", 
                            transform=self.edges_ax.transAxes, ha='center', va='center')
            print(f"Błąd w update_step_display: {e}")
            
        self.edges_canvas.draw()

    def display_final_edges(self):
        """Wyświetla finalne krawędzie z możliwością edycji"""
        if self.image_processor.current_image is not None:
            img_rgb = cv.cvtColor(self.image_processor.current_image, cv.COLOR_BGR2RGB)
            self.edges_ax.imshow(img_rgb, alpha=0.3)
        
        colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
        
        # Wyczyść i aktualizuj listę krawędzi
        self.edges_listbox.delete(0, tk.END)
        
        for i, edge_idx in enumerate(self.drawing_order):
            if edge_idx < len(self.final_edges):
                edge = self.final_edges[edge_idx]
                color = colors[edge_idx % len(colors)]
                
                if len(edge) > 1:
                    x_coords = [p[0] for p in edge]
                    y_coords = [p[1] for p in edge]
                    
                    # Podświetl wybraną krawędź
                    linewidth = 3 if edge_idx == self.selected_edge else 2
                    alpha = 1.0 if edge_idx == self.selected_edge else 0.7
                    
                    self.edges_ax.plot(x_coords, y_coords, color=color, 
                                    linewidth=linewidth, alpha=alpha)
                    
                    # Pokaż punkty w trybie edycji
                    if self.edit_mode != "view" and edge_idx == self.selected_edge:
                        self.edges_ax.scatter(x_coords, y_coords, c=color, s=50, 
                                            edgecolors='white', linewidths=2, zorder=5)
                        
                        # Numeruj punkty
                        for j, (x, y) in enumerate(edge):
                            self.edges_ax.annotate(str(j), (x, y), xytext=(5, 5), 
                                                textcoords='offset points', fontsize=10,
                                                bbox=dict(boxstyle='round,pad=0.2', 
                                                        facecolor='white', alpha=0.9),
                                                zorder=6)
                
                # Dodaj do listy
                self.edges_listbox.insert(tk.END, f"Krawędź {edge_idx+1} ({len(edge)} pkt)")
        
        # Pokaż kolejność jeśli włączona
        if self.show_drawing_order:
            for i, edge_idx in enumerate(self.drawing_order):
                if edge_idx < len(self.final_edges) and len(self.final_edges[edge_idx]) > 0:
                    start_point = self.final_edges[edge_idx][0]
                    self.edges_ax.text(start_point[0], start_point[1], str(i+1), 
                                    fontsize=14, fontweight='bold',
                                    bbox=dict(boxstyle="circle,pad=0.3", 
                                            facecolor='yellow', alpha=0.9),
                                    ha='center', va='center', zorder=7)
        
        self.edges_ax.set_title(f"Finalne krawędzie - {self.edit_mode}")

    # Dodaj podstawowe metody obsługi
    def update_canny(self, event=None):
        """Aktualizuje filtr Canny"""
        if hasattr(self, 'current_step'):
            self.process_all_steps()
            if self.current_step in [2, 3]:
                self.update_step_display()

    def set_edit_mode(self, mode):
        """Ustawia tryb edycji"""
        self.edit_mode = mode
        mode_texts = {
            "view": "Podgląd",
            "add_point": "Dodaj punkt",
            "delete_point": "Usuń punkt", 
            "insert_point": "Wstaw punkt"
        }
        
        self.mode_label.config(text=f"Tryb: {mode_texts.get(mode, mode)}")
        
        if self.current_step == 4:
            self.update_step_display()

    def on_canvas_click(self, event):
        """Obsługuje kliknięcia na canvas"""
        # Sprawdź czy jesteśmy w oknie edytora i czy mamy odpowiednie atrybuty
        if not hasattr(self, 'edit_mode') or not hasattr(self, 'edges_ax'):
            return
            
        if event.inaxes != self.edges_ax or event.xdata is None or event.ydata is None:
            return
        
        # Sprawdź czy jesteśmy w trybie edycji (używaj edit_mode zamiast editing_mode)
        if self.edit_mode == "view":
            x, y = int(event.xdata), int(event.ydata)
            self.select_nearest_edge(x, y)

    def select_nearest_edge(self, x, y):
        """Wybiera najbliższą krawędź"""
        min_dist = float('inf')
        closest_edge = None
        
        for edge_idx, edge in enumerate(self.final_edges):
            for px, py in edge:
                dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if dist < min_dist and dist < 20:
                    min_dist = dist
                    closest_edge = edge_idx
        
        if closest_edge is not None:
            self.selected_edge = closest_edge
            self.update_step_display()
            self.editor_status.config(text=f"Wybrano krawędź {closest_edge+1}")

    # Podstawowe metody do dokończenia
    def on_edge_select(self, event):
        pass

    def add_new_edge(self):
        pass

    def delete_selected_edge(self):
        pass

    def toggle_order_display(self):
        self.show_drawing_order = not self.show_drawing_order
        if self.current_step == 4:
            self.update_step_display()

    def move_selected_up(self):
        pass

    def move_selected_down(self):
        pass

    def recalculate_paths(self):
        """Przelicza ścieżki"""
        ordered_edges = [self.final_edges[i] for i in self.drawing_order if i < len(self.final_edges)]
        self.image_processor.edge_paths = ordered_edges
        self.editor_status.config(text=f"Przeliczono {len(ordered_edges)} ścieżek")

    def confirm_and_close(self):
        """Zatwierdza i zamyka"""
        self.recalculate_paths()
        self.log_message(f"Zatwierdzono {len(self.image_processor.edge_paths)} krawędzi z edytora")
        self.edges_window.destroy()
        
    def on_canvas_click(self, event):
        """Obsługuje kliknięcia na canvas"""
        if not self.editing_mode or not self.edit_mode or event.inaxes != self.edges_ax:
            return
        
        x, y = int(event.xdata), int(event.ydata)
        
        # Znajdź najbliższą krawędź i punkt
        min_dist = float('inf')
        closest_edge = None
        closest_point = None
        
        for edge_idx, edge in enumerate(self.final_edges):
            for point_idx, (px, py) in enumerate(edge):
                dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                if dist < min_dist and dist < 20:  # 20 pikseli tolerancji
                    min_dist = dist
                    closest_edge = edge_idx
                    closest_point = point_idx
        
        if closest_edge is not None:
            self.selected_edge = closest_edge
            self.selected_point = closest_point
            self.edges_listbox.selection_clear(0, tk.END)
            
            # Znajdź pozycję w drawing_order
            try:
                list_idx = self.drawing_order.index(closest_edge)
                self.edges_listbox.selection_set(list_idx)
            except ValueError:
                pass
            
            self.update_step_display()
            self.editor_status.config(text=f"Wybrano: krawędź {closest_edge+1}, punkt {closest_point}")

    def recalculate_paths(self):
        """Przelicza ścieżki na podstawie edytowanych krawędzi"""
        # Aktualizuj edge_paths w image_processor
        ordered_edges = [self.final_edges[i] for i in self.drawing_order if i < len(self.final_edges)]
        self.image_processor.edge_paths = ordered_edges
        
        self.editor_status.config(text=f"Przeliczono {len(ordered_edges)} ścieżek")

    def confirm_and_close(self):
        """Zatwierdza zmiany i zamyka edytor"""
        self.recalculate_paths()
        self.log_message(f"Zatwierdzono {len(self.image_processor.edge_paths)} krawędzi z edytora")
        self.edges_window.destroy()

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
        position_names = {0.7: "blisko", 1.0: "średnio", 1.5: "daleko"}
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
            # Ustaw domyślne granice (będą aktualizowane dynamicznie podczas symulacji)
            self.painting_ax.set_xlim(-1.5, 1.5)  
            self.painting_ax.set_ylim(1.0, 4.0)   
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
    
    def calculate_painting_bounds(self):
        """Oblicza dynamiczne granice dla okna light painting na podstawie trajektorii"""
        if not self.trajectory_points:
            # Fallback gdy brak trajektorii
            return -1.5, 1.5, 1.0, 4.0
        
        # Zbierz wszystkie pozycje X i Z
        x_coords = []
        z_coords = []
        
        for point in self.trajectory_points:
            pos = point["actual_pos"]
            x_coords.append(pos[0])  # X
            z_coords.append(pos[2])  # Z (wysokość)
        
        if not x_coords or not z_coords:
            return -1.5, 1.5, 1.0, 4.0
        
        # Znajdź min/max z marginesem
        x_min, x_max = min(x_coords), max(x_coords)
        z_min, z_max = min(z_coords), max(z_coords)
        
        # Dodaj 20% marginesu
        x_margin = max(0.2, (x_max - x_min) * 0.2)
        z_margin = max(0.2, (z_max - z_min) * 0.2)
        
        x_min_bounded = x_min - x_margin
        x_max_bounded = x_max + x_margin
        z_min_bounded = z_min - z_margin
        z_max_bounded = z_max + z_margin
        
        # Upewnij się, że zakres nie jest zbyt mały
        if (x_max_bounded - x_min_bounded) < 0.5:
            center_x = (x_max_bounded + x_min_bounded) / 2
            x_min_bounded = center_x - 0.25
            x_max_bounded = center_x + 0.25
            
        if (z_max_bounded - z_min_bounded) < 0.5:
            center_z = (z_max_bounded + z_min_bounded) / 2
            z_min_bounded = center_z - 0.25
            z_max_bounded = center_z + 0.25
        
        self.log_message(f"📏 Obliczone granice: X({x_min_bounded:.2f}, {x_max_bounded:.2f}), Z({z_min_bounded:.2f}, {z_max_bounded:.2f})")
        
        return x_min_bounded, x_max_bounded, z_min_bounded, z_max_bounded

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
        
        # Oblicz dynamiczne granice na podstawie trajektorii
        x_min, x_max, z_min, z_max = self.calculate_painting_bounds()
        
        if self.painting_ax is not None:
            self.painting_ax.clear()
            self.painting_ax.set_xlim(x_min, x_max)  # Dynamiczny zakres X
            self.painting_ax.set_ylim(z_min, z_max)  # Dynamiczny zakres Z
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
            # Sprawdź czy mamy trajektorię do obliczenia granic
            if hasattr(self, 'trajectory_points') and self.trajectory_points:
                x_min, x_max, z_min, z_max = self.calculate_painting_bounds()
                self.painting_ax.set_xlim(x_min, x_max)
                self.painting_ax.set_ylim(z_min, z_max)
            else:
                # Użyj domyślnych granic gdy brak trajektorii
                self.painting_ax.set_xlim(-1.5, 1.5)
                self.painting_ax.set_ylim(1.0, 4.0)
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

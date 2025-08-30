import cv2
import numpy as np
import matplotlib.pyplot as plt

image = cv2.imread('obrazk.png', cv2.IMREAD_GRAYSCALE)

_, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY_INV)

contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Przekształć obraz do koloru (RGB), by móc rysować kolorowe punkty
color_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

# Lista wektorów (punktów)
vector_paths = []

# Iteruj przez kontury
for contour in contours:
#contour = contours[1]
    path = []
    for point in contour:
        x, y = point[0]
        path.append((x, y))
        print(x, y)
        # Rysuj czerwoną kropkę w miejscu punktu
        cv2.circle(color_image, (x, y), radius=2, color=(0, 0, 255), thickness=-1)
    vector_paths.append(path)

# Wyświetl obraz z czerwonymi punktami
# Konwersja obrazu z BGR (OpenCV) do RGB (matplotlib)
color_image_rgb = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)

# Wyświetlenie obrazu z czerwonymi kropkami
plt.figure(figsize=(10, 10))
plt.imshow(color_image_rgb)
plt.title('Wektory jako czerwone kropki')
plt.axis('off')
plt.show()

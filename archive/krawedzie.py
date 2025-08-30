import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt

img_color = cv.imread("krollew.jpg")
assert img_color is not None, "file could not be read, check with os.path.exists()"
all_contours = []  # lista obrysów
current_contour = []
drawing = False

def draw_free(event, x, y, flags, param):
    global drawing, current_contour, temp_img
    if event == cv.EVENT_LBUTTONDOWN:
        drawing = True
        current_contour = [(x, y)]
    elif event == cv.EVENT_MOUSEMOVE and drawing:
        current_contour.append((x, y))
        cv.circle(temp_img, (x, y), 2, (0, 0, 255), -1)
        if len(current_contour) > 1:
            cv.line(temp_img, current_contour[-2], current_contour[-1], (0, 255, 0), 2)
    elif event == cv.EVENT_LBUTTONUP:
        drawing = False
        if len(current_contour) > 2:
            all_contours.append(np.array(current_contour, dtype=np.int32))

# Kopia do rysowania
temp_img = img_color.copy()

cv.namedWindow("Rysuj kształt (ENTER = zatwierdź)")
cv.setMouseCallback("Rysuj kształt (ENTER = zatwierdź)", draw_free)

while True:
    cv.imshow("Rysuj kształt (ENTER = zatwierdź)", temp_img)
    key = cv.waitKey(1) & 0xFF
    if key == 13:  # ENTER
        break
    elif key == 8:  # BACKSPACE usuwa ostatni obrys
        if all_contours:
            all_contours.pop()
            temp_img = img_color.copy()
            for contour in all_contours:
                for i in range(1, len(contour)):
                    cv.line(temp_img, tuple(contour[i - 1]), tuple(contour[i]), (0, 255, 0), 2)
                    cv.circle(temp_img, tuple(contour[i]), 2, (0, 0, 255), -1)
cv.destroyAllWindows()

# --- Tworzymy maskę ze środkiem ---
mask = np.zeros(img_color.shape[:2], dtype=np.uint8)
for contour in all_contours:
    cv.fillPoly(mask, [contour], 255)
# Wycinamy obszar wnętrza kształtu
roi = cv.bitwise_and(img_color, img_color, mask=mask)
# Zamiana na szarość i wykrywanie krawędzi
roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
edges = cv.Canny(roi_gray, 100, 200)
# Kolorowe krawędzie
color_edges = np.zeros_like(img_color)
color_edges[edges != 0] = img_color[edges != 0]
color_edges = cv.bitwise_and(color_edges, color_edges, mask=mask)

"""Wyswietlanie"""
plt.figure(figsize=(15,6))
plt.subplot(131), plt.imshow(cv.cvtColor(img_color, cv.COLOR_BGR2RGB))
plt.title("Oryginał"), plt.axis("off")
plt.subplot(132), plt.imshow(cv.cvtColor(roi, cv.COLOR_BGR2RGB))
plt.title("Wnętrze rysowanego kształtu"), plt.axis("off")
plt.subplot(133), plt.imshow(cv.cvtColor(color_edges, cv.COLOR_BGR2RGB))
plt.title("Kolorowe krawędzie wewnątrz kształtu"), plt.axis("off")
plt.show()

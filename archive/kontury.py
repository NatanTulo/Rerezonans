import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt

# 1. Wczytanie obrazu
img = cv.imread("krollew.jpg")
assert img is not None, "Nie można wczytać obrazu"

# 2. Interaktywne rysowanie konturów
all_contours = []
current = []
drawing = False

def on_mouse(evt, x, y, flags, param):
    global drawing, current, temp
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

temp = img.copy()
cv.namedWindow("Rysuj (ENTER=OK, BACKSPACE=usuń)")
cv.setMouseCallback("Rysuj (ENTER=OK, BACKSPACE=usuń)", on_mouse)

while True:
    cv.imshow("Rysuj (ENTER=OK, BACKSPACE=usuń)", temp)
    k = cv.waitKey(1) & 0xFF
    if k == 13:    # ENTER
        break
    elif k == 8:   # BACKSPACE
        if all_contours:
            all_contours.pop()
            temp = img.copy()
            for cnt in all_contours:
                for i in range(1, len(cnt)):
                    cv.line(temp, tuple(cnt[i-1]), tuple(cnt[i]), (0,255,0), 2)
                    cv.circle(temp, tuple(cnt[i]), 2, (0,0,255), -1)
cv.destroyAllWindows()

# 3. Tworzenie maski i ROI
mask = np.zeros(img.shape[:2], np.uint8)
for cnt in all_contours:
    cv.fillPoly(mask, [cnt], 255)

roi = cv.bitwise_and(img, img, mask=mask)
roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)

# 4. Canny
edges = cv.Canny(roi_gray, 100, 200)

# 5. Wyciąganie konturów jako sekwencji punktów
conts, _ = cv.findContours(edges, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)
vector_paths = [[tuple(pt[0]) for pt in cnt] for cnt in conts]

# 6. Tworzenie obrazu punktowego
points_img = np.zeros_like(img)
ys, xs = np.where(edges != 0)
for x, y in zip(xs, ys):
    b, g, r = img[y, x]
    cv.circle(points_img, (x, y), radius=2, color=(int(b), int(g), int(r)), thickness=-1)

# 7. Wyświetlenie: oryginał vs same punkty
orig_rgb   = cv.cvtColor(img, cv.COLOR_BGR2RGB)
points_rgb = cv.cvtColor(points_img, cv.COLOR_BGR2RGB)

plt.figure(figsize=(10,5))
plt.subplot(1,2,1)
plt.imshow(orig_rgb);   plt.title("Oryginał");               plt.axis("off")
plt.subplot(1,2,2)
plt.imshow(points_rgb); plt.title("Same punkty krawędzi");   plt.axis("off")
plt.tight_layout()
plt.show()

# 8. Wynik: vector_paths
print(f"Znaleziono {len(vector_paths)} kontur(ów) krawędzi.")
for i, path in enumerate(vector_paths,1):
    print(f"  Ścieżka {i}: {len(path)} punktów")
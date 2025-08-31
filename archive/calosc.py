import ikpy.chain
from ikpy.link import DHLink, OriginLink
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import cv2 as cv

PI = np.pi

# =============================
# === CZĘŚĆ 1: Robot (BEZ ZMIAN)
# =============================

L1, L2, L3, L4, L5 = 1, 1, 1, 1, 1
alpha1, alpha2, alpha3, alpha4, alpha5 = PI / 2, 0, -PI / 2, 0, PI / 2
lam1, lam2, lam3, lam4, lam5 = L1, L2, 0, 0, L3
del1, del2, del3, del4, del5 = L1, 0, L3, L4, 0

my_chain = ikpy.chain.Chain([
    OriginLink(),
    DHLink(name="joint_1", d=del1, a=lam1, alpha=alpha1, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_2", d=del2, a=lam2, alpha=alpha2, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_3", d=del3, a=lam3, alpha=alpha3, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_4", d=del4, a=lam4, alpha=alpha4, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_5", d=del5, a=lam5, alpha=alpha5, bounds=(-PI / 2, PI / 2))
])

def get_joint_positions_manual(angles):
    positions = []
    current_transform = np.eye(4)
    positions.append(current_transform[:3, 3].copy())

    dh_params = [
        (del1, lam1, alpha1),
        (del2, lam2, alpha2),
        (del3, lam3, alpha3),
        (del4, lam4, alpha4),
        (del5, lam5, alpha5)
    ]

    for i, (d, a, alpha) in enumerate(dh_params):
        if i + 1 < len(angles):
            theta = angles[i + 1]
            cos_theta, sin_theta = np.cos(theta), np.sin(theta)
            cos_alpha, sin_alpha = np.cos(alpha), np.sin(alpha)

            dh_matrix = np.array([
                [cos_theta, -sin_theta * cos_alpha, sin_theta * sin_alpha, a * cos_theta],
                [sin_theta, cos_theta * cos_alpha, -cos_theta * sin_alpha, a * sin_theta],
                [0, sin_alpha, cos_alpha, d],
                [0, 0, 0, 1]
            ])
            current_transform = current_transform @ dh_matrix
            positions.append(current_transform[:3, 3].copy())

    return np.array(positions)

# =============================
# === CZĘŚĆ 2: OpenCV – punkty + kolory
# =============================

img = cv.imread("archive/obrazek.png")
assert img is not None, "Nie można wczytać obrazu"

# Maska rysowanego obszaru
all_contours, current, drawing = [], [], False

def on_mouse(evt, x, y, flags, param):
    global drawing, current, temp
    if evt == cv.EVENT_LBUTTONDOWN:
        drawing, current = True, [(x, y)]
    elif evt == cv.EVENT_MOUSEMOVE and drawing:
        current.append((x, y))
        cv.circle(temp, (x, y), 2, (0, 0, 255), -1)
        cv.line(temp, current[-2], current[-1], (0, 255, 0), 2)
    elif evt == cv.EVENT_LBUTTONUP:
        drawing = False
        if len(current) > 2:
            all_contours.append(np.array(current, dtype=np.int32))

temp = img.copy()
window_name = "Rysuj (ENTER=OK, BACKSPACE=usuń)"
cv.namedWindow(window_name, cv.WINDOW_NORMAL)
cv.imshow(window_name, temp)
cv.setMouseCallback(window_name, on_mouse)


while True:
    cv.imshow("Rysuj (ENTER=OK, BACKSPACE=usuń)", temp)
    k = cv.waitKey(1) & 0xFF
    if k == 13: break
    elif k == 8 and all_contours:
        all_contours.pop()
        temp = img.copy()
        for cnt in all_contours:
            for i in range(1, len(cnt)):
                cv.line(temp, tuple(cnt[i-1]), tuple(cnt[i]), (0,255,0), 2)
                cv.circle(temp, tuple(cnt[i]), 2, (0,0,255), -1)
cv.destroyAllWindows()

# Wyciąganie krawędzi
mask = np.zeros(img.shape[:2], np.uint8)
for cnt in all_contours: cv.fillPoly(mask, [cnt], 255)
roi = cv.bitwise_and(img, img, mask=mask)
roi_gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
edges = cv.Canny(roi_gray, 100, 200)

# Punkty + kolory
ys, xs = np.where(edges != 0)
colors_bgr = [img[y, x] for (x, y) in zip(xs, ys)]
# Normalizacja współrzędnych tak, by mieściły się w zadanych zakresach
xs_norm = (xs - xs.min()) / (xs.max() - xs.min())  # [0,1]
ys_norm = (ys - ys.min()) / (ys.max() - ys.min())  # [0,1]

# Skalowanie
xs_scaled = xs_norm * 6 - 3              # X → [-3, 3]
zs_scaled = ys_norm * (4 - 0.1) + 0.1    # Z → [0.1, 4]

points_3d = np.column_stack((xs_scaled, np.full_like(xs_scaled, 2), zs_scaled))

print(points_3d)
colors_rgb = [(c[2]/255, c[1]/255, c[0]/255) for c in colors_bgr]  # BGR→RGB

# Wybieramy co 20-ty punkt (dla szybkości)
targets_list = points_3d[::60]
colors_list = colors_rgb[::60]

print(f"Wyciągnięto {len(targets_list)} punktów do odwiedzenia.")

# =============================
# === CZĘŚĆ 3: Animacja robota
# =============================

initial_position = [0,0,0,0,0,0]
use_manual = True
get_positions = get_joint_positions_manual
num_steps = 15

fig = plt.figure(figsize=(14,10))
ax = fig.add_subplot(111, projection='3d')
xs, ys, zs = zip(*targets_list)
ax.set_xlim(-4,4); ax.set_ylim(-4,4); ax.set_zlim(-1,5)
ax.set_xlabel('X [m]'); ax.set_ylabel('Y [m]'); ax.set_zlabel('Z [m]')
ax.scatter(xs, ys, zs, c=colors_list, marker = 'x')
ax.view_init(elev=25, azim=45)

robot_links, = ax.plot([], [], [], 'b-', linewidth=3)
robot_joints, = ax.plot([], [], [], 'ro', markersize=8)
trail = []

# Trajektorie
all_trajectories, trail_colors = [], []
for target, col in zip(targets_list, colors_list):
    joint_angles_target = my_chain.inverse_kinematics(target, initial_position=initial_position)
    joint_traj = np.array([np.linspace(start, end, num_steps)
                           for start,end in zip(initial_position, joint_angles_target)]).T
    for step in joint_traj:  # zapisz kolor na każdym kroku
        trail_colors.append(col)
    all_trajectories.extend(joint_traj)
    initial_position = joint_angles_target
all_trajectories = np.array(all_trajectories)

def animate(frame):
    current_angles = all_trajectories[frame]
    joint_positions = get_positions(current_angles)

    robot_links.set_data(joint_positions[:,0], joint_positions[:,1])
    robot_links.set_3d_properties(joint_positions[:,2])
    robot_joints.set_data(joint_positions[:,0], joint_positions[:,1])
    robot_joints.set_3d_properties(joint_positions[:,2])

    # Dodaj punkt śladu z kolorem
    ee = joint_positions[-1]
    ax.scatter(ee[0], ee[1], ee[2], color=trail_colors[frame], s=8)

    return [robot_links, robot_joints]

anim = FuncAnimation(fig, animate, frames=len(all_trajectories), interval=50, blit=False, repeat=False)
plt.tight_layout()
plt.show()
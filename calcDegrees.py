import ikpy.chain
from ikpy.link import DHLink, OriginLink
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

PI = np.pi

# Parametry robota
L1, L2, L3, L4, L5 = 1, 1, 1, 1, 1
alpha1, alpha2, alpha3, alpha4, alpha5 = PI / 2, 0, -PI / 2, 0, PI / 2
lam1, lam2, lam3, lam4, lam5 = L1, L2, 0, 0, L3
del1, del2, del3, del4, del5 = L1, 0, L3, L4, 0

my_chain = ikpy.chain.Chain([
    OriginLink(),
    # DHLink(name="joint_0", d=0, a=0, alpha=0, bounds=(-PI/2, PI/2)),
    DHLink(name="joint_1", d=del1, a=lam1, alpha=alpha1, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_2", d=del2, a=lam2, alpha=alpha2, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_3", d=del3, a=lam3, alpha=alpha3, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_4", d=del4, a=lam4, alpha=alpha4, bounds=(-PI / 2, PI / 2)),
    DHLink(name="joint_5", d=del5, a=lam5, alpha=alpha5, bounds=(-PI / 2, PI / 2))
])

# Zadana pozycja docelowa [x, y, z]
target_position = [0.5, 0.2, 0.8]  # przykład: 50cm w przód, 20cm w prawo, 80cm w górę

# Pozycja początkowa (opcjonalna, ale zalecana dla stabilności)
initial_position = [0, 0, 0, 0, 0, 0]  # 6 elementów (OriginLink + 5 jointów)

joint_angles = my_chain.inverse_kinematics(
    target_position, 
    initial_position=initial_position
)

# Wynik: joint_angles to tablica z kątami θ1, θ2, θ3, θ4, θ5
print("Kąty przegubów:", joint_angles)
print("θ1 =", joint_angles[1])
print("θ2 =", joint_angles[2])
print("θ3 =", joint_angles[3])
print("θ4 =", joint_angles[4])
print("θ5 =", joint_angles[5])



# Weryfikacja - kinematyka prosta dla sprawdzenia
result_position = my_chain.forward_kinematics(joint_angles)
print("Rzeczywista pozycja końcówki:")
print(result_position[:3, 3])  # pozycja [x, y, z]
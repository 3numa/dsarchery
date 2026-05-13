# physics.py
# Arrow physics + perspective projection.
#
# Screen-space half-parabola: cursor position is the apex, arrow only falls.
# screen_sy grows monotonically — the upward-bend artifact is impossible.
#
# Draw power: only controls vz (depth reach). Everything else is fixed.
# Wind: screen-space accumulation so drift is visible and predictable.

import math

GRAVITY_SCREEN = 140   # screen-px/sec²
MAX_Z          = 1000
BASE_VZ        = 1100  # wz/sec at 100% draw

# Wind drift coefficient: screen-px per wind-unit per second.
# At wind=10 over a 1s flight this gives ~35px of lateral drift.
WIND_COEFF = 3.5


def project(wx, wy, wz, vp_x, vp_y):
    """Perspective projection. wx/wy are world offsets from the vanishing point."""
    scale = max(0.01, 1.0 - wz / (MAX_Z * 1.4))
    return vp_x + wx * scale, vp_y + wy * scale, scale


class Arrow:

    def __init__(self, mouse_sx, mouse_sy, aim_h, draw_power, vp_x, vp_y):
        self.vp_x = vp_x
        self.vp_y = vp_y

        self.flight_t = 0.0

        # Screen-space apex (where the arrow starts)
        self.start_sx = float(mouse_sx)
        self.start_sy = float(mouse_sy)

        # World horizontal at z=0
        self.start_wx = float(mouse_sx - vp_x)

        # Horizontal world drift from aim angle — fixed, not draw-dependent
        self.horiz_v = math.sin(aim_h) * 200.0   # world-wx px/sec

        # Forward speed — the only thing draw power changes
        self.vz = BASE_VZ * max(0.15, draw_power / 100.0)

        # Screen-space wind accumulator (px, not world units)
        self.wind_drift_sx = 0.0

        # Current positions
        self.screen_sx = self.start_sx
        self.screen_sy = self.start_sy
        self.wx        = self.start_wx
        self.wy        = float(mouse_sy - vp_y)
        self.wz        = 0.0

        # 0→1 over first 0.2s — shaft reveals from tip inward
        self.shaft_reveal = 0.0

        self.alive  = True
        self.landed = False

    def update(self, dt, wind):
        """wind: ±10 max. Positive = pushes right."""

        if not self.alive:
            return

        self.flight_t += dt
        t = self.flight_t

        # Wind accumulates directly in screen space
        self.wind_drift_sx += wind * dt

        # Forward depth movement
        self.wz = self.vz * t

        # Perspective scale only for depth calculations
        scale = max(0.01, 1.0 - self.wz / (MAX_Z * 1.4))

        # Vertical gravity arc
        self.screen_sy = (
                self.start_sy
                + 0.5 * GRAVITY_SCREEN * t * t
        )

        # Horizontal motion starts from aimed mouse position
        self.wx = self.horiz_v * t

        self.screen_sx = (
                self.start_sx  # <- original aimed X position
                + self.wx
                + self.wind_drift_sx
        )

        # Keep projection-consistent world y for collisions
        self.wy = (
                          self.screen_sy - self.vp_y
                  ) / scale

        # Arrow shaft reveal animation
        self.shaft_reveal = min(1.0, t / 0.20)

        # End conditions
        if (
                self.wz >= MAX_Z
                or self.screen_sy > self.vp_y + 600
        ):
            self.alive = False
            self.landed = True

    def screen_pos(self):
        scale = max(0.01, 1.0 - self.wz / (MAX_Z * 1.4))
        return self.screen_sx, self.screen_sy, scale

    def velocity_angle(self):
        """Screen-space velocity angle for orienting the arrow sprite."""
        t      = max(self.flight_t, 0.001)
        scale  = max(0.01, 1.0 - self.wz / (MAX_Z * 1.4))
        vx     = self.horiz_v * scale + (self.wind_drift_sx / t if t > 0 else 0)
        vy     = GRAVITY_SCREEN * t
        tilt   = self.vz * 0.020 * scale   # subtle forward lean
        return math.atan2(vy + tilt, vx + tilt)

    def can_hit(self, target_wz):
        """No hit until arrow reaches 88% of target depth."""
        return self.wz >= target_wz * 0.88

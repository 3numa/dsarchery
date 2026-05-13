# targets.py
# Target objects at varying depths, drifting side to side.
# 4 rings, tournament-style scoring: 3 / 5 / 7 / 10

import math
import random

# (radius px unscaled, score, color) — inner to outer
# Larger radii than before so the face is readable on screen
RINGS = [
    ( 18, 10, (255, 230,  40)),   # gold  — 10 pts
    ( 36,  7, (210,  45,  45)),   # red   —  7 pts
    ( 54,  5, ( 45,  90, 210)),   # blue  —  5 pts
    ( 72,  3, ( 30,  30,  30)),   # black —  3 pts
]

OUTER_RADIUS = RINGS[-1][0]

# Push targets further back so they read as distant
DEPTH_LEVELS = [500, 620, 740, 860, 950]

LIFETIME_MIN = 9.0
LIFETIME_MAX = 18.0

_id_counter = 0


def _random_world_x(canvas_w):
    # Gaussian centered at 0, sigma keeps most targets in the middle third
    sigma = canvas_w * 0.18
    x = random.gauss(0, sigma)
    limit = canvas_w * 0.38
    return max(-limit, min(limit, x))


class Target:
    def __init__(self, world_x, world_z, canvas_w):
        global _id_counter
        self.id = _id_counter
        _id_counter += 1

        self.wx = world_x
        self.wz = world_z
        self.wy = 0.0
        self.canvas_w = canvas_w

        self.origin_x    = world_x
        self.drift_dir   = random.choice([-1, 1])
        self.drift_speed = random.uniform(0.35, 0.7)
        self.drift_range = random.uniform(25, 60)

        self.bob_offset = random.uniform(0, math.pi * 2)
        self.bob_amp    = random.uniform(10, 20) if random.random() < 0.35 else 0

        # screen-space bounding box — written by renderer each frame
        self.x = 0.0
        self.y = 0.0
        self.w = 0.0
        self.h = 0.0
        self.screen_scale = 1.0

        self.hit       = False
        self.score_val = 0
        self.ring_idx  = -1   # index into RINGS of the struck ring
        self.hit_flash = 0.0

        self.lifetime = random.uniform(LIFETIME_MIN, LIFETIME_MAX)
        self.age      = 0.0
        self.expired  = False
        self.alpha    = 255

    def update(self, dt, t):
        if self.hit:
            self.hit_flash = max(0.0, self.hit_flash - dt)
            return

        self.age += dt
        if self.age >= self.lifetime:
            self.expired = True
            return

        self.wx = self.origin_x + math.sin(t * self.drift_speed * self.drift_dir) * self.drift_range
        self.wy = math.sin(t * 1.1 + self.bob_offset) * self.bob_amp

        remaining = self.lifetime - self.age
        self.alpha = int(255 * min(1.0, remaining / 1.5))

    def check_hit(self, sx, sy) -> int:
        """
        Precise ring hit detection using screen-space distance.
        Inner-to-outer so the highest score always wins.
        """
        if self.hit:
            return 0

        cx   = self.x + self.w / 2
        cy   = self.y + self.h / 2
        dist = math.hypot(sx - cx, sy - cy)

        for i, (r, score, _) in enumerate(RINGS):
            if dist <= r * self.screen_scale:
                self.hit       = True
                self.score_val = score
                self.ring_idx  = i
                self.hit_flash = 0.9   # longer flash so player can see which ring
                return score

        return 0


def make_target(canvas_w):
    z = random.choice(DEPTH_LEVELS) + random.uniform(-30, 30)
    x = _random_world_x(canvas_w)
    return Target(x, z, canvas_w)


def spawn_targets(canvas_w, count=6):
    targets = []
    depths  = list(DEPTH_LEVELS) * 4
    random.shuffle(depths)
    for i in range(count):
        z = depths[i] + random.uniform(-30, 30)
        x = _random_world_x(canvas_w)
        targets.append(Target(x, z, canvas_w))
    return targets

# game.py
# Main game loop, input, state, and QuadTree collision pipeline.

import pygame
import math
import random

from quadtree import QuadTree, Rect
from physics  import Arrow
from targets  import spawn_targets, make_target
from renderer import Renderer

TOTAL_ARROWS = 10
FPS          = 60
MAX_TARGETS  = 6

class Game:
    def __init__(self, surface: pygame.Surface):
        self.surface  = surface
        self.renderer = Renderer(surface)

        W, H = surface.get_size()
        self.qt = QuadTree(Rect(0, 0, W, H))

        self.targets = spawn_targets(W, count=MAX_TARGETS)
        self.arrow   = None

        # aim_h is derived from mouse x — arrow follows cursor exactly
        self.aim_h   = 0.0
        self.mouse_x = W // 2
        self.mouse_y = H // 2

        self.charging     = False
        self.charge_power = 0.0

        self.score  = 0
        self.arrows = TOTAL_ARROWS
        self.over   = False
        # wind: positive = rightward (matches wx accumulation in physics)
        self.wind   = random.randint(-8, 8)
        self.t      = 0.0

        self.score_pops = []
        self.SHOW_QUADTREE = False

    def _fire(self):
        if self.arrows <= 0 or self.over:
            return
        if self.charge_power < 2:   # ignore accidental taps
            self.charging     = False
            self.charge_power = 0.0
            return

        self.arrows -= 1
        r = self.renderer

        self.arrow = Arrow(
            mouse_sx   = self.mouse_x,
            mouse_sy   = self.mouse_y,
            aim_h      = self.aim_h,
            draw_power = self.charge_power,
            vp_x       = r.vp_x,
            vp_y       = r.vp_y,
        )
        self.charging     = False
        self.charge_power = 0.0

    def _restart(self):
        W, H = self.surface.get_size()
        self.targets      = spawn_targets(W, count=MAX_TARGETS)
        self.arrow        = None
        self.score        = 0
        self.arrows       = TOTAL_ARROWS
        self.over         = False
        self.charging     = False
        self.charge_power = 0.0
        self.aim_h        = 0.0
        self.score_pops   = []
        self.wind         = random.randint(-8, 8)
        self.t            = 0.0
        self.qt           = QuadTree(Rect(0, 0, W, H))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and not self.charging and self.arrows > 0 and not self.over:
                self.charging     = True
                self.charge_power = 0.0

            if event.key == pygame.K_h:
                self.SHOW_QUADTREE = not self.SHOW_QUADTREE

            if event.key == pygame.K_r:
                self._restart()

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE and self.charging:
                self._fire()

        if event.type == pygame.MOUSEMOTION:
            self.mouse_x = event.pos[0]
            self.mouse_y = event.pos[1]
            W = self.surface.get_width()
            # aim_h maps mouse x to ±1.0 — used for horizontal drift of the shot
            self.aim_h = max(-1.0, min(1.0, (self.mouse_x / W - 0.5) * 2.0))

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.charging and self.arrows > 0 and not self.over:
                self.charging     = True
                self.charge_power = 0.0

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.charging:
                self._fire()

    def _rebuild_qt(self):
        W, H = self.surface.get_size()
        self.qt = QuadTree(Rect(0, 0, W, H))
        for target in self.targets:
            if not target.hit:
                self.qt.insert(target)

    def _check_collisions(self):
        if self.arrow is None or not self.arrow.alive:
            return

        sx, sy, _ = self.arrow.screen_pos()
        query_rect = Rect(sx - 1, sy - 1, 2, 2)
        candidates = self.qt.query(query_rect)

        for target in candidates:
            if not self.arrow.can_hit(target.wz):
                continue

            pts = target.check_hit(sx, sy)
            if pts > 0:
                self.score      += pts
                self.arrow.alive = False
                ring_names = {0: "GOLD 10", 1: "+7", 2: "+5", 3: "+3"}
                label = ring_names.get(target.ring_idx, f"+{pts}")
                self.score_pops.append({
                    "sx": sx, "sy": sy - 25,
                    "text": label,
                    "life": 1.0,
                })
                break

    def update(self, dt):
        if self.over:
            return

        self.t    += dt
        # wind drifts as a random walk, clamped to ±45
        self.wind += random.uniform(0, 0.05)
        self.wind  = max(-8, min(8, self.wind))

        if self.charging:
            self.charge_power = min(100, self.charge_power + 72 * dt)

        for target in self.targets:
            target.update(dt, self.t)

        # cull expired/done targets and top up
        W = self.surface.get_width()
        self.targets = [
            t for t in self.targets
            if not t.expired and not (t.hit and t.hit_flash <= 0)
        ]
        while len(self.targets) < MAX_TARGETS:
            self.targets.append(make_target(W))

        if self.arrow:
            # wind scale: 0.30 keeps it noticeable without being overwhelming
            self.arrow.update(dt, self.wind)
            if self.arrow.landed:
                self.arrow = None

        for pop in self.score_pops:
            pop["life"] -= dt * 1.1
        self.score_pops = [p for p in self.score_pops if p["life"] > 0]

        # trigger game over only after the final arrow has fully landed
        if self.arrows <= 0 and self.arrow is None and not self.charging:
            self.over = True

    def draw(self):
        r = self.renderer

        r.draw_background()

        for target in self.targets:
            r.draw_target(target, self.t)

        self._rebuild_qt()
        self._check_collisions()

        self._rebuild_qt()
        self._check_collisions()

        if self.SHOW_QUADTREE:
            for rect in self.qt.get_leaf_boundaries():
                pygame.draw.rect(
                    self.surface,
                    (0, 255, 0),
                    pygame.Rect(rect.x, rect.y, rect.w, rect.h),
                    1
                )

        r.draw_arrow(self.arrow)
        r.draw_bow(self.charge_power, self.charging)          # bow stays centered, cosmetic
        r.draw_crosshair(self.mouse_x, self.mouse_y)          # crosshair exactly at cursor

        if self.charging:
            r.draw_power_bar(self.charge_power)

        for pop in self.score_pops:
            r.draw_score_pop(pop["text"], pop["sx"], pop["sy"], pop["life"])

        r.draw_hud(self.score, self.arrows, self.wind)

        if self.over:
            r.draw_game_over(self.score)

        pygame.display.flip()

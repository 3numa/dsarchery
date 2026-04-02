# renderer.py
# All pygame drawing: background, floor grid, targets, arrow, bow, HUD.
#
# 3D illusion:
#   1. Perspective floor grid converging at the vanishing point
#   2. Targets scale and receive a depth-shadow overlay (further = darker)
#   3. Only the struck ring glows white; all others keep their colour
#   4. Arrow shaft grows in as it flies (tip first, shaft reveals over 0.2s)

import pygame
import math
from physics import project, MAX_Z
from targets import RINGS, OUTER_RADIUS


def _get_font(size):
    return pygame.font.SysFont("couriernew", size, bold=True)


class Renderer:
    def __init__(self, surface: pygame.Surface):
        self.surface = surface
        self._update_dims()
        self.font_lg = _get_font(26)
        self.font_sm = _get_font(14)

    def _update_dims(self):
        W, H = self.surface.get_size()
        self.W        = W
        self.H        = H
        self.vp_x     = W // 2
        self.vp_y     = int(H * 0.42)
        self.ground_y = int(H * 0.72)

    def on_resize(self, surface):
        self.surface = surface
        self._update_dims()

    # ------------------------------------------------------------------ #
    # Background + floor grid
    # ------------------------------------------------------------------ #

    def draw_background(self):
        W, H = self.W, self.H
        surf = self.surface

        sky_stops = [
            (0.00, ( 13,  27,  42)),
            (0.38, ( 26,  58,  92)),
            (0.58, ( 46, 107,  79)),
            (0.72, ( 58, 122,  58)),
            (1.00, ( 30,  77,  30)),
        ]
        prev_t, prev_c = sky_stops[0]
        for next_t, next_c in sky_stops[1:]:
            y0, y1 = int(prev_t * H), int(next_t * H)
            for y in range(y0, y1):
                b = (y - y0) / max(1, y1 - y0)
                col = tuple(int(prev_c[j] + (next_c[j] - prev_c[j]) * b) for j in range(3))
                pygame.draw.line(surf, col, (0, y), (W, y))
            prev_t, prev_c = next_t, next_c

        for i in range(60):
            sx = (i * 137 + 41) % W
            sy = (i * 97  + 13) % int(self.ground_y * 0.55)
            pygame.draw.circle(surf, (255, 255, 255), (sx, sy), 2 if i % 3 == 0 else 1)

        self._draw_floor_grid()

    def _draw_floor_grid(self):
        surf = self.surface
        vx, vy, gy = self.vp_x, self.vp_y, self.ground_y
        W, H = self.W, self.H
        for i in range(19):
            gx = int(i / 18 * W)
            pygame.draw.line(surf, (50, 135, 50), (vx, gy), (gx, H), 1)
        for i in range(1, 11):
            t = (i / 10) ** 1.8
            y = int(gy + (H - gy) * t)
            pygame.draw.line(surf, (50, 130, 50), (0, y), (W, y), 1)

    # ------------------------------------------------------------------ #
    # Targets
    # ------------------------------------------------------------------ #

    def draw_target(self, target, t):
        """
        Project target, update its screen bounding box (used by QuadTree and hit detection),
        then draw it with a depth-based shadow overlay.
        """
        vx, vy = self.vp_x, self.vp_y

        # world_y: positive = below vanishing point in screen space.
        # 140 sits targets at roughly 40% from the bottom of the screen.
        world_y = 140 + target.wy
        sx, sy, scale = project(target.wx, world_y, target.wz, vx, vy)
        target.screen_scale = scale

        outer_r   = OUTER_RADIUS * scale
        target.x  = sx - outer_r
        target.y  = sy - outer_r
        target.w  = outer_r * 2
        target.h  = outer_r * 2

        life_alpha = target.alpha / 255.0
        self._draw_target_face(int(sx), int(sy), scale, life_alpha,
                               target.hit, target.hit_flash,
                               target.ring_idx, target.wz)

    def _draw_target_face(self, cx, cy, scale, life_alpha, hit, flash, hit_ring, wz):
        surf = self.surface

        for i in range(len(RINGS) - 1, -1, -1):
            r, score, color = RINGS[i]
            sr = max(2, int(r * scale))

            # only the struck ring glows white while the flash is active
            if hit and flash > 0 and i == hit_ring:
                base_c = (255, 255, 255)
            else:
                base_c = color

            c = tuple(int(ch * life_alpha) for ch in base_c)
            pygame.draw.circle(surf, c, (cx, cy), sr)
            # thin black outline on each ring
            pygame.draw.circle(surf, (0, 0, 0), (cx, cy), sr, max(1, int(scale * 0.8)))

        # gold centre dot
        gold = tuple(int(ch * life_alpha) for ch in (255, 235, 60))
        pygame.draw.circle(surf, gold, (cx, cy), max(2, int(4 * scale)))

        # depth shadow: a circular black overlay whose alpha grows with distance.
        # This is the same depth signal that drives arrow invincibility in can_hit().
        if not (hit and flash > 0):
            depth_t  = wz / MAX_Z           # 0 = close, 1 = far
            shadow_a = int(depth_t * 170 * life_alpha)
            if shadow_a > 4:
                outer_r = max(2, int(OUTER_RADIUS * scale))
                s = pygame.Surface((outer_r * 2, outer_r * 2), pygame.SRCALPHA)
                pygame.draw.circle(s, (0, 0, 0, shadow_a), (outer_r, outer_r), outer_r)
                surf.blit(s, (cx - outer_r, cy - outer_r))

    # ------------------------------------------------------------------ #
    # Arrow
    # ------------------------------------------------------------------ #

    def draw_arrow(self, arrow):
        if arrow is None or not arrow.alive:
            return

        surf = self.surface
        sx, sy, scale = arrow.screen_pos()
        angle = arrow.velocity_angle()

        self._draw_arrow_shape(int(sx), int(sy), scale, angle, arrow.shaft_reveal)

    def _draw_arrow_shape(self, cx, cy, scale, angle, shaft_reveal):
        """
        Arrow is drawn tip-first. The shaft grows in from 0→full over shaft_reveal (0→1).
        This simulates the arrow appearing from just its point and gaining visible
        length as it falls away from the shooter and turns to face the target.
        Full shaft length at z=0 (scale=1) is 28px; shrinks with perspective.
        """
        surf  = self.surface
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        def rot(x, y):
            return (cx + int(x * cos_a - y * sin_a),
                    cy + int(x * sin_a + y * cos_a))

        # Shaft length scales with both perspective and reveal progress
        max_shaft = 28
        shaft = int(max_shaft * scale * shaft_reveal)
        w     = max(1, int(3 * scale))

        # Only draw shaft and fletching once there's something to show
        if shaft > 2:
            pygame.draw.line(surf, (200, 165, 75), rot(-shaft, 0), rot(0, 0), w)

        # Tip (arrowhead) — always visible from first frame
        tip_len = int(9 * scale)
        tip = [rot(0, 0), rot(tip_len, -w), rot(tip_len, w)]
        pygame.draw.polygon(surf, (150, 150, 150), tip)

        # Fletching — only visible once shaft is mostly revealed
        if shaft_reveal > 0.6 and shaft > 4:
            for sign in (-1, 1):
                fletch = [rot(-shaft, 0),
                          rot(-shaft - int(6*scale), sign * int(5*scale)),
                          rot(int(-shaft * 0.5), 0)]
                pygame.draw.polygon(surf, (180, 40, 40), fletch)

    # ------------------------------------------------------------------ #
    # Bow — cosmetic, stays centered at bottom of screen
    # ------------------------------------------------------------------ #

    def draw_bow(self, power, charging):
        surf = self.surface
        bx   = self.W // 2
        by   = self.H - 80

        arc_rect = pygame.Rect(bx - 38, by - 38, 76, 76)
        pygame.draw.arc(surf, (139, 94, 26), arc_rect,
                        math.radians(45), math.radians(315), 5)

        pullback = int(power * 0.12) if charging else 0
        mid = (bx - pullback, by)
        pygame.draw.line(surf, (220, 220, 220), (bx - 27, by - 27), mid, 2)
        pygame.draw.line(surf, (220, 220, 220), (bx - 27, by + 27), mid, 2)

        if charging and power > 5:
            pygame.draw.line(surf, (200, 165, 75), mid, (bx + 48, by), 3)

    # ------------------------------------------------------------------ #
    # Crosshair — rendered exactly at cursor position
    # ------------------------------------------------------------------ #

    def draw_crosshair(self, mouse_x, mouse_y):
        surf = self.surface
        cx, cy = mouse_x, mouse_y

        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 13, 2)
        pygame.draw.line(surf, (255, 255, 255), (cx - 20, cy), (cx + 20, cy), 1)
        pygame.draw.line(surf, (255, 255, 255), (cx, cy - 20), (cx, cy + 20), 1)
        # small dot at dead center
        pygame.draw.circle(surf, (255, 80, 80), (cx, cy), 2)

    # ------------------------------------------------------------------ #
    # Power bar
    # ------------------------------------------------------------------ #

    def draw_power_bar(self, power):
        surf  = self.surface
        bar_w = 160
        bar_h = 14
        bx    = self.W // 2 - bar_w // 2
        by    = self.H - 52

        pygame.draw.rect(surf, (0, 0, 0), (bx - 2, by - 2, bar_w + 4, bar_h + 4))
        t      = power / 100
        r      = int(80 + t * 175)
        g      = int(220 - t * 180)
        fill_w = int(bar_w * t)
        if fill_w > 0:
            pygame.draw.rect(surf, (r, g, 40), (bx, by, fill_w, bar_h))
        pygame.draw.rect(surf, (255, 255, 255), (bx, by, bar_w, bar_h), 1)

    # ------------------------------------------------------------------ #
    # HUD
    # ------------------------------------------------------------------ #

    def draw_hud(self, score, arrows, wind):
        surf = self.surface
        pygame.draw.rect(surf, (0, 0, 0),    (10, 10, 230, 100), border_radius=4)
        pygame.draw.rect(surf, (40, 80, 40), (10, 10, 230, 100), 1, border_radius=4)

        self._text(f"SCORE:  {score}",   (22, 34), (255, 224, 51))
        self._text(f"ARROWS: {arrows}",  (22, 60), (170, 221, 255))

        # wind indicator: positive wind blows right, shown as >>
        # the number is the magnitude; direction matches wx accumulation in physics
        if abs(wind) < 3:
            wind_str = "  calm"
        elif wind > 0:
            wind_str = f">> {wind:.0f}"    # rightward
        else:
            wind_str = f"<< {abs(wind):.0f}"  # leftward
        self._text(f"WIND: {wind_str}", (22, 86), (136, 255, 170))

        self._text("[SPACE/LMB] hold & release to fire",
                   (self.W // 2 - 215, self.H - 22), (160, 160, 160), small=True)
        self._text("[R] Restart",
                   (self.W - 140, self.H - 22), (100, 100, 100), small=True)

    def _text(self, msg, pos, color, small=False):
        font = self.font_sm if small else self.font_lg
        self.surface.blit(font.render(msg, True, color[:3]), pos)

    # ------------------------------------------------------------------ #
    # Score popup
    # ------------------------------------------------------------------ #

    def draw_score_pop(self, text, sx, sy, life):
        font   = _get_font(int(20 + (1 - life) * 8))
        surf_t = font.render(text, True, (255, 224, 51))
        surf_t.set_alpha(int(255 * life))
        rect   = surf_t.get_rect(center=(int(sx), int(sy - (1 - life) * 45)))
        self.surface.blit(surf_t, rect)

    # ------------------------------------------------------------------ #
    # Game over screen
    # ------------------------------------------------------------------ #

    def draw_game_over(self, score):
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.surface.blit(overlay, (0, 0))

        cx, cy = self.W // 2, self.H // 2

        def centered(size, text, y, color):
            s = _get_font(size).render(text, True, color)
            self.surface.blit(s, s.get_rect(center=(cx, y)))

        centered(52, "QUIVER EMPTY",           cy - 55, (255, 224, 51))
        centered(32, f"Final Score:  {score}", cy + 10, (255, 255, 255))
        centered(20, "Press  R  to play again", cy + 60, (160, 200, 160))

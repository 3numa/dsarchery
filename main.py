# main.py
# Entry point. Run this to start the game.
#   python main.py

import pygame
import sys
from game import Game, FPS

WIDTH  = 960
HEIGHT = 620


def main():
    pygame.init()
    pygame.display.set_caption("Archery // QuadTree Spatial Partitioning")

    flags   = pygame.RESIZABLE
    surface = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    clock   = pygame.time.Clock()

    game = Game(surface)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.VIDEORESIZE:
                surface = pygame.display.set_mode((event.w, event.h), flags)
                game.surface  = surface
                game.renderer.on_resize(surface)

            game.handle_event(event)

        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)   # cap delta time so a lag spike doesn't break physics

        game.update(dt)
        game.draw()


if __name__ == "__main__":
    main()

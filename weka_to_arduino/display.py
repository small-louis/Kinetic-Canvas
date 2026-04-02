import numpy as np
import pygame
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .main import AnimationManager

from .wave import WaveSimulation


class PixelDisplay:
    res_x: int
    res_y: int
    screen: pygame.Surface

    def __init__(self, manager: "AnimationManager", res_x, res_y) -> None:
        self.manager = manager
        self.res_x = res_x
        self.res_y = res_y
        self.frame = 0
        self.layers = []

    async def setup(self):
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.res_x, self.res_y), pygame.SCALED | pygame.SRCALPHA | pygame.RESIZABLE
        )
        self.screen.fill(pygame.Color(0, 0, 0))
        self.layers.append(Sparkles(self.manager.wave, self))

    def getArray(self) -> list[int]:
        """Returns a flattended array of R,G,B values for the display. Each pixel has 3 values in the array. Pixels are ordered from top-left to bottom-right."""
        # TODO
        return [0 for i in range(self.res_x * self.res_y * 3)]

    def stop(self):
        pygame.quit()

    async def tick(self):
        for layer in self.layers:
            layer.tick()

        self.frame += 1

        pygame.display.flip()


class Sparkles:
    colour = pygame.Color(240, 240, 255, 100)
    fadeRate = 0.2

    def __init__(self, wave: WaveSimulation, display: PixelDisplay):
        self.display = display
        self.wave: WaveSimulation = WaveSimulation(self)
        self.surface = pygame.Surface((display.res_x, display.res_y), pygame.SRCALPHA)

    def tick(self):
        # This will draw random sparkles across the screen based on wave height at that pixel position
        self.surface.fill(pygame.Color(0, 0, 0, int(self.fadeRate * 255)))
        wave_heights: list[float] = self.wave.calculate_discrete_positions(
            self.display.res_x
        )[1]
        for x, height in enumerate(wave_heights):
            chance_sparkle = (height + 12) / 24
            # Create array of random numbers between 0 and 1
            randoms = np.random.rand(self.display.res_y)
            for y in range(self.display.res_y):
                self.surface.set_at(
                    (x, y), self.colour.lerp(pygame.Color(0, 0, 0, 0), chance_sparkle)
                )
            # # Create array of 0 or 1 based on chance_sparkle
            # sparkles = randoms < (chance_sparkle + 0.5)
            # for y, sparkle in enumerate(sparkles):
            #     if sparkle:
            #         # Draw a white pixel
            #         self.surface.set_at((x, y), self.colour)
        # Blend the new surface with the old one
        self.display.screen.blit(self.surface, (0, 0))

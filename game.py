import random
import pygame
from window import Window
from player import Player


class Game:
    def __init__(self, window: Window, player: Player, verbose=False, mode='random'):
        self._window = window
        self._player = player
        self._obstacles_manual = []
        self._obstacles = []
        self._verbose = verbose
        self._mode = mode

    def reset(self):
        if self._mode == 'random':
            return self._new_random_game()
        else:
            return self._new_manual_game()

    def _new_random_game(self):
        self._obstacles = []
        self._generate_obstacles(10)
        self._player.reset()
        self._draw_ui()

        return self.observe()

    def _new_manual_game(self):
        self._obstacles = self._obstacles_manual
        self._player.reset()
        self._draw_ui()

        return self.observe()

    def setup(self, skip=False):
        if not skip:
            self._window.set_state('Setup')
            self._new_manual_game()
            while True:
                button_pressed, pos = self._handle_buttons()
                if button_pressed == 1:
                    self._window.set_state('Run')
                    return
                elif button_pressed == 2:
                    self.reset()
                elif button_pressed == 3:
                    tile = self._window.window_coords_to_tile(pos)
                    self._set_obstacle(tile)
                self._obstacles_manual = self._obstacles
                self._draw_ui()
        else:
            self._window.set_state('Run')

    def step(self, action):
        info = {}
        self._player.move(action)
        done = self._done()
        self._draw_ui()

        button_pressed, _ = self._handle_buttons()
        if button_pressed == 1:
            self.setup()
        elif button_pressed == 2:
            info['won'] = False
            done = True
            self.reset()

        info['won'] = self._won()
        info['coords'] = self._player.get_coords()
        info['prev_pos'] = self._player.get_prev_pos()
        observation = self.observe()
        reward = self._get_reward()

        if self._verbose:
            print(f'Observation: {observation}, reward: {reward}, done: {done}, info: {info}')

        return observation, reward, done, info

    def play(self):
        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.KEYDOWN:
                    action = 0
                    if event.key == pygame.K_UP:
                        action = 0
                    if event.key == pygame.K_RIGHT:
                        action = 1
                    if event.key == pygame.K_DOWN:
                        action = 2
                    if event.key == pygame.K_LEFT:
                        action = 3
                    _, _, done, info = self.step(action)
                    if done:
                        self.reset()

    def delay(self):
        self._window.delay()

    def set_window_mode(self, mode):
        self._window.set_mode(mode)
        
    def _tile_in_window(self, tile):
        if (0 <= tile[0] <= self._window.get_size()[0] - 1) \
                and (0 <= tile[1] <= self._window.get_size()[1] - 1):
            return True
        else:
            return False

    def _done(self):
        coords = self._player.get_coords()
        if (coords[0] < 0 or coords[0] > self._window.get_size()[0] - 1) \
                or (coords[1] < 1 or coords[1] > self._window.get_size()[1] - 1) \
                or (coords in self._obstacles):
            return True
        else:
            return False

    def _won(self):
        if self._player.get_coords()[1] == 0:
            return True
        else:
            return False

    def _generate_obstacles(self, min_count=4, max_count=4):
        if max_count < min_count:
            max_count = min_count

        count = random.randint(min_count, max_count)
        size = self._window.get_size()
        side = random.randint(0, 1)

        for _ in range(count):
            if side:
                x = random.randint(1, size[0] - 3)
            else:
                x = random.randint(2, size[0] - 2)
            y = random.randint(2, size[1] - 3)

            self._add_obstacle((x, y))
            direction = random.randint(1, 3)
            if direction == 1:
                x = x + 1
            if direction == 2:
                y = y + 1
            if direction == 3:
                x = x - 1
            self._add_obstacle((x, y))

    def _add_obstacle(self, tile):
        self._obstacles.append(tile)
        self._draw_ui()

    def _remove_obstacle(self, tile):
        self._obstacles.remove(tile)

    def smart_add(self, tile):
        pos = self._player.get_coords()
        if pos[0] == tile[0]:
            x = tile[0]
            for y in range(min(pos[1], tile[1]), max(pos[1], tile[1]) + 1):
                try:
                    self._remove_obstacle((x, y))
                except ValueError:
                    pass
        if pos[1] == tile[1]:
            y = tile[1]
            for x in range(min(pos[0], tile[0]), max(pos[0], tile[0]) + 1):
                try:
                    self._remove_obstacle((x, y))
                except ValueError:
                    pass
        if self._tile_in_window(tile):
            self._add_obstacle(tile)

    def _get_obstacles(self):
        return self._obstacles

    def _set_obstacle(self, tile):
        if tile in self._obstacles:
            self._remove_obstacle(tile)
        else:
            self._add_obstacle(tile)

    def _get_reward(self):
        lost = self._done()
        won = self._won()
        last_action = self._player.get_last_action()

        if won:
            return 50
        elif lost:
            return -100
        elif self._player.get_coords() == self._player.get_prev_pos()[1]:
            return -50
        elif last_action == 0:
            return 1 * (self._window.get_size()[1] - self._player.get_coords()[1])
        elif last_action == 2:
            return -2
        else:
            return -1

    def observe(self):  # Should be private but needed for mqtt
        size_x, size_y = self._window.get_size()
        observation = self._obstacle_area(size_x, size_y)
        observation.extend(self._prev_action())
        observation.extend(self._player.get_coords())

        return observation

    def _obstacle_area(self, size_x, size_y):
        obstacles = [0] * ((2 * size_x + 1) * (2 * size_y + 1))
        x, y = self._player.get_coords()

        for i in range(2 * size_x + 1):
            for j in range(2 * size_y + 1):
                tile = (x - size_x + i, y - size_y + j)
                if self._is_obstacle(tile):
                    obstacles[(2 * size_x + 1) * j + i] = 1

        return obstacles

    def _obstacle_next(self):
        data = [0] * 4
        coords = self._player.get_coords()

        if self._is_obstacle((coords[0], coords[1] - 1)):
            data[0] = 1
        if self._is_obstacle((coords[0] + 1, coords[1])):
            data[1] = 1
        if self._is_obstacle((coords[0], coords[1] + 1)):
            data[2] = 1
        if self._is_obstacle((coords[0] - 1, coords[1])):
            data[3] = 1
        return data

    def _is_obstacle(self, tile):
        if (tile[0] < 0 or tile[0] > self._window.get_size()[0] - 1) \
                or tile[1] > self._window.get_size()[1] - 1 \
                or tile in self._obstacles:
            return True
        else:
            return False

    def _prev_action(self):
        data = [0] * 2
        action = self._player.get_last_action()
        if action == 1:
            data[1] = 1
        elif action == 2:
            data[0] = 1
        elif action == 3:
            data[0] = data[1] = 1

        return data

    def _draw_ui(self):
        self._window.clear()
        self._window.render_menu()
        self._window.draw_finish()
        self._window.draw_history(self._player.get_history())
        self._window.draw_obstacles(self._obstacles)
        self._window.draw_player(self._player)
        self._window.update()

    def _handle_buttons(self):
        button_id = 0
        events = pygame.event.get()
        dim = self._window.get_dimensions()
        tile_dim = self._window.get_tile_dimensions()
        pos = (0, 0)

        for event in events:
            if event.type == pygame.MOUSEBUTTONUP:
                pos = pygame.mouse.get_pos()
                if pos[0] < dim[0] // 2 \
                        and pos[1] < tile_dim[1]:
                    button_id = 1
                elif pos[0] > dim[0] // 2 \
                        and pos[1] < tile_dim[1]:
                    button_id = 2
                else:
                    button_id = 3
        return button_id, pos

    def get_window(self):
        return self._window

    def get_player(self):
        return self._player

    def set_mode(self, mode):
        self._mode = mode

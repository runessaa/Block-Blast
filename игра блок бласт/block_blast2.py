import pygame
import random
import asyncio
import platform
import math
import os

# инициализация pygame
pygame.init()
pygame.mixer.init()

# границы окна, кнопок и тп
WIDTH, HEIGHT = 550, 700
GRID_SIZE = 8
CELL_SIZE = 50
GRID_OFFSET_X = (WIDTH - GRID_SIZE * CELL_SIZE) // 2
GRID_OFFSET_Y = 120
FPS = 60

# цвета и фон
WHITE = (255, 255, 255)
DARK_ORCHID = (153, 50, 204)
DARK_PURPLE = (70, 0, 105)
GRID_BACKGROUND_COLOR = (*DARK_PURPLE, 153)
GRAY = (128, 128, 128)
SHADOW = (50, 50, 50)
HIGHLIGHT = (255, 255, 255, 150)
HIGHLIGHT_FILL = (255, 255, 255, 50)
PURPLE_OUTLINE = (138, 43, 226)
EFFECT_COLORS = [
    (0, 0, 205),
    (138, 43, 226),
    (255, 105, 180)
]
COLORS = [
    (138, 43, 226),
    (148, 0, 211),
    (255, 20, 147),
    (255, 105, 180),
    (0, 0, 205),
    (75, 0, 130),
]

HIGHSCORE_FILE = "block_blast_highscore.txt"

# формы блоков для игры
BLOCK_SHAPES = [
    [[1]], [[1, 1]], [[1], [1]], [[1, 1], [1, 1]],
    [[1, 1, 1]], [[1], [1], [1]], [[1, 1], [0, 1]],
]

# функция затемнения цвета
def darken_color(color, factor=0.7):
    return tuple(int(c * factor) for c in color)

# функция отрисовки текста с контуром
def draw_text_with_custom_outline(screen, text_str, font, base_color, outline_color, base_pos, is_centered=True, custom_offsets=None):
    text_surface = font.render(text_str, True, base_color)
    outline_surface = font.render(text_str, True, outline_color)

    if is_centered:
        text_w, text_h = font.size(text_str)
        actual_base_pos_for_text = (base_pos[0] - text_w // 2, base_pos[1] - text_h // 2)
    else:
        actual_base_pos_for_text = base_pos

    if custom_offsets is None:
        custom_offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for dx, dy in custom_offsets:
        screen.blit(outline_surface, (actual_base_pos_for_text[0] + dx, actual_base_pos_for_text[1] + dy))

    screen.blit(text_surface, actual_base_pos_for_text)

# класс частицы для анимации взрывов
class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-4.5, -1.5)
        self.angle = random.uniform(0, 360)
        self.angular_velocity = random.uniform(-10, 10)
        self.alpha = 255
        self.size = random.randint(6, 12)
        self.color = random.choice(EFFECT_COLORS)
        self.gravity = 0.18

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.angle = (self.angle + self.angular_velocity) % 360
        self.vy += self.gravity
        self.alpha -= 7
        return self.alpha > 0

    def draw(self, screen):
        if self.alpha > 0:
            edge = self.size
            particle_surf = pygame.Surface((edge, edge), pygame.SRCALPHA)
            current_color_with_alpha = (self.color[0], self.color[1], self.color[2], int(self.alpha))
            pygame.draw.rect(particle_surf, current_color_with_alpha, (0,0,edge,edge))

            rotated_surface = pygame.transform.rotate(particle_surf, self.angle)
            rotated_rect = rotated_surface.get_rect(center=(int(self.x), int(self.y)))
            screen.blit(rotated_surface, rotated_rect.topleft)

# основной класс игры BlockBlast
class BlockBlast:
    def __init__(self):
        # инициализация экрана, шрифтов, загрузка фона и звуков
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Block Blast")
        self.clock = pygame.time.Clock()

        self.score_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.game_over_title_font = pygame.font.SysFont("Arial", 72, bold=True)
        self.instruction_font = pygame.font.SysFont("Arial", 30, bold=True)
        self.slider_label_font = pygame.font.SysFont("Arial", 20, bold=True)

        try:
            self.background = pygame.image.load('eee.jpg').convert()
            self.background = pygame.transform.scale(self.background, (WIDTH, HEIGHT))
        except pygame.error as e:
            print(f"Ошибка загрузки фона: {e}")
            self.background = pygame.Surface((WIDTH, HEIGHT))
            self.background.fill(DARK_PURPLE)

        try:
            pygame.mixer.music.load('track.mp3')
            self.pickup_sound = pygame.mixer.Sound('classic_hurt.mp3')
            self.destroy_sound = pygame.mixer.Sound('yra.mp3')
        except pygame.error as e:
            print(f"Ошибка загрузки звуков: {e}. Звуки будут отключены.")
            self.pickup_sound = type('DummySound', (), {'play': lambda: None, 'set_volume': lambda x: None})()
            self.destroy_sound = type('DummySound', (), {'play': lambda: None, 'set_volume': lambda x: None})()

        self.music_volume = 0.5
        self.effect_volume = 0.5
        self.pickup_sound.set_volume(self.effect_volume)
        
        self.destroy_sound_base_multiplier = 1.0 
        self.destroy_sound.set_volume(min(1.0, self.effect_volume * self.destroy_sound_base_multiplier))
        pygame.mixer.music.set_volume(self.music_volume)

        self.dragging_music_slider = False
        self.dragging_effect_slider = False

        self.running = True
        self.load_high_score()
        self.reset_game_state()

    # работа с рекордом (чтение/запись)
    def load_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "r") as f:
                self.high_score = int(f.read())
        except (FileNotFoundError, ValueError):
            self.high_score = 0

    def save_high_score(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(self.high_score))
        except IOError:
            print(f"Error: Could not save high score to {HIGHSCORE_FILE}")

    def update_high_score_on_game_over(self):
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    # сброс состояния игры
    def reset_game_state(self):
        self.grid = [[None for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        self.score = 0
        self.game_over = False
        self.current_block = None
        self.current_block_color = None
        self.block_offset_x = 0
        self.block_offset_y = 0
        self.available_blocks = self.generate_new_available_blocks()
        self.particles = []

        if self.check_if_game_is_over():
            self.game_over = True

    # генерация новых блоков для выбора игроком
    def generate_new_available_blocks(self):
        blocks = [random.choice(BLOCK_SHAPES) for _ in range(3)]
        self.available_colors = [random.choice(COLORS) for _ in range(3)]
        return blocks

    # отрисовка одного блока с 3D-эффектом
    def draw_3d_block(self, x, y, color, alpha=255):
        shadow_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        shadow_surface.fill((*SHADOW, 100))
        self.screen.blit(shadow_surface, (x + 5, y + 5))

        block_surface = pygame.Surface((CELL_SIZE - 2, CELL_SIZE - 2))
        if alpha < 255:
            block_surface.set_alpha(alpha)
        block_surface.fill(color)
        self.screen.blit(block_surface, (x + 1, y + 1))

        dark_color = darken_color(color)
        pygame.draw.polygon(self.screen, dark_color, [
            (x + CELL_SIZE - 2, y + 1),
            (x + CELL_SIZE - 2, y + CELL_SIZE - 2),
            (x + CELL_SIZE + 3, y + CELL_SIZE - 7),
            (x + CELL_SIZE + 3, y + 6)
        ])
        pygame.draw.polygon(self.screen, dark_color, [
            (x + 1, y + CELL_SIZE - 2),
            (x + CELL_SIZE - 2, y + CELL_SIZE - 2),
            (x + CELL_SIZE + 3, y + CELL_SIZE - 7),
            (x + 6, y + CELL_SIZE - 7)
        ])

    # отрисовка сетки поля и блоков на ней
    def draw_grid(self):
        grid_surface = pygame.Surface((GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE), pygame.SRCALPHA)
        grid_surface.fill(GRID_BACKGROUND_COLOR)
        self.screen.blit(grid_surface, (GRID_OFFSET_X, GRID_OFFSET_Y))

        for i in range(GRID_SIZE + 1):
            pygame.draw.line(self.screen, GRAY,
                           (GRID_OFFSET_X, GRID_OFFSET_Y + i * CELL_SIZE),
                           (GRID_OFFSET_X + GRID_SIZE * CELL_SIZE, GRID_OFFSET_Y + i * CELL_SIZE), 1)
            pygame.draw.line(self.screen, GRAY,
                           (GRID_OFFSET_X + i * CELL_SIZE, GRID_OFFSET_Y),
                           (GRID_OFFSET_X + i * CELL_SIZE, GRID_OFFSET_Y + GRID_SIZE * CELL_SIZE), 1)

        for i in range(GRID_SIZE):
            for j in range(GRID_SIZE):
                if self.grid[i][j]:
                    x = GRID_OFFSET_X + j * CELL_SIZE
                    y = GRID_OFFSET_Y + i * CELL_SIZE
                    self.draw_3d_block(x, y, self.grid[i][j])

    # отрисовка доступных для выбора блоков
    def draw_available_blocks(self):
        total_block_visual_width = 0
        for block_shape in self.available_blocks:
            block_width_cells = len(block_shape[0])
            total_block_visual_width += block_width_cells * CELL_SIZE + 20
        total_block_visual_width -= 20 if self.available_blocks else 0

        x_start_offset = (WIDTH - total_block_visual_width) // 2
        y_offset = 530 

        current_x = x_start_offset
        for idx, block_shape in enumerate(self.available_blocks):
            color = self.available_colors[idx]
            max_block_width_pixels = 0
            for r_idx, row_data in enumerate(block_shape):
                for c_idx, cell_val in enumerate(row_data):
                    if cell_val:
                        x_pos = current_x + c_idx * CELL_SIZE
                        y_pos = y_offset + r_idx * CELL_SIZE
                        self.draw_3d_block(x_pos, y_pos, color)
                max_block_width_pixels = max(max_block_width_pixels, len(row_data) * CELL_SIZE)
            current_x += max_block_width_pixels + 20

    # отрисовка текущего счета
    def draw_score_display(self):
        draw_text_with_custom_outline(self.screen, str(self.score), self.score_font, WHITE, PURPLE_OUTLINE,
                                     (WIDTH // 2, 60), is_centered=True)

    # отрисовка и обновление частиц (эффекты)
    def draw_particles(self):
        for particle in self.particles[:]:
            if not particle.update():
                self.particles.remove(particle)
            else:
                particle.draw(self.screen)

    # проверка, можно ли поставить блок в указанную позицию
    def can_place_block_at(self, block_shape, grid_r, grid_c):
        for r_offset, row_data in enumerate(block_shape):
            for c_offset, cell_val in enumerate(row_data):
                if cell_val:
                    actual_r, actual_c = grid_r + r_offset, grid_c + c_offset
                    if not (0 <= actual_r < GRID_SIZE and 0 <= actual_c < GRID_SIZE) or \
                       self.grid[actual_r][actual_c] is not None:
                        return False
        return True

    # получение позиции для перетаскиваемого блока
    def get_dragged_block_top_left_screen_pos(self, mouse_x, mouse_y):
        if self.current_block:
            return mouse_x - self.block_offset_x, mouse_y - self.block_offset_y
        return mouse_x, mouse_y

    # поиск позиции для "прилипания" блока к сетке
    def find_snap_position_for_dragged_block(self, mouse_x, mouse_y):
        if not self.current_block:
            return None
        dragged_block_screen_x, dragged_block_screen_y = self.get_dragged_block_top_left_screen_pos(mouse_x, mouse_y)
        target_grid_c = round((dragged_block_screen_x - GRID_OFFSET_X) / CELL_SIZE)
        target_grid_r = round((dragged_block_screen_y - GRID_OFFSET_Y) / CELL_SIZE)
        if self.can_place_block_at(self.current_block, target_grid_r, target_grid_c):
            return (target_grid_r, target_grid_c)
        return None

    # размещение блока на сетке
    def place_block_on_grid(self, block_shape, grid_r, grid_c, color):
        placed_cells = 0
        for r_offset, row_data in enumerate(block_shape):
            for c_offset, cell_val in enumerate(row_data):
                if cell_val:
                    self.grid[grid_r + r_offset][grid_c + c_offset] = color
                    placed_cells +=1
        self.score += placed_cells

    # очистка заполненных линий и запуск эффектов
    def clear_completed_lines(self):
        rows_to_clear = [r for r in range(GRID_SIZE) if all(self.grid[r][c] for c in range(GRID_SIZE))]
        cols_to_clear = [c for c in range(GRID_SIZE) if all(self.grid[r][c] for r in range(GRID_SIZE))]
        cleared_anything_this_turn = False
        lines_cleared_count = 0
        cleared_cells_coords = set()

        if rows_to_clear:
            cleared_anything_this_turn = True
            lines_cleared_count += len(rows_to_clear)
            for r_idx in rows_to_clear:
                for c_idx in range(GRID_SIZE):
                    if self.grid[r_idx][c_idx] is not None and (r_idx, c_idx) not in cleared_cells_coords:
                        x = GRID_OFFSET_X + c_idx * CELL_SIZE + CELL_SIZE // 2
                        y = GRID_OFFSET_Y + r_idx * CELL_SIZE + CELL_SIZE // 2
                        for _ in range(8):
                            self.particles.append(Particle(x, y))
                        self.grid[r_idx][c_idx] = None
                        cleared_cells_coords.add((r_idx, c_idx))

        if cols_to_clear:
            if not cleared_anything_this_turn:
                 cleared_anything_this_turn = True
            lines_cleared_count += len(cols_to_clear)
            for c_idx in cols_to_clear:
                for r_idx in range(GRID_SIZE):
                    if self.grid[r_idx][c_idx] is not None and (r_idx, c_idx) not in cleared_cells_coords:
                        x = GRID_OFFSET_X + c_idx * CELL_SIZE + CELL_SIZE // 2
                        y = GRID_OFFSET_Y + r_idx * CELL_SIZE + CELL_SIZE // 2
                        for _ in range(8):
                            self.particles.append(Particle(x, y))
                        self.grid[r_idx][c_idx] = None
                        cleared_cells_coords.add((r_idx, c_idx))

        if cleared_anything_this_turn:
            self.destroy_sound.set_volume(min(1.0, self.effect_volume * self.destroy_sound_base_multiplier))
            self.destroy_sound.play()
            self.score += lines_cleared_count * 50

    # проверка окончания игры (нет доступных ходов)
    def check_if_game_is_over(self):
        if not self.available_blocks:
            return True
        for block_shape in self.available_blocks:
            for r in range(GRID_SIZE):
                for c in range(GRID_SIZE):
                    if self.can_place_block_at(block_shape, r, c):
                        return False
        return True

    # отрисовка слайдеров громкости
    def draw_volume_sliders(self):
        slider_width, slider_height = 180, 18
        slider_x = 20 

        slider_y_music = 30 
        slider_y_effects = slider_y_music + 50 

        pygame.draw.rect(self.screen, GRAY, (slider_x, slider_y_music, slider_width, slider_height), border_radius=5)
        fill_width_music = int(slider_width * self.music_volume)
        pygame.draw.rect(self.screen, PURPLE_OUTLINE, (slider_x, slider_y_music, fill_width_music, slider_height), border_radius=5)
        pygame.draw.circle(self.screen, WHITE, (slider_x + fill_width_music, slider_y_music + slider_height // 2), 8)
        draw_text_with_custom_outline(self.screen, "Music", self.slider_label_font, WHITE, DARK_PURPLE,
                                     (slider_x + slider_width // 2, slider_y_music - 15), 
                                     is_centered=True)

        pygame.draw.rect(self.screen, GRAY, (slider_x, slider_y_effects, slider_width, slider_height), border_radius=5)
        fill_width_effects = int(slider_width * self.effect_volume)
        pygame.draw.rect(self.screen, PURPLE_OUTLINE, (slider_x, slider_y_effects, fill_width_effects, slider_height), border_radius=5)
        pygame.draw.circle(self.screen, WHITE, (slider_x + fill_width_effects, slider_y_effects + slider_height // 2), 8)
        draw_text_with_custom_outline(self.screen, "Effects", self.slider_label_font, WHITE, DARK_PURPLE,
                                     (slider_x + slider_width // 2, slider_y_effects - 15), 
                                     is_centered=True)

    # обработка взаимодействия со слайдерами громкости
    def handle_slider_interaction(self, mouse_x, mouse_y, is_dragging):
        slider_width, slider_height = 180, 18
        slider_x = 20
        slider_y_music = 30 
        slider_y_effects = slider_y_music + 50 

        music_slider_rect = pygame.Rect(slider_x, slider_y_music, slider_width, slider_height)
        if self.dragging_music_slider or (is_dragging and music_slider_rect.collidepoint(mouse_x, mouse_y)):
            self.dragging_music_slider = True
            self.music_volume = max(0, min(1, (mouse_x - slider_x) / slider_width))
            pygame.mixer.music.set_volume(self.music_volume)

        effects_slider_rect = pygame.Rect(slider_x, slider_y_effects, slider_width, slider_height)
        if self.dragging_effect_slider or (is_dragging and effects_slider_rect.collidepoint(mouse_x, mouse_y)):
            self.dragging_effect_slider = True
            self.effect_volume = max(0, min(1, (mouse_x - slider_x) / slider_width))
            self.pickup_sound.set_volume(self.effect_volume)
            self.destroy_sound.set_volume(min(1.0, self.effect_volume * self.destroy_sound_base_multiplier))

    # основной игровой цикл (асинхронный)
    async def game_loop_iteration(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.handle_slider_interaction(mouse_x, mouse_y, True)

                    if not (self.dragging_music_slider or self.dragging_effect_slider):
                        if self.current_block is None:
                            total_block_visual_width = 0
                            block_rects_and_indices = []
                            _total_width_calc = sum(len(bs[0]) * CELL_SIZE + 20 for bs in self.available_blocks) -20 if self.available_blocks else 0
                            temp_x_start_offset = (WIDTH - _total_width_calc) // 2
                            temp_y_offset_available = 530 

                            current_x_for_collision = temp_x_start_offset
                            for idx, block_shape in enumerate(self.available_blocks):
                                block_pixel_width = len(block_shape[0]) * CELL_SIZE
                                block_pixel_height = len(block_shape) * CELL_SIZE
                                block_rect = pygame.Rect(current_x_for_collision, temp_y_offset_available, block_pixel_width, block_pixel_height)
                                block_rects_and_indices.append((block_rect, idx))
                                current_x_for_collision += block_pixel_width + 20
                            
                            for rect, idx in block_rects_and_indices:
                                if rect.collidepoint(mouse_x, mouse_y):
                                    self.current_block = self.available_blocks.pop(idx)
                                    self.current_block_color = self.available_colors.pop(idx)
                                    self.block_offset_x = mouse_x - rect.x
                                    self.block_offset_y = mouse_y - rect.y
                                    self.pickup_sound.set_volume(self.effect_volume)
                                    self.pickup_sound.play()
                                    break
                        else:
                            snap_pos = self.find_snap_position_for_dragged_block(mouse_x, mouse_y)
                            if snap_pos:
                                self.place_block_on_grid(self.current_block, snap_pos[0], snap_pos[1], self.current_block_color)
                                self.clear_completed_lines()
                                self.current_block = None
                                self.current_block_color = None
                                self.block_offset_x = 0
                                self.block_offset_y = 0
                                if not self.available_blocks:
                                    self.available_blocks = self.generate_new_available_blocks()
                                if self.check_if_game_is_over():
                                    self.game_over = True
                                    self.update_high_score_on_game_over()

                elif event.button == 3:
                    if self.current_block:
                        self.available_blocks.append(self.current_block)
                        self.available_colors.append(self.current_block_color)
                        self.current_block = None
                        self.current_block_color = None

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging_music_slider = False
                    self.dragging_effect_slider = False

            if event.type == pygame.MOUSEMOTION:
                if self.dragging_music_slider or self.dragging_effect_slider:
                    self.handle_slider_interaction(mouse_x, mouse_y, False)

        self.screen.blit(self.background, (0, 0))
        self.draw_grid()
        self.draw_available_blocks()
        self.draw_score_display()
        self.draw_particles()
        self.draw_volume_sliders()

        if self.current_block:
            snap_pos_highlight = self.find_snap_position_for_dragged_block(mouse_x, mouse_y)
            if snap_pos_highlight:
                highlight_surface = pygame.Surface((GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE), pygame.SRCALPHA)
                for r_offset, row_data in enumerate(self.current_block):
                    for c_offset, cell_val in enumerate(row_data):
                        if cell_val:
                            r, c = snap_pos_highlight[0] + r_offset, snap_pos_highlight[1] + c_offset
                            if 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
                                pygame.draw.rect(highlight_surface, HIGHLIGHT_FILL,
                                                (c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE))
                                pygame.draw.rect(highlight_surface, HIGHLIGHT,
                                                (c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE), 3)
                self.screen.blit(highlight_surface, (GRID_OFFSET_X, GRID_OFFSET_Y))

            dragged_block_draw_x, dragged_block_draw_y = self.get_dragged_block_top_left_screen_pos(mouse_x, mouse_y)
            for r_offset, row_data in enumerate(self.current_block):
                for c_offset, cell_val in enumerate(row_data):
                    if cell_val:
                        self.draw_3d_block(dragged_block_draw_x + c_offset * CELL_SIZE,
                                           dragged_block_draw_y + r_offset * CELL_SIZE,
                                           self.current_block_color, alpha=200)

        pygame.display.flip()
        self.clock.tick(FPS)
        if platform.system() == "Emscripten":
            await asyncio.sleep(0)

    # цикл экрана окончания игры
    async def game_over_screen_loop(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        return True
                    if event.key == pygame.K_q:
                        self.running = False
                        return False

            self.screen.blit(self.background, (0, 0))
            draw_text_with_custom_outline(self.screen, "GAME OVER", self.game_over_title_font, WHITE, DARK_ORCHID,
                                         (WIDTH // 2, HEIGHT // 3), is_centered=True)
            draw_text_with_custom_outline(self.screen, f"Score: {self.score}", self.score_font, WHITE, PURPLE_OUTLINE,
                                         (WIDTH // 2, HEIGHT // 2 - 20), is_centered=True)
            draw_text_with_custom_outline(self.screen, f"High Score: {self.high_score}", self.score_font, WHITE, PURPLE_OUTLINE,
                                         (WIDTH // 2, HEIGHT // 2 + 40), is_centered=True)
            draw_text_with_custom_outline(self.screen, "Press R to Restart", self.instruction_font, WHITE, GRAY,
                                         (WIDTH // 2, HEIGHT * 2 // 3), is_centered=True)
            draw_text_with_custom_outline(self.screen, "Press Q to Quit", self.instruction_font, WHITE, GRAY,
                                         (WIDTH // 2, HEIGHT * 2 // 3 + 40), is_centered=True)

            pygame.display.flip()
            self.clock.tick(FPS)
            if platform.system() == "Emscripten":
                await asyncio.sleep(0)
        return False

    # запуск всей игры
    async def run_game(self):
        try:
            if hasattr(pygame.mixer.music, 'get_busy'):
                 pygame.mixer.music.play(-1)
        except pygame.error as e:
            print(f"Не удалось запустить музыку: {e}")

        while self.running:
            if self.game_over:
                should_restart = await self.game_over_screen_loop()
                if should_restart and self.running:
                    self.reset_game_state()
                elif not self.running:
                    break
            else:
                await self.game_loop_iteration()
        try:
            if hasattr(pygame.mixer.music, 'get_busy'):
                pygame.mixer.music.stop()
        except pygame.error:
            pass
        pygame.quit()

# запуск BlockBlast
if __name__ == "__main__":
    game_instance = BlockBlast()
    if platform.system() == "Emscripten":
        asyncio.ensure_future(game_instance.run_game())
    else:
        asyncio.run(game_instance.run_game())
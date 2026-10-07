import math
import queue
import sys
import time
import pygame

WIDTH, HEIGHT = 600, 600
FPS = 120

COLOR_BG = (8, 12, 20)
COLOR_TEXT = (220, 245, 255)

gui_queue = queue.Queue()


class JarvisOrb3D:

  def __init__(self):
    pygame.init()
    pygame.font.init()
    self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("J.A.R.V.I.S - ASSISTANT AI ON PC")
    self.clock = pygame.time.Clock()

    font_path = pygame.font.match_font("segoeui") or pygame.font.match_font(
        "arial"
    )
    self.font = pygame.font.Font(font_path, 20)

    self.overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    self.state = "IDLE"
    self.user_text = ""
    self.scale = 1.0
    self.real_volume = 0.0  # Biến lưu Volume thực tế từ giọng sếp

    self.angle_x = 0
    self.angle_y = 0
    self.angle_z = 0

    self.num_points = 85
    self.base_points = []
    phi = math.pi * (math.sqrt(5) - 1)

    for i in range(self.num_points):
      y = 1 - (i / float(self.num_points - 1)) * 2
      radius_at_y = math.sqrt(1 - y * y)
      theta = phi * i
      x = math.cos(theta) * radius_at_y
      z = math.sin(theta) * radius_at_y
      self.base_points.append((x, y, z))

    self.edges = []
    threshold = 0.50
    for i in range(self.num_points):
      p1 = self.base_points[i]
      for j in range(i + 1, self.num_points):
        p2 = self.base_points[j]
        dist = math.sqrt(
            (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2
        )
        if dist < threshold:
          self.edges.append((i, j))

  def update_state(self):
    while not gui_queue.empty():
      data = gui_queue.get()
      event_type = data.get("type")
      if event_type == "STATE":
        self.state = data.get("value")
      elif event_type == "USER_TEXT":
        self.user_text = data.get("value")
      elif event_type == "VOLUME":
        self.real_volume = data.get("value", 0.0)

  def draw_3d_sphere(self):
      center = (WIDTH // 2, HEIGHT // 2 - 30)
      base_radius = 110
      t = time.time()

      # Tốc độ quay 3D giữ nguyên cố định
      self.angle_x += 0.8
      self.angle_y += 1.2
      self.angle_z += 0.4

      # ƯU TIÊN CO GIÃN THEO CƯỜNG ĐỘ ÂM THANH THỰC TẾ
      if self.real_volume > 0.03:
        # Phóng to mạnh từ 1.00 đến 1.80 lần tùy độ to của giọng nói
        target_scale = 1.0 + (self.real_volume * 0.80)
      elif self.state == "AI_SPEAKING":
        target_scale = 1.06 + 0.08 * math.sin(t * 14.0)
        self.user_text = ""
      else:
        target_scale = 1.0 + 0.03 * math.sin(t * 2.5)
        self.user_text = ""

      # Lerp tốc độ cao (0.45) để phản hồi tức thì theo từng tiếng phát ra
      self.scale += (target_scale - self.scale) * 0.45
      current_radius = base_radius * self.scale

      rad_x, rad_y, rad_z = (
          math.radians(self.angle_x),
          math.radians(self.angle_y),
          math.radians(self.angle_z),
      )

      transformed_points = []
      for x, y, z in self.base_points:
        y1 = y * math.cos(rad_x) - z * math.sin(rad_x)
        z1 = y * math.sin(rad_x) + z * math.cos(rad_x)

        x2 = x * math.cos(rad_y) + z1 * math.sin(rad_y)
        z2 = -x * math.sin(rad_y) + z1 * math.cos(rad_y)

        x3 = x2 * math.cos(rad_z) - y1 * math.sin(rad_z)
        y3 = x2 * math.sin(rad_z) + y1 * math.cos(rad_z)

        screen_x = int(center[0] + x3 * current_radius)
        screen_y = int(center[1] + y3 * current_radius)
        transformed_points.append((screen_x, screen_y, z2))

      self.overlay.fill((0, 0, 0, 0))

      core_r = int(current_radius * 0.45)
      for r in range(core_r, 0, -6):
        alpha = int(140 * (r / core_r))
        pygame.draw.circle(self.overlay, (0, 180, 255, alpha), center, r)

      for i, j in self.edges:
        pt1, pt2 = transformed_points[i], transformed_points[j]
        avg_z = (pt1[2] + pt2[2]) / 2.0

        if avg_z > -0.65:
          depth_factor = (avg_z + 1.0) / 2.0
          g_c = int(140 + 115 * depth_factor)
          b_c = int(220 + 35 * depth_factor)
          alpha = int(30 + 210 * depth_factor)
          line_w = 2 if depth_factor > 0.6 else 1

          pygame.draw.line(
              self.overlay,
              (0, g_c, b_c, alpha),
              (pt1[0], pt1[1]),
              (pt2[0], pt2[1]),
              line_w,
          )

      for px, py, z in transformed_points:
        depth_factor = (z + 1.0) / 2.0
        node_r = int(2 + 2.5 * depth_factor)
        g_node = int(200 + 55 * depth_factor)
        alpha = int(50 + 205 * depth_factor)

        pygame.draw.circle(
            self.overlay, (80, g_node, 255, alpha), (px, py), node_r
        )

      self.screen.blit(self.overlay, (0, 0))

  def draw_text(self):
    if self.state == "USER_SPEAKING" and self.user_text:
      text_surface = self.font.render(
          f"Sếp: {self.user_text}", True, COLOR_TEXT
      )
      rect = text_surface.get_rect(center=(WIDTH // 2, HEIGHT - 70))

      bg_rect = rect.inflate(24, 12)
      bg_surf = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
      bg_surf.fill((10, 20, 35, 185))
      pygame.draw.rect(
          bg_surf,
          (0, 200, 255, 130),
          bg_surf.get_rect(),
          width=1,
          border_radius=6,
      )

      self.screen.blit(bg_surf, bg_rect.topleft)
      self.screen.blit(text_surface, rect)

  def run(self):
    running = True
    while running:
      self.clock.tick(FPS)
      for event in pygame.event.get():
        if event.type == pygame.QUIT:
          pygame.quit()
          sys.exit()

      self.update_state()
      self.screen.fill(COLOR_BG)
      self.draw_3d_sphere()
      self.draw_text()
      pygame.display.flip()


def start_gui():
  gui = JarvisOrb3D()
  gui.run()
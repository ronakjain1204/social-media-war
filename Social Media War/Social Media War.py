
import math
import random
import logging
from pathlib import Path

import pygame


# -------------------- Configuration --------------------

WIDTH = 900
HEIGHT = 500
FPS = 60

PLAYER_SPEED = 5
BULLET_SPEED = 10
MAX_BULLETS = 3
PLAYER_HEALTH = 5
AI_FIRE_RATE = 0.8  # Average firing attempts per second

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
PINK = (255, 20, 147)

ASSET_DIR = Path(__file__).resolve().parent

logging.basicConfig(
    filename=ASSET_DIR / "game.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)

pygame.init()

try:
    pygame.mixer.init()
except pygame.error:
    logging.warning("Audio is unavailable. Continuing without sound.")


SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Social Media Wars")

CLOCK = pygame.time.Clock()

HEALTH_FONT = pygame.font.SysFont("comicsans", 20)
TITLE_FONT = pygame.font.SysFont("comicsans", 60)
WINNER_FONT = pygame.font.SysFont("comicsans", 48)
MENU_FONT = pygame.font.SysFont("comicsans", 28)

BORDER = pygame.Rect(WIDTH // 2 - 5, 0, 10, HEIGHT)

PLAYER_HIT = pygame.USEREVENT + 1
OPPONENT_HIT = pygame.USEREVENT + 2


# -------------------- Asset Loading --------------------

def load_image(filename, size=None):
    """Load an image and optionally resize it."""
    path = ASSET_DIR / filename

    try:
        image = pygame.image.load(str(path)).convert_alpha()
        if size:
            image = pygame.transform.scale(image, size)
        return image
    except (pygame.error, FileNotFoundError) as error:
        logging.exception("Could not load image: %s", path)
        raise RuntimeError(f"Unable to load image: {filename}") from error


def load_background():
    """Load an available background image."""
    for filename in ("Background.png", "BG1.png", "BG2.png"):
        path = ASSET_DIR / filename
        if path.exists():
            image = pygame.image.load(str(path)).convert()
            return pygame.transform.scale(image, (WIDTH, HEIGHT))

    logging.warning("No background image found; using a plain background.")
    return None


def load_sound(filename):
    """Load a sound, allowing the game to run without it."""
    if not pygame.mixer.get_init():
        return None

    path = ASSET_DIR / filename

    try:
        return pygame.mixer.Sound(str(path))
    except (pygame.error, FileNotFoundError):
        logging.warning("Sound unavailable: %s", filename)
        return None


def play_sound(sound):
    """Play a sound if it was loaded successfully."""
    if sound is not None:
        sound.play()


BACKGROUND = load_background()
FACEBOOK_IMAGE = load_image("Facebook.png", (40, 40))
INSTAGRAM_IMAGE = load_image("Instagram.png", (40, 40))

HIT_SOUND = load_sound("Hit_sound.mp3")
FIRE_SOUND = load_sound("Fire_sound.mp3")


# -------------------- Reusable Game Functions --------------------

def draw_text_centered(text, font, color, y):
    """Draw centered text at a specified vertical position."""
    rendered = font.render(text, True, color)
    SCREEN.blit(
        rendered,
        (WIDTH // 2 - rendered.get_width() // 2, y),
    )


def draw_game(blue, pink, blue_bullets, pink_bullets,
              blue_health, pink_health):
    """Render the background, players, health and projectiles."""
    if BACKGROUND is not None:
        SCREEN.blit(BACKGROUND, (0, 0))
    else:
        SCREEN.fill((35, 35, 45))

    pygame.draw.rect(SCREEN, BLACK, BORDER)

    blue_text = HEALTH_FONT.render(
        f"Health: {blue_health}", True, WHITE
    )
    pink_text = HEALTH_FONT.render(
        f"Health: {pink_health}", True, WHITE
    )

    SCREEN.blit(blue_text, (10, 10))
    SCREEN.blit(
        pink_text,
        (WIDTH - pink_text.get_width() - 10, 10),
    )

    SCREEN.blit(FACEBOOK_IMAGE, blue)
    SCREEN.blit(INSTAGRAM_IMAGE, pink)

    for bullet in blue_bullets:
        pygame.draw.rect(SCREEN, BLUE, bullet)

    for bullet in pink_bullets:
        pygame.draw.rect(SCREEN, PINK, bullet)

    pygame.display.flip()


def move_player(keys, player, controls, bounds):
    """Move a player according to the pressed keys and boundaries."""
    left, right, up, down = controls

    if keys[left]:
        player.x -= PLAYER_SPEED
    if keys[right]:
        player.x += PLAYER_SPEED
    if keys[up]:
        player.y -= PLAYER_SPEED
    if keys[down]:
        player.y += PLAYER_SPEED

    player.clamp_ip(bounds)


def move_players(keys, blue, pink):
    """Handle movement for both sides of the battlefield."""
    blue_bounds = pygame.Rect(
        0, 0, BORDER.left, HEIGHT
    )
    pink_bounds = pygame.Rect(
        BORDER.right, 0, WIDTH - BORDER.right, HEIGHT
    )

    move_player(
        keys,
        blue,
        (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s),
        blue_bounds,
    )

    move_player(
        keys,
        pink,
        (
            pygame.K_LEFT,
            pygame.K_RIGHT,
            pygame.K_UP,
            pygame.K_DOWN,
        ),
        pink_bounds,
    )


def create_bullet(player, direction):
    """Create a projectile pointing toward the opponent."""
    if direction == 1:
        x = player.right
    else:
        x = player.left - 6

    return pygame.Rect(x, player.centery - 2, 6, 4)


def fire_bullet(player, bullets, direction):
    """Fire if the projectile limit has not been reached."""
    if len(bullets) >= MAX_BULLETS:
        return

    bullets.append(create_bullet(player, direction))
    play_sound(FIRE_SOUND)


def handle_bullets(blue_bullets, pink_bullets, blue, pink):
    """Move bullets, detect collisions and remove expired bullets."""
    blue_hits = 0
    pink_hits = 0

    for bullet in blue_bullets[:]:
        bullet.x += BULLET_SPEED

        if bullet.colliderect(pink):
            blue_bullets.remove(bullet)
            blue_hits += 1
        elif bullet.left > WIDTH:
            blue_bullets.remove(bullet)

    for bullet in pink_bullets[:]:
        bullet.x -= BULLET_SPEED

        if bullet.colliderect(blue):
            pink_bullets.remove(bullet)
            pink_hits += 1
        elif bullet.right < 0:
            pink_bullets.remove(bullet)

    return blue_hits, pink_hits


def update_ai(pink, blue, pink_bullets, elapsed_seconds):
    """Move the AI toward the player's height and fire periodically."""
    if pink.centery < blue.centery - 10:
        pink.y += PLAYER_SPEED
    elif pink.centery > blue.centery + 10:
        pink.y -= PLAYER_SPEED

    ai_bounds = pygame.Rect(
        BORDER.right, 0, WIDTH - BORDER.right, HEIGHT
    )
    pink.clamp_ip(ai_bounds)

    # Convert a per-second firing rate into a frame-independent chance.
    chance = 1 - math.exp(-AI_FIRE_RATE * elapsed_seconds)

    if random.random() < chance:
        fire_bullet(pink, pink_bullets, -1)


# -------------------- Menus --------------------

def draw_menu(title, options):
    """Render a title and a list of menu options."""
    SCREEN.fill(BLACK)
    draw_text_centered(title, TITLE_FONT, WHITE, 130)

    for index, option in enumerate(options):
        draw_text_centered(
            option, MENU_FONT, WHITE, 260 + index * 45
        )

    pygame.display.flip()


def start_menu():
    """Return 'single', 'two', or None if the game is closed."""
    while True:
        draw_menu(
            "Social Media Wars",
            [
                "Press 1 for Single Player",
                "Press 2 for Two Player",
                "Press Q to Quit",
            ],
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    return "single"
                if event.key == pygame.K_2:
                    return "two"
                if event.key == pygame.K_q:
                    return None

        CLOCK.tick(FPS)


def end_game_menu(winner_text):
    """Display the result and return the player's next choice."""
    while True:
        draw_menu(
            winner_text,
            [
                "Press R for Rematch",
                "Press M for Main Menu",
                "Press Q to Quit",
            ],
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return "rematch"
                if event.key == pygame.K_m:
                    return "menu"
                if event.key == pygame.K_q:
                    return "quit"

        CLOCK.tick(FPS)


# -------------------- Game Loop --------------------

def play_round(mode):
    """Run one round and return its result."""
    blue = pygame.Rect(280, 230, 40, 40)
    pink = pygame.Rect(580, 230, 40, 40)

    blue_health = PLAYER_HEALTH
    pink_health = PLAYER_HEALTH

    blue_bullets = []
    pink_bullets = []

    logging.info("Starting round in %s mode.", mode)

    while True:
        elapsed_seconds = CLOCK.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "menu"

                if (
                    event.key == pygame.K_LCTRL
                    and len(blue_bullets) < MAX_BULLETS
                ):
                    fire_bullet(blue, blue_bullets, 1)

                if (
                    mode == "two"
                    and event.key == pygame.K_RCTRL
                    and len(pink_bullets) < MAX_BULLETS
                ):
                    fire_bullet(pink, pink_bullets, -1)

        keys = pygame.key.get_pressed()
        move_player(
            keys,
            blue,
            (pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s),
            pygame.Rect(0, 0, BORDER.left, HEIGHT),
        )

        if mode == "two":
            move_player(
                keys,
                pink,
                (
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                    pygame.K_UP,
                    pygame.K_DOWN,
                ),
                pygame.Rect(
                    BORDER.right, 0, WIDTH - BORDER.right, HEIGHT
                ),
            )
        else:
            update_ai(
                pink, blue, pink_bullets, elapsed_seconds
            )

        blue_hits, pink_hits = handle_bullets(
            blue_bullets, pink_bullets, blue, pink
        )

        blue_health -= pink_hits
        pink_health -= blue_hits

        if blue_hits or pink_hits:
            play_sound(HIT_SOUND)

        draw_game(
            blue,
            pink,
            blue_bullets,
            pink_bullets,
            max(0, blue_health),
            max(0, pink_health),
        )

        if blue_health <= 0:
            logging.info("Instagram won the round.")
            return "Instagram Wins!"

        if pink_health <= 0:
            logging.info("Facebook won the round.")
            return "Facebook Wins!"


def main():
    """Manage menus, rounds, rematches and application shutdown."""
    try:
        while True:
            mode = start_menu()

            if mode is None:
                break

            while True:
                result = play_round(mode)

                if result == "quit":
                    return

                if result == "menu":
                    break

                choice = end_game_menu(result)

                if choice == "quit":
                    return

                if choice == "menu":
                    break

                # 'rematch' starts a fresh round in the same mode.

    except Exception:
        logging.exception("Unexpected game error.")
        raise

    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

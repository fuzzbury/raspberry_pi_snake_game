import sense_hat
from sense_hat import SenseHat
import time
import enum
import random
import sys
import tty
import termios
import select
import os
import threading

BOARD_SIZE = 8

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class NonBlockingKeyboard:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None


# Shared last-key storage (thread-safe)
last_key_pressed = None
key_lock = threading.Lock()


def key_reader(stop_event):
    """Background thread: reads keys and stores the last key pressed."""
    global last_key_pressed
    with NonBlockingKeyboard() as kb:
        while not stop_event.is_set():
            k = kb.get_key()
            if k is None:
                time.sleep(0.01)
                continue
            # handle escape sequences for arrows
            if k == '\x1b':
                k2 = kb.get_key()
                if k2 == '[':
                    k3 = kb.get_key()
                    if k3:
                        mapping = {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}
                        mapped = mapping.get(k3)
                        with key_lock:
                            last_key_pressed = mapped
                        logger.debug(f"key_reader mapped arrow: {repr(mapped)}")
                        continue
                # unrecognized escape sequence; skip
                continue
            # normal key
            with key_lock:
                last_key_pressed = k
            logger.debug(f"key_reader read key: {repr(k)}")
    logger.debug("key_reader exiting")

class Direction(enum.Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4


class Snake:
    """Represents a snake in the game."""
    
    def __init__(self, start_pos, start_direction, color):
        """
        Initialize a snake.
        
        Args:
            start_pos: Tuple (x, y) for the starting head position
            start_direction: Direction enum for initial direction
            color: Tuple (r, g, b) for the snake's color
        """
        self.head = list(start_pos)
        self.tail = []
        self.direction = start_direction
        self.next_direction = start_direction
        self.color = color
        self.growth_counter = 0
    
    def set_direction(self, direction):
        """Set the next direction for the snake."""
        self.next_direction = direction
    
    def update(self):
        """Update the snake's position."""
        # Update direction (prevents 180-degree turns)
        if not self._is_opposite_direction(self.direction, self.next_direction):
            self.direction = self.next_direction
        
        old_head = [self.head[0], self.head[1]]
        
        # Move head based on direction
        if self.direction == Direction.UP:
            self.head[1] -= 1
        elif self.direction == Direction.DOWN:
            self.head[1] += 1
        elif self.direction == Direction.LEFT:
            self.head[0] -= 1
        elif self.direction == Direction.RIGHT:
            self.head[0] += 1
        
        # Clamp to board boundaries
        self.head[0] = min(max(self.head[0], 0), BOARD_SIZE - 1)
        self.head[1] = min(max(self.head[1], 0), BOARD_SIZE - 1)
        
        # Update tail
        if old_head != self.head:
            self.tail.insert(0, tuple(old_head))
            # Only grow if growth counter > 0
            if self.growth_counter == 0:
                self.tail.pop()
            

            self.growth_counter -= 1
            self.growth_counter = max(self.growth_counter, 0)
    
    def grow(self, amount=1):
        """Add segments to the snake's growth counter."""
        self.growth_counter += amount
    
    def get_all_positions(self):
        """Return all positions occupied by the snake."""
        return [tuple(self.head)] + self.tail
    
    def display(self, sense):
        """Display the snake on the Sense HAT."""
        for (x, y) in self.tail:
            sense.set_pixel(x, y, self.color)
        sense.set_pixel(self.head[0], self.head[1], self.color)
    
    @staticmethod
    def _is_opposite_direction(current, next_dir):
        """Check if next direction is opposite to current direction."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites.get(current) == next_dir


def main():
    global last_key_pressed
    sense = SenseHat()
    sense.clear()
    
    # Colors
    green = (0, 255, 0)
    blue = (0, 0, 255)
    red = (255, 0, 0)
    
    # Setup joystick constants
    up_key = sense_hat.DIRECTION_UP
    down_key = sense_hat.DIRECTION_DOWN
    left_key = sense_hat.DIRECTION_LEFT
    right_key = sense_hat.DIRECTION_RIGHT
    pressed_key = sense_hat.ACTION_PRESSED
    
    # Create two snakes
    # Start snakes in opposite corners
    snake1 = Snake((0, 0), Direction.RIGHT, green)  # Joystick-controlled (top-left)
    snake2 = Snake((BOARD_SIZE - 1, BOARD_SIZE - 1), Direction.LEFT, blue)    # ASDW-controlled (bottom-right)
    
    # No global keyboard package used; snake2 is controlled via ASDW/arrow keys.
    
    apple = None
    time_since_last_apple = 0

    stop_event = threading.Event()
    reader_thread = threading.Thread(target=key_reader, args=(stop_event,), daemon=True)
    reader_thread.start()
    try:
        while True:
            # Generate apple if needed
            if apple is None:
                all_snake_positions = set(snake1.get_all_positions() + snake2.get_all_positions())
                no_snake_pixels = [(x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE) if (x, y) not in all_snake_positions]
                
                if no_snake_pixels:
                    apple = random.choice(no_snake_pixels)
            
            # Handle joystick input for snake1
            for event in sense.stick.get_events():
                if event.action == pressed_key:
                    if event.direction == up_key:
                        snake1.set_direction(Direction.UP)
                    elif event.direction == down_key:
                        snake1.set_direction(Direction.DOWN)
                    elif event.direction == left_key:
                        snake1.set_direction(Direction.LEFT)
                    elif event.direction == right_key:
                        snake1.set_direction(Direction.RIGHT)

            # Read last key pressed by the background reader and clear it
            with key_lock:
                k = last_key_pressed
                last_key_pressed = None
            logger.debug(f"main read last_key_pressed: {repr(k)}")

            if k:
                if k == 'w':
                    snake2.set_direction(Direction.UP)
                elif k == 's':
                    snake2.set_direction(Direction.DOWN)
                elif k == 'a':
                    snake2.set_direction(Direction.LEFT)
                elif k == 'd':
                    snake2.set_direction(Direction.RIGHT)

            # Update both snakes
            snake1.update()
            snake2.update()
            
            # Update apple timer
            time_since_last_apple += 1
            
            # Check apple collision for snake1s
            if apple and snake1.head == list(apple):
                snake1.grow(1)
                time_since_last_apple = 0
                apple = None
            
            # Check apple collision for snake2
            if apple and snake2.head == list(apple):
                snake2.grow(1)
                time_since_last_apple = 0
                apple = None
            
            # Clear and display
            sense.clear()
            
            if apple:
                sense.set_pixel(apple[0], apple[1], red)
            
            snake1.display(sense)
            snake2.display(sense)
            
            time.sleep(0.5)
    finally:
        stop_event.set()
        reader_thread.join(timeout=0.5)


if __name__ == "__main__":  
    main()
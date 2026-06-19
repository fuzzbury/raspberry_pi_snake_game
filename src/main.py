
#to install a virtual enviroment with access to the system packages
#Tools -> Open System Shell
#python3 -m venv --system-site-packages /home/alex/Documents/thonny_experiment/python_venv

#then
#close window
#Tools->options->intrepreter and select you folder above (go into bin and find python3)

#Tools -> Open System Shell
#pip install pynput
#
# WHY python3 -m venv --system-site-packages
# A regular venv is deliberately isolated — 
# it only sees packages installed via pip into that venv, 
# nothing from the system. 
# This is the whole point of a venv (reproducible, conflict-free environments).

# RTIMU was never published to PyPI because it's a 
# C library compiled specifically for the Raspberry Pi hardware 
# by the Raspberry Pi Foundation and shipped as part of Raspberry Pi OS via apt. 
# So there's literally nothing for pip to download and install — 
# it doesn't exist as a pip package.

# That's why --system-site-packages is the fix: 
# it pokes a hole in the isolation just enough to let the venv 
# see the system's apt-installed packages (like RTIMU) 
# while still keeping its own pip packages separate.

import sense_hat
from sense_hat import SenseHat
import time
import enum
import random
import logging
from pynput import keyboard #pip install pynput

BOARD_SIZE = 8

# Log to a file instead of stdout so it doesn't interfere with game output.
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.FileHandler('snake_debug.log')]
)
logger = logging.getLogger(__name__)


class Direction(enum.Enum):
    # Four possible movement directions for a snake
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4


class Snake:
    """Represents a snake in the game."""

    def __init__(self, start_pos, start_direction, color):
        # Head is a mutable list so we can update x/y in place each tick
        self.head = list(start_pos)
        # Tail is an ordered list of (x, y) tuples, newest segment first
        self.tail = []
        self.direction = start_direction
        # next_direction buffers player input so the turn only takes effect on the next update
        self.next_direction = start_direction
        self.color = color
        # How many extra segments are still to be added on future updates
        self.growth_counter = 0

    def set_direction(self, direction):
        """Queue a direction change; it is applied on the next call to update()."""
        self.next_direction = direction

    def update(self):
        """Advance the snake one step in its current direction."""
        # Ignore the queued direction if it would reverse the snake back on itself
        if not self._is_opposite_direction(self.direction, self.next_direction):
            self.direction = self.next_direction

        # Save the current head position before moving so we can push it onto the tail
        old_head = [self.head[0], self.head[1]]

        # Move the head one cell in the current direction
        if self.direction == Direction.UP:
            self.head[1] -= 1
        elif self.direction == Direction.DOWN:
            self.head[1] += 1
        elif self.direction == Direction.LEFT:
            self.head[0] -= 1
        elif self.direction == Direction.RIGHT:
            self.head[0] += 1

        # Keep the head clamped inside the 8x8 board
        #self.head[0] = min(max(self.head[0], 0), BOARD_SIZE - 1)
        #self.head[1] = min(max(self.head[1], 0), BOARD_SIZE - 1)

        # Only extend the tail if the head actually moved (hitting a wall keeps it still)
        if old_head != self.head:
            # The old head position becomes the newest tail segment
            self.tail.insert(0, old_head)

            if self.growth_counter == 0:
                # No pending growth — drop the last tail segment to keep the length the same
                self.tail.pop()

            # Consume one unit of pending growth (floor at 0 to avoid going negative)
            self.growth_counter = max(self.growth_counter - 1, 0)

    def is_head_outside_board(self):
        """Return True if the snake's head is outside the 8x8 board."""
        return not (0 <= self.head[0] < BOARD_SIZE and 0 <= self.head[1] < BOARD_SIZE)

    def grow(self, amount=1):
        """Schedule the snake to gain `amount` extra segments on upcoming updates."""
        self.growth_counter += amount

    def get_all_positions(self):
        """Return every grid cell currently occupied by this snake (head + all tail segments)."""
        return [self.head] + self.tail

    def display(self, sense):
        """Light up every cell this snake occupies on the Sense HAT LED matrix."""
        for (x, y) in self.tail:
            sense.set_pixel(x, y, self.color) 
        if not self.is_head_outside_board():
            sense.set_pixel(self.head[0], self.head[1], self.color)

    @staticmethod
    def _is_opposite_direction(current, next_dir):
        """Return True if next_dir would turn the snake directly back on itself."""
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites.get(current) == next_dir


def main():
    # Initialise the Sense HAT and blank all LEDs
    sense = SenseHat()
    sense.clear()

    # Track the last key pressed by snake 2; updated by the pynput listener thread
    last_key = [None]

    def on_press(key):
        try:
            last_key[0] = key.char
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    # Colours for each game element on the LED matrix
    green = (0, 255, 0)
    blue = (0, 0, 255)
    red = (255, 0, 0)

    # Snake 1: starts top-left, moves right, controlled by the Sense HAT joystick
    snake1 = Snake((0, 0), Direction.RIGHT, green)
    # Snake 2: starts bottom-right, moves left, controlled by WASD on the keyboard
    snake2 = Snake((BOARD_SIZE - 1, BOARD_SIZE - 1), Direction.LEFT, blue)

    # Apple position; None means one needs to be spawned at the start of the next tick
    apple = None

    while True:
        # --- Spawn apple ---
        # If there is no apple on the board, pick a random unoccupied cell and place one
        if apple is None:
            occupied = snake1.get_all_positions() + snake2.get_all_positions()
            empty_cells = [
                [x, y]
                for x in range(BOARD_SIZE)
                for y in range(BOARD_SIZE)
                if [x, y] not in occupied
            ]
            if empty_cells:
                apple = random.choice(empty_cells)

        # --- Snake 1 input: Sense HAT joystick ---
        # get_events() drains all joystick events queued since the last call
        for event in sense.stick.get_events():
            if event.action == sense_hat.ACTION_PRESSED:
                if event.direction == sense_hat.DIRECTION_UP:
                    snake1.set_direction(Direction.UP)
                elif event.direction == sense_hat.DIRECTION_DOWN:
                    snake1.set_direction(Direction.DOWN)
                elif event.direction == sense_hat.DIRECTION_LEFT:
                    snake1.set_direction(Direction.LEFT)
                elif event.direction == sense_hat.DIRECTION_RIGHT:
                    snake1.set_direction(Direction.RIGHT)

        # --- Snake 2 input: keyboard (WASD) ---
        key = last_key[0]
        last_key[0] = None
        logger.debug(f"key pressed: {key}")

        if key == 'w':
            snake2.set_direction(Direction.UP)
        elif key == 's':
            snake2.set_direction(Direction.DOWN)
        elif key == 'a':
            snake2.set_direction(Direction.LEFT)
        elif key == 'd':
            snake2.set_direction(Direction.RIGHT)

        # --- Update ---
        # Advance both snakes one step according to their current directions
        snake1.update()
        snake2.update()

        # Check if snake 1's head landed on the apple
        if apple and snake1.head == apple:
            snake1.grow(1)
            apple = None

        # Check if snake 2's head landed on the apple
        if apple and snake2.head == apple:
            snake2.grow(1)
            apple = None

        # --- Draw ---
        # Clear the LED matrix, then repaint the apple and both snakes
        sense.clear()
        if apple:
            sense.set_pixel(apple[0], apple[1], red)
        snake1.display(sense)
        snake2.display(sense)
        #test for game over conditions
        alive1 = True
        alive2 = True


        if (snake1.head in snake1.tail 
            or snake1.head in snake2.get_all_positions() 
            or snake1.is_head_outside_board()):
            alive1 = False

        if (snake2.head in snake2.tail
            or snake2.head in snake1.get_all_positions() 
            or snake2.is_head_outside_board()):
            alive2 = False
    
        # Wait before the next tick — reducing this value speeds the game up
        time.sleep(0.5)
        if not alive1 and not alive2:
            sense.show_message("Draw!", text_colour=[255, 0, 0])
            break
        elif not alive1:
            sense.show_message("Blue!", text_colour=blue)
            break
        elif not alive2:
            sense.show_message("Green!", text_colour=green)
            break

    listener.stop()

if __name__ == "__main__":
    main()


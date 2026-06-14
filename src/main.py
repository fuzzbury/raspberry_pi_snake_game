import sense_hat
from sense_hat import SenseHat
import time
import enum
import random


class Direction(enum.Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    
    RIGHT = 4

sense = SenseHat()
sense.clear()

green = (0, 255, 0)
light_green = (0, 128, 0)
red = (255, 0, 0)
yellow = (255, 255, 0)
white = (255, 255, 255)
nothing = (0, 0, 0)
pink = (255, 0, 255)


up_key = sense_hat.DIRECTION_UP
down_key = sense_hat.DIRECTION_DOWN
left_key = sense_hat.DIRECTION_LEFT
right_key = sense_hat.DIRECTION_RIGHT
pressed_key = sense_hat.ACTION_PRESSED


def update_snake(tail, head, do_grow):
    if len(tail) > 0:
        tail.insert(0, (head[0], head[1]))
        if not do_grow:
            tail.pop()

def main():
    head = [0,0]
    tail=[] 
    direction = Direction.RIGHT
    apple = None
    time_since_last_apple = 0



    while True:
        if apple is None:
            #get pixels where there is no snake
            no_snake_pixels = [(x, y) for x in range(8) for y in range(8) if (x, y) not in tail and (x, y) != (head[0], head[1])]
            #add head
            no_snake_pixels.append((head[0], head[1]))

            #choose random pixel for apple  that is not occupied by the snake
            offset= random.randint(0, len(no_snake_pixels)-1)
            apple = no_snake_pixels[offset]

        for event in sense.stick.get_events():
            if event.action == pressed_key:
                if event.direction == up_key:
                    direction = Direction.UP
                elif event.direction == down_key:
                    direction = Direction.DOWN
                elif event.direction == left_key:
                    direction = Direction.LEFT
                elif event.direction == right_key:
                    direction = Direction.RIGHT

        old_head = [head[0], head[1]]

        if direction == Direction.UP:
            head[1] -= 1
        elif direction == Direction.DOWN:
            head[1] += 1
        elif direction == Direction.LEFT:
            head[0] -= 1
        elif direction == Direction.RIGHT:
            head[0] += 1

        
        head[0] = min(max(head[0], 0), 7)
        head[1] = min(max(head[1], 0), 7)

        if old_head != head:
            update_snake(tail, old_head, do_grow = time_since_last_apple < 4)

        sense.clear()

        time_since_last_apple  += 1
        if apple is not None:

            if head[0] == apple[0] and head[1] == apple[1]:
                tail.append((head[0], head[1]))
                time_since_last_apple = 0
                apple = None

        if apple is not None:
            sense.set_pixel(apple[0], apple[1], red)

        for (x,y) in tail:
            sense.set_pixel(x, y, green)


        sense.set_pixel(head[0], head[1], green)
        time.sleep(0.5)


if __name__ == "__main__":  
    main()
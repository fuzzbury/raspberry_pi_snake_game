# debug_kb.py
import sys, tty, termios, select

fd = sys.stdin.fileno()
old = termios.tcgetattr(fd)
tty.setcbreak(fd)
print("Press keys (q to quit)...")

try:
    while True:
        if select.select([sys.stdin], [], [], 0.1)[0]:
            c = sys.stdin.read(1)
            print("READ:", repr(c))
            if c == 'q':
                break
finally:
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print("Exiting, terminal restored.")
"""Block Drop - a falling-block puzzle game built with tkinter (no extra installs).

Controls:
    Left / Right   move
    Down           soft drop
    Up / X         rotate clockwise
    Z              rotate counter-clockwise
    Space          hard drop
    C              hold piece
    P              pause
    R              restart
    Esc            quit
"""

import random
import tkinter as tk

COLS, ROWS = 10, 20
CELL = 30
SIDE = 180
WIDTH = COLS * CELL + SIDE
HEIGHT = ROWS * CELL

BG = "#14161f"
GRID = "#1e2130"
TEXT = "#e6e8f0"
DIM = "#7a7f96"

# Seven four-cell shapes, each as (cells, color). Cells are (col, row) offsets.
SHAPES = {
    "I": ([(0, 1), (1, 1), (2, 1), (3, 1)], "#5ec8d8"),
    "O": ([(1, 0), (2, 0), (1, 1), (2, 1)], "#e8c547"),
    "T": ([(1, 0), (0, 1), (1, 1), (2, 1)], "#b07cd8"),
    "S": ([(1, 0), (2, 0), (0, 1), (1, 1)], "#6cc070"),
    "Z": ([(0, 0), (1, 0), (1, 1), (2, 1)], "#e06464"),
    "J": ([(0, 0), (0, 1), (1, 1), (2, 1)], "#5a82e0"),
    "L": ([(2, 0), (0, 1), (1, 1), (2, 1)], "#e8954a"),
}

LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}


def rotate(cells, size, clockwise=True):
    if clockwise:
        return [(size - 1 - y, x) for x, y in cells]
    return [(y, size - 1 - x) for x, y in cells]


class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.cells, self.color = SHAPES[kind]
        self.cells = list(self.cells)
        self.size = 4 if kind in ("I", "O") else 3
        self.x = COLS // 2 - self.size // 2
        self.y = -1 if kind == "I" else 0

    def blocks(self, dx=0, dy=0, cells=None):
        return [(self.x + cx + dx, self.y + cy + dy) for cx, cy in (cells or self.cells)]


class Game:
    def __init__(self, root):
        self.root = root
        root.title("Block Drop")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack()
        root.bind("<Key>", self.on_key)
        self.after_id = None
        self.reset()

    # ---------- state ----------
    def reset(self):
        self.board = [[None] * COLS for _ in range(ROWS)]
        self.bag = []
        self.score = 0
        self.lines = 0
        self.level = 1
        self.hold = None
        self.can_hold = True
        self.paused = False
        self.over = False
        self.next_kind = self.draw_from_bag()
        self.spawn()
        self.schedule()

    def draw_from_bag(self):
        if not self.bag:
            self.bag = list(SHAPES)
            random.shuffle(self.bag)
        return self.bag.pop()

    def spawn(self, kind=None):
        if kind is None:
            kind = self.next_kind
            self.next_kind = self.draw_from_bag()
        self.piece = Piece(kind)
        if not self.fits(self.piece.blocks()):
            self.over = True

    def fits(self, blocks):
        for x, y in blocks:
            if x < 0 or x >= COLS or y >= ROWS:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    def drop_interval(self):
        return max(60, 800 - (self.level - 1) * 70)

    # ---------- actions ----------
    def move(self, dx, dy):
        if self.fits(self.piece.blocks(dx, dy)):
            self.piece.x += dx
            self.piece.y += dy
            return True
        return False

    def turn(self, clockwise):
        if self.piece.kind == "O":
            return
        new = rotate(self.piece.cells, self.piece.size, clockwise)
        # Simple wall kicks: try nudging sideways / up.
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)):
            if self.fits(self.piece.blocks(dx, dy, new)):
                self.piece.cells = new
                self.piece.x += dx
                self.piece.y += dy
                return

    def hard_drop(self):
        dist = 0
        while self.move(0, 1):
            dist += 1
        self.score += dist * 2
        self.lock()

    def hold_piece(self):
        if not self.can_hold:
            return
        current = self.piece.kind
        if self.hold is None:
            self.hold = current
            self.spawn()
        else:
            self.hold, swap = current, self.hold
            self.spawn(swap)
        self.can_hold = False

    def lock(self):
        for x, y in self.piece.blocks():
            if y < 0:
                self.over = True
                return
            self.board[y][x] = self.piece.color
        self.clear_lines()
        self.can_hold = True
        self.spawn()

    def clear_lines(self):
        remaining = [row for row in self.board if any(c is None for c in row)]
        cleared = ROWS - len(remaining)
        if cleared:
            self.board = [[None] * COLS for _ in range(cleared)] + remaining
            self.lines += cleared
            self.score += LINE_SCORES[cleared] * self.level
            self.level = self.lines // 10 + 1

    def ghost_y(self):
        dy = 0
        while self.fits(self.piece.blocks(0, dy + 1)):
            dy += 1
        return dy

    # ---------- loop ----------
    def schedule(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(self.drop_interval(), self.tick)

    def tick(self):
        self.after_id = None
        if not self.paused and not self.over:
            if not self.move(0, 1):
                self.lock()
        self.render()
        self.schedule()

    def on_key(self, event):
        key = event.keysym.lower()
        if key == "escape":
            self.root.destroy()
            return
        if key == "r":
            self.reset()
            self.render()
            return
        if self.over:
            return
        if key == "p":
            self.paused = not self.paused
        elif self.paused:
            return
        elif key == "left":
            self.move(-1, 0)
        elif key == "right":
            self.move(1, 0)
        elif key == "down":
            if self.move(0, 1):
                self.score += 1
        elif key in ("up", "x"):
            self.turn(True)
        elif key == "z":
            self.turn(False)
        elif key == "space":
            self.hard_drop()
        elif key == "c":
            self.hold_piece()
        self.render()

    # ---------- drawing ----------
    def cell(self, x, y, color, outline_only=False, size=CELL, ox=0, oy=0):
        x0, y0 = ox + x * size, oy + y * size
        if outline_only:
            self.canvas.create_rectangle(x0 + 2, y0 + 2, x0 + size - 2, y0 + size - 2,
                                         outline=color, width=2)
        else:
            self.canvas.create_rectangle(x0 + 1, y0 + 1, x0 + size - 1, y0 + size - 1,
                                         fill=color, outline="")
            self.canvas.create_rectangle(x0 + 1, y0 + 1, x0 + size - 1, y0 + 5,
                                         fill="#ffffff", outline="", stipple="gray25")

    def preview(self, kind, ox, oy, faded=False):
        cells, color = SHAPES[kind]
        if faded:
            color = DIM
        size = 22
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        w = (max(xs) - min(xs) + 1) * size
        h = (max(ys) - min(ys) + 1) * size
        bx = ox + (SIDE - 40 - w) / 2 - min(xs) * size
        by = oy + (60 - h) / 2 - min(ys) * size
        for cx, cy in cells:
            self.cell(cx, cy, color, size=size, ox=bx, oy=by)

    def render(self):
        c = self.canvas
        c.delete("all")
        for x in range(COLS + 1):
            c.create_line(x * CELL, 0, x * CELL, HEIGHT, fill=GRID)
        for y in range(ROWS + 1):
            c.create_line(0, y * CELL, COLS * CELL, y * CELL, fill=GRID)

        for y, row in enumerate(self.board):
            for x, color in enumerate(row):
                if color:
                    self.cell(x, y, color)

        if not self.over:
            g = self.ghost_y()
            for x, y in self.piece.blocks(0, g):
                if y >= 0:
                    self.cell(x, y, self.piece.color, outline_only=True)
            for x, y in self.piece.blocks():
                if y >= 0:
                    self.cell(x, y, self.piece.color)

        # side panel
        px = COLS * CELL + 20
        c.create_rectangle(COLS * CELL, 0, WIDTH, HEIGHT, fill="#10121a", outline="")
        c.create_text(px, 20, text="NEXT", fill=DIM, anchor="w", font=("Segoe UI", 11, "bold"))
        self.preview(self.next_kind, px, 35)
        c.create_text(px, 120, text="HOLD", fill=DIM, anchor="w", font=("Segoe UI", 11, "bold"))
        if self.hold:
            self.preview(self.hold, px, 135, faded=not self.can_hold)

        y = 230
        for label, value in (("SCORE", self.score), ("LINES", self.lines), ("LEVEL", self.level)):
            c.create_text(px, y, text=label, fill=DIM, anchor="w", font=("Segoe UI", 11, "bold"))
            c.create_text(px, y + 24, text=str(value), fill=TEXT, anchor="w",
                          font=("Segoe UI", 18, "bold"))
            y += 65

        c.create_text(px, HEIGHT - 70, anchor="nw", fill=DIM, font=("Segoe UI", 8),
                      text="←→ move  ↓ soft drop\n↑/X Z rotate  Space drop\nC hold  P pause  R restart")

        if self.paused or self.over:
            c.create_rectangle(0, HEIGHT / 2 - 50, COLS * CELL, HEIGHT / 2 + 50,
                               fill="#000000", stipple="gray50", outline="")
            title = "PAUSED" if self.paused else "GAME OVER"
            c.create_text(COLS * CELL / 2, HEIGHT / 2 - 10, text=title, fill=TEXT,
                          font=("Segoe UI", 24, "bold"))
            c.create_text(COLS * CELL / 2, HEIGHT / 2 + 25, fill=DIM, font=("Segoe UI", 10),
                          text="P to resume" if self.paused else "R to restart")


def main():
    root = tk.Tk()
    game = Game(root)
    game.render()
    root.mainloop()


if __name__ == "__main__":
    main()

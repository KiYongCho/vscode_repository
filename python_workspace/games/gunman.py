"""Dusty Draw - a quick-draw western shooting game built with tkinter (no extra installs).

Outlaws pop up in the windows, doorways and behind barrels of a frontier town.
Shoot them before they draw and fire on you - but don't hit the townsfolk!

Controls:
    Mouse          aim
    Left click     shoot
    Right click/R  reload (6-shot revolver)
    P              pause
    Enter          start / restart
    Esc            quit
"""

import random
import time
import tkinter as tk

W, H = 900, 600
GROUND = 470

SKY_TOP = (240, 150, 80)
SKY_BOTTOM = (250, 215, 150)
TEXT = "#fff6e0"
SHADOW = "#2a1a10"

# Where people can appear: (x, y of feet, kind of cover)
SPOTS = [
    (130, 215, "window"), (230, 215, "window"),
    (180, 395, "door"),
    (420, 175, "window"), (520, 175, "window"),
    (470, 395, "door"),
    (720, 235, "window"),
    (740, 395, "door"),
    (330, 470, "barrel"), (610, 470, "barrel"), (850, 470, "barrel"),
]


def hex_color(rgb):
    return "#%02x%02x%02x" % rgb


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Target:
    def __init__(self, spot, kind, now, level):
        self.x, self.y, self.cover = spot
        self.kind = kind  # "outlaw" or "civilian"
        self.born = now
        speed = max(0.45, 1.0 - (level - 1) * 0.07)
        if kind == "outlaw":
            self.draw_at = now + random.uniform(0.6, 1.3) * speed
            self.fire_at = self.draw_at + random.uniform(0.55, 0.9) * speed
        else:
            self.leave_at = now + random.uniform(1.4, 2.2)
        self.dead_at = None
        self.hit_box = (self.x - 22, self.y - 95, self.x + 22, self.y)

    def drawn(self, now):
        return self.kind == "outlaw" and now >= self.draw_at

    def hit(self, mx, my):
        x0, y0, x1, y1 = self.hit_box
        return x0 <= mx <= x1 and y0 <= my <= y1


class Game:
    def __init__(self, root):
        self.root = root
        root.title("Dusty Draw")
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=W, height=H, highlightthickness=0, cursor="none")
        self.canvas.pack()
        self.mouse = (W // 2, H // 2)
        self.state = "title"
        self.best = 0

        c = self.canvas
        c.bind("<Motion>", lambda e: setattr(self, "mouse", (e.x, e.y)))
        c.bind("<Button-1>", self.shoot)
        c.bind("<Button-3>", lambda e: self.reload())
        root.bind("<Key>", self.on_key)

        self.build_scenery()
        self.reset()
        self.loop()

    # ---------- setup ----------
    def reset(self):
        self.targets = []
        self.effects = []  # (kind, x, y, until)
        self.score = 0
        self.lives = 3
        self.level = 1
        self.outlaws_down = 0
        self.ammo = 6
        self.reload_until = 0
        self.hurt_until = 0
        self.next_spawn = time.time() + 1.0
        self.paused_at = None
        self.message = ("", 0)

    def build_scenery(self):
        """Static background is drawn once with tag 'bg'."""
        c = self.canvas
        for i in range(GROUND):
            c.create_line(0, i, W, i, fill=hex_color(lerp(SKY_TOP, SKY_BOTTOM, i / GROUND)), tags="bg")
        c.create_oval(640, 40, 740, 140, fill="#fff1b8", outline="", tags="bg")
        # far mesas
        c.create_polygon(0, 300, 80, 240, 200, 240, 260, 300, fill="#c4734a", outline="", tags="bg")
        c.create_polygon(560, 300, 620, 220, 780, 220, 860, 300, fill="#b8673f", outline="", tags="bg")
        # ground
        c.create_rectangle(0, GROUND, W, H, fill="#c99a62", outline="", tags="bg")
        for _ in range(60):
            x, y = random.randint(0, W), random.randint(GROUND + 5, H)
            c.create_line(x, y, x + random.randint(4, 14), y, fill="#b3854f", tags="bg")

        # buildings: (x0, y0, x1, color, sign)
        buildings = [
            (70, 140, 290, "#8a5634", "SALOON"),
            (360, 100, 580, "#7a4a2c", "BANK"),
            (660, 160, 880, "#94613d", "HOTEL"),
        ]
        for x0, y0, x1, color, sign in buildings:
            c.create_rectangle(x0, y0, x1, GROUND, fill=color, outline=SHADOW, width=2, tags="bg")
            for yy in range(y0 + 12, GROUND, 14):
                c.create_line(x0, yy, x1, yy, fill=SHADOW, stipple="gray25", tags="bg")
            c.create_rectangle(x0 + 30, y0 - 30, x1 - 30, y0 + 5, fill="#5c3820", outline=SHADOW, tags="bg")
            c.create_text((x0 + x1) / 2, y0 - 12, text=sign, fill="#f3d9a4",
                          font=("Georgia", 16, "bold"), tags="bg")
            # porch roof
            c.create_rectangle(x0 - 10, 300, x1 + 10, 312, fill="#4d2e18", outline="", tags="bg")
            for px in (x0, x1):
                c.create_rectangle(px - 3, 312, px + 3, GROUND, fill="#4d2e18", outline="", tags="bg")

        # dark openings behind spots so people appear "inside"
        for x, y, cover in SPOTS:
            if cover == "window":
                c.create_rectangle(x - 32, y - 85, x + 32, y, fill="#2b1a0e", outline="#e8cf9a", width=3, tags="bg")
            elif cover == "door":
                c.create_rectangle(x - 34, y - 110, x + 34, y + 75, fill="#2b1a0e", outline="#e8cf9a", width=3, tags="bg")

    # ---------- spawning ----------
    def spawn(self, now):
        used = {(t.x, t.y) for t in self.targets}
        free = [s for s in SPOTS if (s[0], s[1]) not in used]
        if not free:
            return
        kind = "civilian" if random.random() < 0.22 else "outlaw"
        self.targets.append(Target(random.choice(free), kind, now, self.level))
        gap = max(0.35, 1.5 - (self.level - 1) * 0.12)
        self.next_spawn = now + random.uniform(gap * 0.6, gap * 1.3)
        # sometimes two at once on higher levels
        if self.level >= 3 and random.random() < 0.25:
            self.next_spawn = now + 0.1

    # ---------- input ----------
    def on_key(self, e):
        k = e.keysym.lower()
        if k == "escape":
            self.root.destroy()
        elif k == "return" and self.state in ("title", "over"):
            self.reset()
            self.state = "play"
        elif k == "p" and self.state in ("play", "paused"):
            self.toggle_pause()
        elif k == "r":
            self.reload()

    def toggle_pause(self):
        now = time.time()
        if self.state == "play":
            self.state, self.paused_at = "paused", now
        else:
            # shift every timer forward by the paused duration
            d = now - self.paused_at
            self.next_spawn += d
            self.reload_until += d
            for t in self.targets:
                t.born += d
                if t.kind == "outlaw":
                    t.draw_at += d
                    t.fire_at += d
                else:
                    t.leave_at += d
                if t.dead_at:
                    t.dead_at += d
            self.state = "play"

    def reload(self):
        if self.state == "play" and self.ammo < 6 and time.time() >= self.reload_until:
            self.reload_until = time.time() + 0.9

    def shoot(self, e):
        if self.state in ("title", "over"):
            self.reset()
            self.state = "play"
            return
        if self.state != "play":
            return
        now = time.time()
        if now < self.reload_until:
            return
        if self.ammo == 0:
            self.flash("Click! Reload (right-click)", now)
            return
        self.ammo -= 1
        self.effects.append(("shot", e.x, e.y, now + 0.25))
        # front-most targets first (barrels are lower on screen)
        for t in sorted(self.targets, key=lambda t: -t.y):
            if t.dead_at is None and t.hit(e.x, e.y):
                t.dead_at = now
                if t.kind == "outlaw":
                    quick = now < t.draw_at
                    pts = 150 if quick else 100
                    pts *= self.level
                    self.score += pts
                    self.outlaws_down += 1
                    self.effects.append(("text", t.x, t.y - 110, now + 0.8, f"+{pts}" + (" QUICK!" if quick else "")))
                    if self.outlaws_down % 10 == 0:
                        self.level += 1
                        self.flash(f"LEVEL {self.level}", now)
                else:
                    self.lose_life(now, "You shot a townsperson!")
                break
        if self.ammo == 0:
            self.reload_until = now + 0.9 + 0.3  # auto-reload after empty

    # ---------- game logic ----------
    def flash(self, text, now):
        self.message = (text, now + 1.4)

    def lose_life(self, now, text):
        self.lives -= 1
        self.hurt_until = now + 0.35
        self.flash(text, now)
        if self.lives <= 0:
            self.state = "over"
            self.best = max(self.best, self.score)

    def update(self, now):
        if self.reload_until and now >= self.reload_until:
            self.ammo = 6
            self.reload_until = 0
        if now >= self.next_spawn:
            self.spawn(now)

        alive = []
        for t in self.targets:
            if t.dead_at is not None:
                if now - t.dead_at < 0.5:
                    alive.append(t)
                continue
            if t.kind == "outlaw" and now >= t.fire_at:
                self.effects.append(("muzzle", t.x + 26, t.y - 55, now + 0.15))
                self.lose_life(now, "You got shot!")
                if self.state == "over":
                    return
                continue
            if t.kind == "civilian" and now >= t.leave_at:
                continue
            alive.append(t)
        self.targets = alive
        self.effects = [fx for fx in self.effects if fx[3] > now]

    # ---------- drawing ----------
    def draw_person(self, t, now):
        c = self.canvas
        x, y = t.x, t.y
        dead = t.dead_at is not None
        sink = 0
        if dead:
            sink = min(1.0, (now - t.dead_at) / 0.4) * 90
        else:
            rise = min(1.0, (now - t.born) / 0.15)
            sink = (1 - rise) * 90
        y += sink

        if t.kind == "outlaw":
            hat, shirt, face = "#1c1410", "#5a2a20", "#d9a77a"
        else:
            hat, shirt, face = "#efe2c2", "#3f6fa8", "#e8bb92"

        # body
        c.create_rectangle(x - 18, y - 55, x + 18, y, fill=shirt, outline=SHADOW, width=2, tags="fg")
        # head
        c.create_oval(x - 14, y - 82, x + 14, y - 54, fill=face, outline=SHADOW, width=2, tags="fg")
        # hat
        c.create_rectangle(x - 24, y - 80, x + 24, y - 75, fill=hat, outline=SHADOW, tags="fg")
        c.create_rectangle(x - 13, y - 96, x + 13, y - 78, fill=hat, outline=SHADOW, tags="fg")
        if dead:
            c.create_line(x - 8, y - 72, x - 3, y - 66, fill=SHADOW, width=2, tags="fg")
            c.create_line(x - 3, y - 72, x - 8, y - 66, fill=SHADOW, width=2, tags="fg")
            c.create_line(x + 3, y - 72, x + 8, y - 66, fill=SHADOW, width=2, tags="fg")
            c.create_line(x + 8, y - 72, x + 3, y - 66, fill=SHADOW, width=2, tags="fg")
        else:
            c.create_oval(x - 7, y - 72, x - 3, y - 68, fill=SHADOW, outline="", tags="fg")
            c.create_oval(x + 3, y - 72, x + 7, y - 68, fill=SHADOW, outline="", tags="fg")

        if t.kind == "outlaw":
            # bandana over the lower face
            c.create_polygon(x - 14, y - 66, x + 14, y - 66, x, y - 54, fill="#b8322a", outline=SHADOW, tags="fg")
            if t.drawn(now) and not dead:
                # arm and gun raised
                c.create_line(x + 18, y - 45, x + 30, y - 55, fill=shirt, width=7, tags="fg")
                c.create_rectangle(x + 26, y - 62, x + 44, y - 54, fill="#555", outline=SHADOW, tags="fg")
                # warning that grows as the shot approaches
                urgency = (now - t.draw_at) / max(0.01, t.fire_at - t.draw_at)
                blink = int(now * 12) % 2 == 0 or urgency > 0.6
                if blink:
                    c.create_text(x, y - 118, text="!", fill="#ff3b2f",
                                  font=("Georgia", 26, "bold"), tags="fg")
        else:
            # civilian waves
            c.create_line(x - 18, y - 45, x - 30, y - 70, fill=shirt, width=7, tags="fg")

        # cover in front of the person
        if t.cover == "window":
            c.create_rectangle(t.x - 36, t.y, t.x + 36, t.y + 95, fill="#8a5634", outline="", tags="fg")
            c.create_rectangle(t.x - 36, t.y - 4, t.x + 36, t.y + 6, fill="#e8cf9a", outline="", tags="fg")
        elif t.cover == "door":
            c.create_rectangle(t.x - 36, t.y, t.x + 36, t.y + 95, fill="#2b1a0e", outline="", tags="fg")
            c.create_rectangle(t.x - 36, t.y, t.x + 36, t.y + 40, fill="#6b4024", outline=SHADOW, tags="fg")
        elif t.cover == "barrel":
            pass
        if t.cover == "barrel":
            bx, by = t.x, t.y
            c.create_rectangle(bx - 40, by - 30, bx + 40, by + 70, fill="#7a4a24", outline=SHADOW, width=2, tags="fg")
            for yy in (by - 20, by + 20, by + 55):
                c.create_line(bx - 40, yy, bx + 40, yy, fill="#3a2614", width=4, tags="fg")
            c.create_rectangle(bx - 40, by + 70, bx + 40, H, fill="#c99a62", outline="", tags="fg")

    def draw_static_barrels(self):
        c = self.canvas
        used = {(t.x, t.y) for t in self.targets}
        for x, y, cover in SPOTS:
            if cover == "barrel" and (x, y) not in used:
                c.create_rectangle(x - 40, y - 30, x + 40, y + 70, fill="#7a4a24", outline=SHADOW, width=2, tags="fg")
                for yy in (y - 20, y + 20, y + 55):
                    c.create_line(x - 40, yy, x + 40, yy, fill="#3a2614", width=4, tags="fg")

    def hud_text(self, x, y, text, size=16, anchor="nw", color=TEXT):
        c = self.canvas
        f = ("Georgia", size, "bold")
        c.create_text(x + 2, y + 2, text=text, fill=SHADOW, font=f, anchor=anchor, tags="fg")
        c.create_text(x, y, text=text, fill=color, font=f, anchor=anchor, tags="fg")

    def render(self, now):
        c = self.canvas
        c.delete("fg")

        if self.state != "title":
            for t in sorted(self.targets, key=lambda t: t.y):
                self.draw_person(t, now)
        self.draw_static_barrels()

        for fx in self.effects:
            kind, x, y = fx[0], fx[1], fx[2]
            if kind == "shot":
                c.create_oval(x - 6, y - 6, x + 6, y + 6, fill="#1a0f08", outline="#ffe08a", width=2, tags="fg")
            elif kind == "muzzle":
                c.create_oval(x - 14, y - 14, x + 14, y + 14, fill="#ffd34a", outline="#ff7a1a", width=3, tags="fg")
            elif kind == "text":
                rise = (fx[3] - now) * 30
                self.hud_text(x, y - (24 - rise), fx[4], 14, "center", "#ffe08a")

        if now < self.hurt_until:
            c.create_rectangle(0, 0, W, H, fill="#c0201a", stipple="gray50", outline="", tags="fg")

        # HUD
        if self.state != "title":
            self.hud_text(16, 12, f"SCORE  {self.score}")
            self.hud_text(16, 40, f"LEVEL  {self.level}", 13)
            self.hud_text(W - 16, 12, "LIVES  " + "♥" * self.lives, 16, "ne", "#ff6b5a")
            # revolver cylinder
            for i in range(6):
                bx = W - 30 - i * 22
                full = i < self.ammo and not self.reload_until
                c.create_oval(bx - 7, H - 34, bx + 7, H - 20,
                              fill="#d9b35a" if full else "#3a2a1a", outline=SHADOW, width=2, tags="fg")
            if self.reload_until:
                self.hud_text(W - 16, H - 62, "RELOADING...", 12, "ne")
            text, until = self.message
            if now < until:
                self.hud_text(W / 2, 70, text, 22, "center", "#ffe08a")

        if self.state == "title":
            c.create_rectangle(0, 0, W, H, fill="#000", stipple="gray50", outline="", tags="fg")
            self.hud_text(W / 2, 170, "DUSTY DRAW", 54, "center", "#ffd27a")
            self.hud_text(W / 2, 250, "Shoot the masked outlaws before they draw on you.", 16, "center")
            self.hud_text(W / 2, 280, "Leave the townsfolk alone. Shoot before the  !  for bonus points.", 13, "center")
            self.hud_text(W / 2, 320, "Left click: shoot   Right click / R: reload   P: pause", 13, "center")
            self.hud_text(W / 2, 390, "Click or press Enter to start", 20, "center", "#ffe08a")
        elif self.state == "paused":
            c.create_rectangle(0, 0, W, H, fill="#000", stipple="gray50", outline="", tags="fg")
            self.hud_text(W / 2, H / 2, "PAUSED", 40, "center")
        elif self.state == "over":
            c.create_rectangle(0, 0, W, H, fill="#000", stipple="gray50", outline="", tags="fg")
            self.hud_text(W / 2, 200, "GAME OVER", 50, "center", "#ff6b5a")
            self.hud_text(W / 2, 270, f"Score: {self.score}     Best: {self.best}", 20, "center")
            self.hud_text(W / 2, 330, "Click or press Enter to ride again", 18, "center", "#ffe08a")

        # crosshair
        mx, my = self.mouse
        col = "#ff3b2f" if self.state == "play" else TEXT
        c.create_oval(mx - 16, my - 16, mx + 16, my + 16, outline=col, width=2, tags="fg")
        for dx, dy in ((-24, 0), (24, 0), (0, -24), (0, 24)):
            c.create_line(mx + dx * 0.4, my + dy * 0.4, mx + dx, my + dy, fill=col, width=2, tags="fg")

    def loop(self):
        now = time.time()
        if self.state == "play":
            self.update(now)
        self.render(now)
        self.root.after(16, self.loop)


def main():
    root = tk.Tk()
    Game(root)
    root.mainloop()


if __name__ == "__main__":
    main()

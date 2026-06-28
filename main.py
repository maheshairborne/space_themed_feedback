import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk, ImageFilter, ImageDraw
import os, random, collections
import pandas as pd

# ---------------- SETTINGS ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Put your image files next to this script or change names/paths here:
BG_IMAGE = os.path.join(BASE_DIR, "space background.jpg")
ASTEROID_IMAGE = os.path.join(BASE_DIR, "asteroid_bg.png")

# Data files (Excel preferred; CSV fallback if openpyxl isn't installed)
FEEDBACK_XLSX = os.path.join(BASE_DIR, "feedbacks.xlsx")
FEEDBACK_CSV  = os.path.join(BASE_DIR, "feedbacks.csv")

ASTEROID_BASE_SIZE = 180   # bigger asteroids
TRAIL_LENGTH = 80
TRAIL_BASE_SIZE = 14
TRAIL_MAX_ALPHA = 140
UPDATE_MS = 28
MAX_ASTEROIDS = 20
ROTATE_EVERY_N_FRAMES = 5
TRAIL_START_OFFSET = 6
TEXT_FONT = ("Inter", 18, "bold")  # larger label on asteroid
TEXT_OUTLINE_STRENGTH = 2
RESPAWN_DELAY_MS = 1500  # asteroid returns after 1.5 sec

# ---------------- HELPERS ----------------
def has_openpyxl():
    try:
        import openpyxl  # noqa
        return True
    except Exception:
        return False

# ---------------- GUI SETUP ----------------
root = tk.Tk()
root.title("Asteroid Feedback Launcher")
# Use 'zoomed' on Windows; if fullscreen is preferred, replace next line with: root.attributes("-fullscreen", True)
root.state("zoomed")

root.configure(bg="black")

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

canvas = Canvas(root, width=screen_width, height=screen_height, highlightthickness=0, bg="black")
canvas.pack(fill="both", expand=True)

# Background (safe load)
bg_img = None
try:
    if os.path.exists(BG_IMAGE):
        bg_img_raw = Image.open(BG_IMAGE).convert("RGBA").resize((screen_width, screen_height))
        bg_img = ImageTk.PhotoImage(bg_img_raw)
        canvas.create_image(0, 0, anchor="nw", image=bg_img)
    else:
        # No file? Just draw black.
        canvas.create_rectangle(0, 0, screen_width, screen_height, fill="black", outline="")
except Exception:
    canvas.create_rectangle(0, 0, screen_width, screen_height, fill="black", outline="")

# Asteroid base (safe load; create a placeholder if missing)
try:
    if os.path.exists(ASTEROID_IMAGE):
        asteroid_raw_orig = Image.open(ASTEROID_IMAGE).convert("RGBA").resize((ASTEROID_BASE_SIZE, ASTEROID_BASE_SIZE))
    else:
        # Fallback: draw a gray rock
        asteroid_raw_orig = Image.new("RGBA", (ASTEROID_BASE_SIZE, ASTEROID_BASE_SIZE), (0, 0, 0, 0))
        d = ImageDraw.Draw(asteroid_raw_orig)
        d.ellipse((0, 0, ASTEROID_BASE_SIZE, ASTEROID_BASE_SIZE), fill=(100, 100, 110, 255))
except Exception:
    asteroid_raw_orig = Image.new("RGBA", (ASTEROID_BASE_SIZE, ASTEROID_BASE_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(asteroid_raw_orig)
    d.ellipse((0, 0, ASTEROID_BASE_SIZE, ASTEROID_BASE_SIZE), fill=(100, 100, 110, 255))

asteroid_base_photo = ImageTk.PhotoImage(asteroid_raw_orig)
GLOBAL_IMAGE_CACHE = {"asteroid_base": asteroid_base_photo}

# Entry + Button
entry_bg_color = "#121216"
feedback_entry = tk.Entry(
    root, font=TEXT_FONT, width=50, bg=entry_bg_color, fg="white",
    insertbackground="white", bd=0, highlightthickness=0
)
feedback_entry.place(relx=0.5, rely=0.92, anchor="center")

def launch_feedback():  # will be defined later, after class
    pass

launch_button = tk.Button(
    root, text="🚀 Launch Feedback", font=("Inter", 18, "bold"),
    bg="#ff6a00", fg="white", activebackground="#ff8a2b",
    padx=14, pady=8, bd=0, command=lambda: launch_feedback()
)
launch_button.place(relx=0.5, rely=0.97, anchor="center")

# ---------------- TRAIL IMAGE GENERATION ----------------
GRADIENT_COLORS = [
    (255, 255, 255),
    (230, 230, 230),
    (200, 200, 200),
    (150, 150, 150),
    (100, 100, 100),
    (50, 50, 50)
]

def lerp(a, b, t): return int(a + (b - a) * t)

def color_lerp(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))

def generate_trail_images(length=TRAIL_LENGTH, base_size=TRAIL_BASE_SIZE):
    imgs = []
    for i in range(length):
        t = i / max(length - 1, 1)
        segs = len(GRADIENT_COLORS) - 1
        seg_pos = t * segs
        idx = int(seg_pos)
        local_t = seg_pos - idx
        c1 = GRADIENT_COLORS[min(idx, segs - 1)]
        c2 = GRADIENT_COLORS[min(idx + 1, segs)]
        color = color_lerp(c1, c2, local_t)
        alpha = int(TRAIL_MAX_ALPHA * (1 - t)) + 6
        size = max(2, int(base_size * (1 - 0.6 * t)))

        glow_size = size * 4
        im = Image.new("RGBA", (glow_size, glow_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(im)
        cx, cy = glow_size // 2, glow_size // 2
        draw.ellipse(
            (cx - size//2, cy - size//2, cx + size//2, cy + size//2),
            fill=(color[0], color[1], color[2], alpha)
        )
        im = im.filter(ImageFilter.GaussianBlur(radius=max(1, size // 1)))
        imgs.append(ImageTk.PhotoImage(im))
    return imgs

TRAIL_IMAGES = generate_trail_images()

# ---------------- DATA (LOAD/SAVE) ----------------
def save_feedback(text: str):
    """Save to Excel if openpyxl is available, else CSV; always append."""
    text = (text or "").strip()
    if not text:
        return

    df_new = pd.DataFrame([[text]], columns=["Feedback"])

    if has_openpyxl():
        # Excel path
        if os.path.exists(FEEDBACK_XLSX):
            try:
                df_existing = pd.read_excel(FEEDBACK_XLSX)
            except Exception:
                df_existing = pd.DataFrame(columns=["Feedback"])
            df_all = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_all = df_new
        try:
            df_all.to_excel(FEEDBACK_XLSX, index=False)
        except Exception:
            # If Excel write fails, fall back to CSV
            _append_to_csv(df_new)
    else:
        _append_to_csv(df_new)

def _append_to_csv(df_new: pd.DataFrame):
    if os.path.exists(FEEDBACK_CSV):
        try:
            df_existing = pd.read_csv(FEEDBACK_CSV)
        except Exception:
            df_existing = pd.DataFrame(columns=["Feedback"])
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_csv(FEEDBACK_CSV, index=False, encoding="utf-8")

def load_existing_feedbacks():
    """Load from Excel first if available, else CSV; return list of strings."""
    if has_openpyxl() and os.path.exists(FEEDBACK_XLSX):
        try:
            df = pd.read_excel(FEEDBACK_XLSX)
            return [str(x) for x in df["Feedback"].dropna().tolist()]
        except Exception:
            pass
    if os.path.exists(FEEDBACK_CSV):
        try:
            df = pd.read_csv(FEEDBACK_CSV)
            return [str(x) for x in df["Feedback"].dropna().tolist()]
        except Exception:
            pass
    return []

# ---------------- ASTEROID CLASS ----------------
class Asteroid:
    def __init__(self, feedback_text):
        self.feedback_text = feedback_text
        self.spawn()
        self.speed_mult = random.uniform(0.95, 1.35)
        self._rot_angle = random.uniform(0, 360)
        self._spin = random.uniform(-3.0, 3.0)  # faster spin
        self._rot_cache = None
        self._rot_frame_counter = random.randint(0, ROTATE_EVERY_N_FRAMES - 1)

        self.photo = GLOBAL_IMAGE_CACHE["asteroid_base"]
        self.canvas_id = canvas.create_image(self.x, self.y, image=self.photo)

        # Text with outline (shadows)
        self.text_shadow_ids = []
        for dx in range(-TEXT_OUTLINE_STRENGTH, TEXT_OUTLINE_STRENGTH + 1):
            for dy in range(-TEXT_OUTLINE_STRENGTH, TEXT_OUTLINE_STRENGTH + 1):
                if dx == 0 and dy == 0:
                    continue
                sid = canvas.create_text(
                    self.x + dx, self.y + dy,
                    text=self.feedback_text, font=TEXT_FONT, fill="#000000", anchor="center"
                )
                self.text_shadow_ids.append(sid)

        self.text_id = canvas.create_text(
            self.x, self.y, text=self.feedback_text,
            font=TEXT_FONT, fill="white", anchor="center"
        )

        self.trail = collections.deque()
        self.trail_img_refs = collections.deque()

    def spawn(self):
        pad = 160
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left":
            self.x = -pad
            self.y = random.uniform(0, screen_height)
            self.dx = random.uniform(2.2, 5.0)
            self.dy = random.uniform(-1.6, 1.6)
        elif side == "right":
            self.x = screen_width + pad
            self.y = random.uniform(0, screen_height)
            self.dx = random.uniform(-5.0, -2.2)
            self.dy = random.uniform(-1.6, 1.6)
        elif side == "top":
            self.x = random.uniform(0, screen_width)
            self.y = -pad
            self.dx = random.uniform(-1.6, 1.6)
            self.dy = random.uniform(2.2, 5.0)
        else:
            self.x = random.uniform(0, screen_width)
            self.y = screen_height + pad
            self.dx = random.uniform(-1.6, 1.6)
            self.dy = random.uniform(-5.0, -2.2)

    def step(self):
        self.x += self.dx * self.speed_mult
        self.y += self.dy * self.speed_mult

        # Spin the asteroid sprite
        self._rot_frame_counter += 1
        if self._rot_frame_counter >= ROTATE_EVERY_N_FRAMES:
            self._rot_frame_counter = 0
            self._rot_angle = (self._rot_angle + self._spin) % 360
            rotated = asteroid_raw_orig.rotate(self._rot_angle, resample=Image.BICUBIC, expand=True)
            self._rot_cache = ImageTk.PhotoImage(rotated)
            self.photo = self._rot_cache
            canvas.itemconfig(self.canvas_id, image=self.photo)

        # Move sprite + text
        canvas.coords(self.canvas_id, self.x, self.y)
        for sid in self.text_shadow_ids:
            canvas.coords(sid, self.x, self.y)
        canvas.coords(self.text_id, self.x, self.y)
        canvas.tag_raise(self.text_id)

        # Trail
        vx, vy = self.dx * self.speed_mult, self.dy * self.speed_mult
        trail_x = self.x - vx * TRAIL_START_OFFSET
        trail_y = self.y - vy * TRAIL_START_OFFSET
        head_img = TRAIL_IMAGES[0]
        t_id = canvas.create_image(trail_x, trail_y, image=head_img)
        canvas.tag_lower(t_id, self.canvas_id)
        self.trail.append(t_id)
        self.trail_img_refs.append(head_img)

        # Fade trail segments
        for idx, t_obj in enumerate(list(self.trail)):
            tpos = len(self.trail) - 1 - idx
            img = TRAIL_IMAGES[tpos] if tpos < len(TRAIL_IMAGES) else TRAIL_IMAGES[-1]
            canvas.itemconfig(t_obj, image=img)
            try:
                self.trail_img_refs[idx] = img
            except IndexError:
                pass

        # Trim trail
        while len(self.trail) > TRAIL_LENGTH:
            old = self.trail.popleft()
            canvas.delete(old)
            self.trail_img_refs.popleft()

    def is_offscreen(self, margin=240):
        return (self.x < -margin or self.x > screen_width + margin or
                self.y < -margin or self.y > screen_height + margin)

    def respawn_later(self):
        # Properly respawn: reset trail, reposition canvas items immediately
        def do_respawn():
            # clear old trail items
            while self.trail:
                canvas.delete(self.trail.popleft())
            self.trail_img_refs.clear()

            self.spawn()
            canvas.coords(self.canvas_id, self.x, self.y)
            for sid in self.text_shadow_ids:
                canvas.coords(sid, self.x, self.y)
            canvas.coords(self.text_id, self.x, self.y)
            canvas.tag_raise(self.text_id)
        root.after(RESPAWN_DELAY_MS, do_respawn)

# ---------------- MANAGEMENT ----------------
asteroids = []

def create_asteroid(feedback_text):
    if len(asteroids) < MAX_ASTEROIDS:
        asteroids.append(Asteroid(feedback_text))

def flash():
    rid = canvas.create_rectangle(0, 0, screen_width, screen_height, fill="white", outline="")
    root.after(60, lambda: canvas.delete(rid))

def launch_feedback():
    feedback_text = feedback_entry.get().strip()
    if not feedback_text:
        return
    feedback_entry.delete(0, tk.END)

    flash()
    save_feedback(feedback_text)   # robust save (xlsx or csv)
    create_asteroid(feedback_text)

root.bind("<Return>", lambda e: launch_feedback())

def move_loop():
    for a in asteroids:
        a.step()
        if a.is_offscreen():
            a.respawn_later()
    root.after(UPDATE_MS, move_loop)

# Load old feedbacks on start and spawn them
for fb in load_existing_feedbacks():
    if fb:
        create_asteroid(fb)

move_loop()
root.mainloop()
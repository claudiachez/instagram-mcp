"""Generate docs/demo.gif — a stylized Claude conversation animation."""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 820, 460
BG = (24, 24, 27)              # zinc-900
PANEL = (31, 31, 35)
FG = (228, 228, 231)           # zinc-200
USER_BG = (37, 99, 235)        # blue-600
TOOL_BG = (16, 185, 129)       # emerald-500
CLAUDE_BG = (39, 39, 42)       # zinc-800
MUTED = (161, 161, 170)        # zinc-400
ACCENT = (244, 114, 182)       # pink-400 (Instagram-ish)

FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
font_body = ImageFont.truetype(FONT_MONO, 15)
font_small = ImageFont.truetype(FONT_MONO, 12)
font_title = ImageFont.truetype(FONT_MONO, 16)
font_label = ImageFont.truetype(FONT_MONO, 11)

PROMPT = "What did I post on Instagram this week?"
TOOL = "instagram · list_my_media"
RESPONSE = [
    "Your last 3 posts:",
    "",
    "1. PR Manager hiring (Feb 21)    142 reach",
    "2. Hajj Mubarak greeting (May 9)  89 reach",
    "3. Team offsite recap (Apr 15)    67 reach",
    "",
    "Top performer: the hiring post —",
    "likely boosted by the keywords.",
]


def text_w(s: str, font) -> int:
    return font.getbbox(s)[2]


def frame(prompt_chars: int, show_tool: bool, resp_chars: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)

    # Title bar
    d.rectangle([(0, 0), (WIDTH, 44)], fill=PANEL)
    d.ellipse([(18, 16), (30, 28)], fill=ACCENT)
    d.text((40, 14), "Claude  ·  instagram-mcp", font=font_title, fill=FG)
    d.text((WIDTH - 110, 18), "v0.1.1", font=font_label, fill=MUTED)

    y = 72

    # User bubble (right aligned, with typing cursor)
    shown_prompt = PROMPT[:prompt_chars]
    pw = text_w(shown_prompt, font_body)
    bubble_w = pw + 36
    bubble_x = WIDTH - bubble_w - 24
    d.rounded_rectangle(
        [(bubble_x, y), (WIDTH - 24, y + 38)], radius=19, fill=USER_BG
    )
    d.text((bubble_x + 18, y + 10), shown_prompt, font=font_body, fill=(255, 255, 255))
    if prompt_chars < len(PROMPT):
        cx = bubble_x + 18 + pw
        d.rectangle([(cx + 2, y + 12), (cx + 9, y + 28)], fill=(255, 255, 255))

    y += 62

    # Tool call pill (left)
    if show_tool:
        label = f"> {TOOL}"
        lw = text_w(label, font_small) + 22
        d.rounded_rectangle(
            [(24, y), (24 + lw, y + 26)], radius=13, fill=TOOL_BG
        )
        d.text((35, y + 7), label, font=font_small, fill=(255, 255, 255))
        y += 42

    # Claude response bubble (left)
    if resp_chars > 0:
        bubble_h = HEIGHT - y - 24
        d.rounded_rectangle(
            [(24, y), (WIDTH - 140, y + bubble_h)], radius=12, fill=CLAUDE_BG
        )
        remaining = resp_chars
        ty = y + 16
        for line in RESPONSE:
            if remaining <= 0:
                break
            shown = line[: remaining]
            color = FG
            if line.startswith(("1.", "2.", "3.")):
                color = FG
            d.text((42, ty), shown, font=font_body, fill=color)
            remaining -= len(line) + 1  # newline counts
            ty += 24

    return img


def main() -> None:
    frames: list[Image.Image] = []

    # 1. Type the prompt (2 chars per frame)
    for i in range(0, len(PROMPT) + 1, 2):
        frames.append(frame(i, False, 0))

    # 2. Hold completed prompt
    for _ in range(6):
        frames.append(frame(len(PROMPT), False, 0))

    # 3. Tool call appears + held
    for _ in range(8):
        frames.append(frame(len(PROMPT), True, 0))

    # 4. Type the response (4 chars per frame)
    total = sum(len(line) + 1 for line in RESPONSE)
    for i in range(0, total + 1, 4):
        frames.append(frame(len(PROMPT), True, i))

    # 5. Hold the finished response (long pause so the loop is readable)
    for _ in range(28):
        frames.append(frame(len(PROMPT), True, total))

    out = os.path.join(os.path.dirname(__file__), "demo.gif")
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=85,
        loop=0,
        optimize=True,
    )
    size_kb = os.path.getsize(out) // 1024
    print(f"wrote {out} ({len(frames)} frames, {size_kb} KB)")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from .models import AssetPlan, TemplateMap


WIDTH = 1080
HEIGHT = 1920


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _background_frame(plan: AssetPlan) -> Image.Image:
    width = WIDTH
    height = HEIGHT
    top = (24, 34, 52)
    bottom = (81, 101, 133)
    img = Image.new("RGB", (width, height), color=top)
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        color = tuple(int(top[idx] * (1 - ratio) + bottom[idx] * ratio) for idx in range(3))
        draw.line([(0, y), (width, y)], fill=color)

    for idx in range(64):
        x = int((idx * 37 + 19) % width)
        y = int((idx * 97 + 43) % height)
        length = 150 + (idx % 5) * 25
        draw.line([(x, y), (x - 28, y + length)], fill=(210, 223, 236), width=3)
        draw.line([(x + 1, y), (x - 27, y + length)], fill=(176, 195, 214), width=1)

    circle_radius = 280
    draw.ellipse(
        [
            (width // 2 - circle_radius, height // 2 - circle_radius - 120),
            (width // 2 + circle_radius, height // 2 + circle_radius - 120),
        ],
        outline=(230, 238, 244),
        width=5,
    )
    return img


def _draw_text_block(draw: ImageDraw.ImageDraw, plan: AssetPlan) -> None:
    title_font = _load_font(84)
    subtitle_font = _load_font(54)
    small_font = _load_font(30)
    title_lines = wrap(plan.hook.text, width=21)
    subtitle_lines = wrap(plan.subtitle.text, width=28)

    x_margin = 104
    y = 220
    draw.rounded_rectangle(
        [(72, 160), (WIDTH - 72, HEIGHT - 200)],
        radius=44,
        fill=(8, 13, 24, 132),
        outline=(225, 235, 241),
        width=3,
    )
    draw.text((x_margin, y), "SEREVONA", font=small_font, fill=(228, 235, 240))
    y += 90
    for line in title_lines:
        draw.text((x_margin, y), line, font=title_font, fill=(247, 249, 250))
        y += 102
    y += 80
    for line in subtitle_lines:
        draw.text((x_margin, y), line, font=subtitle_font, fill=(222, 231, 236))
        y += 70
    draw.text(
        (x_margin, HEIGHT - 320),
        f"{plan.platform.upper()}  |  {plan.asset_id}",
        font=small_font,
        fill=(187, 201, 212),
    )


def render_mock_asset(plan: AssetPlan, template_map: TemplateMap, outputs_dir: Path, force: bool) -> tuple[Path, Path]:
    manifest_path = outputs_dir / f"{plan.asset_id}.render.json"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    export_path = outputs_dir / f"{plan.asset_id}.mp4"
    thumbnail_path = outputs_dir / f"{plan.asset_id}.jpg"
    if export_path.exists() and thumbnail_path.exists() and manifest_path.exists() and not force:
        return export_path, thumbnail_path

    frame = _background_frame(plan)
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    _draw_text_block(overlay_draw, plan)
    composited = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")

    # Mock mode writes a deterministic placeholder asset so the full pipeline is testable
    # without relying on local video encoders or undocumented Canva behavior.
    export_path.write_bytes(
        "\n".join(
            [
                "SEREVONA MOCK VIDEO PLACEHOLDER",
                f"asset_id={plan.asset_id}",
                f"platform={plan.platform}",
                f"image={plan.image_id}",
                f"hook={plan.hook.text}",
                f"subtitle={plan.subtitle.text}",
            ]
        ).encode("utf-8")
    )
    composited.save(thumbnail_path, quality=92)
    manifest_path.write_text(
        json.dumps(
            {
                "asset_id": plan.asset_id,
                "template_id": template_map.template_id,
                "template_fields": template_map.fields,
                "mode": "mock",
                "image_id": plan.image_id,
                "header_text": plan.hook.text,
                "subtitle_text": plan.subtitle.text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return export_path, thumbnail_path

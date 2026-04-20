from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "gui_prototype" / "assets"
PNG_PATH = ASSETS_DIR / "app_icon.png"
ICO_PATH = ASSETS_DIR / "app_icon.ico"

CANVAS_SIZE = 256
SUPERSAMPLE = 4
HI_SIZE = CANVAS_SIZE * SUPERSAMPLE


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def mix(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def rounded_rect_sdf(px: float, py: float, cx: float, cy: float, half_w: float, half_h: float, radius: float) -> float:
    dx = abs(px - cx) - (half_w - radius)
    dy = abs(py - cy) - (half_h - radius)
    ax = max(dx, 0.0)
    ay = max(dy, 0.0)
    outside = math.hypot(ax, ay)
    inside = min(max(dx, dy), 0.0)
    return outside + inside - radius


def circle_alpha(px: float, py: float, cx: float, cy: float, radius: float, feather: float) -> float:
    dist = math.hypot(px - cx, py - cy)
    return 1.0 - smoothstep(radius - feather, radius + feather, dist)


def ring_alpha(px: float, py: float, cx: float, cy: float, radius: float, thickness: float, feather: float) -> float:
    dist = math.hypot(px - cx, py - cy)
    delta = abs(dist - radius)
    return 1.0 - smoothstep(thickness / 2.0 - feather, thickness / 2.0 + feather, delta)


def segment_alpha(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    width: float,
    feather: float,
) -> float:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0.0 else clamp01((wx * vx + wy * vy) / denom)
    nx = ax + t * vx
    ny = ay + t * vy
    dist = math.hypot(px - nx, py - ny)
    return 1.0 - smoothstep(width / 2.0 - feather, width / 2.0 + feather, dist)


def composite(
    base: tuple[float, float, float],
    overlay: tuple[float, float, float],
    alpha: float,
) -> tuple[float, float, float]:
    return tuple(base[i] * (1.0 - alpha) + overlay[i] * alpha for i in range(3))


def render_high_res() -> list[tuple[int, int, int, int]]:
    pixels: list[tuple[int, int, int, int]] = []
    for y in range(HI_SIZE):
        py = y + 0.5
        for x in range(HI_SIZE):
            px = x + 0.5

            bg_top = (9 / 255.0, 25 / 255.0, 47 / 255.0)
            bg_bottom = (26 / 255.0, 56 / 255.0, 83 / 255.0)
            t = y / max(1, HI_SIZE - 1)
            color = mix(bg_top, bg_bottom, t)

            cx = HI_SIZE * 0.5
            cy = HI_SIZE * 0.5
            rounded = rounded_rect_sdf(px, py, cx, cy, HI_SIZE * 0.42, HI_SIZE * 0.42, HI_SIZE * 0.16)
            alpha = 1.0 - smoothstep(-SUPERSAMPLE * 1.5, SUPERSAMPLE * 1.5, rounded)
            outer_shadow = 1.0 - smoothstep(HI_SIZE * 0.40, HI_SIZE * 0.55, math.hypot(px - cx, py - cy))
            color = composite(color, (5 / 255.0, 13 / 255.0, 25 / 255.0), 0.22 * outer_shadow)

            ring = ring_alpha(px, py, HI_SIZE * 0.49, HI_SIZE * 0.49, HI_SIZE * 0.19, HI_SIZE * 0.09, SUPERSAMPLE * 1.5)
            color = composite(color, (238 / 255.0, 245 / 255.0, 250 / 255.0), 0.92 * ring)

            core = circle_alpha(px, py, HI_SIZE * 0.49, HI_SIZE * 0.49, HI_SIZE * 0.11, SUPERSAMPLE * 2.0)
            color = composite(color, (14 / 255.0, 34 / 255.0, 56 / 255.0), 0.95 * core)

            flow_color = (62 / 255.0, 212 / 255.0, 199 / 255.0)
            wave_a = segment_alpha(
                px,
                py,
                HI_SIZE * 0.23,
                HI_SIZE * 0.60,
                HI_SIZE * 0.42,
                HI_SIZE * 0.44,
                HI_SIZE * 0.08,
                SUPERSAMPLE * 2.0,
            )
            wave_b = segment_alpha(
                px,
                py,
                HI_SIZE * 0.42,
                HI_SIZE * 0.44,
                HI_SIZE * 0.58,
                HI_SIZE * 0.56,
                HI_SIZE * 0.08,
                SUPERSAMPLE * 2.0,
            )
            wave_c = segment_alpha(
                px,
                py,
                HI_SIZE * 0.58,
                HI_SIZE * 0.56,
                HI_SIZE * 0.77,
                HI_SIZE * 0.40,
                HI_SIZE * 0.08,
                SUPERSAMPLE * 2.0,
            )
            color = composite(color, flow_color, max(wave_a, wave_b, wave_c))

            sensor_orbit = ring_alpha(px, py, HI_SIZE * 0.65, HI_SIZE * 0.33, HI_SIZE * 0.06, HI_SIZE * 0.025, SUPERSAMPLE * 1.2)
            color = composite(color, flow_color, 0.95 * sensor_orbit)

            status_dot = circle_alpha(px, py, HI_SIZE * 0.72, HI_SIZE * 0.26, HI_SIZE * 0.028, SUPERSAMPLE * 1.4)
            color = composite(color, (255 / 255.0, 141 / 255.0, 97 / 255.0), 0.95 * status_dot)

            r = int(clamp01(color[0]) * 255)
            g = int(clamp01(color[1]) * 255)
            b = int(clamp01(color[2]) * 255)
            a = int(alpha * 255)
            pixels.append((r, g, b, a))
    return pixels


def downsample_rgba(high_pixels: list[tuple[int, int, int, int]]) -> bytes:
    rows = bytearray()
    for y in range(CANVAS_SIZE):
        rows.append(0)
        for x in range(CANVAS_SIZE):
            acc = [0, 0, 0, 0]
            for sy in range(SUPERSAMPLE):
                for sx in range(SUPERSAMPLE):
                    hx = x * SUPERSAMPLE + sx
                    hy = y * SUPERSAMPLE + sy
                    r, g, b, a = high_pixels[hy * HI_SIZE + hx]
                    acc[0] += r
                    acc[1] += g
                    acc[2] += b
                    acc[3] += a
            scale = SUPERSAMPLE * SUPERSAMPLE
            rows.extend(bytes(channel // scale for channel in acc))
    return bytes(rows)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def build_png_bytes() -> bytes:
    high_pixels = render_high_res()
    rgba_rows = downsample_rgba(high_pixels)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", CANVAS_SIZE, CANVAS_SIZE, 8, 6, 0, 0, 0)
    idat = zlib.compress(rgba_rows, level=9)
    return signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")


def build_ico_bytes(png_bytes: bytes) -> bytes:
    directory = struct.pack("<HHH", 0, 1, 1)
    image_offset = 6 + 16
    entry = struct.pack(
        "<BBBBHHII",
        0,
        0,
        0,
        0,
        1,
        32,
        len(png_bytes),
        image_offset,
    )
    return directory + entry + png_bytes


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    png_bytes = build_png_bytes()
    PNG_PATH.write_bytes(png_bytes)
    ICO_PATH.write_bytes(build_ico_bytes(png_bytes))
    print(f"wrote {PNG_PATH.relative_to(PROJECT_ROOT)}")
    print(f"wrote {ICO_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

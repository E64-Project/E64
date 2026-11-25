#!/usr/bin/env python3
"""Render actual SVG icons for geometry tests and reproducible visual reviews.
Requires installed librsvg, Cairo and Pillow; never accesses emulator/storage APIs.
"""
from pathlib import Path
import argparse
import ctypes as C
import io
from functools import lru_cache
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / 'src/webui/assets/icons'
CATEGORIES = [('folder', 'Directory / Folder'), ('floppy', 'Floppy Disk'),
              ('hard-drive', 'Hard Drive'), ('cartridge', 'Cartridge'),
              ('cassette', 'Tape'), ('program', 'Program'), ('snapshot', 'Snapshot'),
              ('rom', 'ROM'), ('file', 'Unknown / Generic File')]
# In SVG units: 0.4 units = 0.8 pixels at the unchanged 32px display size.
SAFETY_MARGIN = 0.4
TARGET_SPAN = 16 - 2 * SAFETY_MARGIN

@lru_cache(maxsize=1)
def libraries():
    rsvg = C.CDLL('librsvg-2.so.2')
    cairo = C.CDLL('libcairo.so.2')
    gobject = C.CDLL('libgobject-2.0.so.0')
    rsvg.rsvg_handle_new_from_data.argtypes = [C.c_char_p, C.c_size_t, C.c_void_p]
    rsvg.rsvg_handle_new_from_data.restype = C.c_void_p
    rsvg.rsvg_handle_render_cairo.argtypes = [C.c_void_p, C.c_void_p]
    rsvg.rsvg_handle_render_cairo.restype = C.c_int
    cairo.cairo_image_surface_create.argtypes = [C.c_int, C.c_int, C.c_int]
    cairo.cairo_image_surface_create.restype = C.c_void_p
    cairo.cairo_create.argtypes = [C.c_void_p]
    cairo.cairo_create.restype = C.c_void_p
    cairo.cairo_scale.argtypes = [C.c_void_p, C.c_double, C.c_double]
    cairo.cairo_destroy.argtypes = [C.c_void_p]
    cairo.cairo_destroy.restype = None
    cairo.cairo_surface_destroy.argtypes = [C.c_void_p]
    cairo.cairo_surface_destroy.restype = None
    gobject.g_object_unref.argtypes = [C.c_void_p]
    gobject.g_object_unref.restype = None
    return rsvg, cairo, gobject


def render_svg(svg, size):
    """Render vectors directly at the requested size, without bitmap resizing."""
    root = ET.fromstring(svg)
    width, height = [float(root.attrib[key].removesuffix('px')) for key in ('width', 'height')]
    assert width == height and width > 0
    rsvg, cairo, gobject = libraries()
    data = svg.encode() if isinstance(svg, str) else svg
    handle = rsvg.rsvg_handle_new_from_data(data, len(data), None)
    if not handle:
        raise ValueError('librsvg could not parse SVG')
    surface = context = None
    try:
        surface = cairo.cairo_image_surface_create(0, size, size)
        context = cairo.cairo_create(surface)
        cairo.cairo_scale(context, size / width, size / height)
        if not rsvg.rsvg_handle_render_cairo(handle, context):
            raise ValueError('librsvg could not render SVG')
        chunks = []
        callback_type = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(C.c_ubyte), C.c_uint)
        def write_png(_closure, data_pointer, length):
            chunks.append(C.string_at(data_pointer, length))
            return 0
        callback = callback_type(write_png)
        cairo.cairo_surface_write_to_png_stream.argtypes = [C.c_void_p, callback_type, C.c_void_p]
        cairo.cairo_surface_write_to_png_stream.restype = C.c_int
        if cairo.cairo_surface_write_to_png_stream(surface, callback, None):
            raise ValueError('Cairo PNG output failed')
        with Image.open(io.BytesIO(b''.join(chunks))) as image:
            return image.convert('RGBA')
    finally:
        if context:
            cairo.cairo_destroy(context)
        if surface:
            cairo.cairo_surface_destroy(surface)
        gobject.g_object_unref(handle)


def ink_bounds(svg, size=1600):
    box = render_svg(svg, size).getchannel('A').getbbox()
    assert box is not None, 'SVG has no painted artwork'
    return tuple(value * 16 / size for value in box)


def on_black(image):
    result = Image.new('RGB', image.size, '#000000')
    result.paste(image, (0, 0), image)
    return result


def font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/' + name, size)


def review_sheet(output, source=ICONS):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1140, 1050), '#000000')
    draw = ImageDraw.Draw(sheet)
    draw.text((32, 22), 'E64 — Current File Manager Icons', font=font(30, True), fill='#EEEEEE')
    draw.text((32, 67), 'Actual current SVG artwork • Black File Manager background • 160×160 and 32×32 renders', font=font(16), fill='#BBBBBB')
    for index, (name, category) in enumerate(CATEGORIES):
        x, y = 24 + index % 3 * 372, 110 + index // 3 * 304
        draw.rounded_rectangle((x, y, x + 348, y + 282), radius=10, outline='#333333')
        svg = (Path(source) / (name + '.svg')).read_text()
        for size, px, py in [(160, x + 28, y + 28), (32, x + 259, y + 92)]:
            image = render_svg(svg, size)
            image.save(output.parent / f'{name}-{size}.png')
            sheet.paste(image, (px, py), image)
        draw.text((x + 42, y + 198), '160 × 160', font=font(15), fill='#999999')
        draw.text((x + 240, y + 139), '32 × 32', font=font(15), fill='#BBBBBB')
        bounds = draw.textbbox((0, 0), category, font=font(19, True))
        draw.text((x + (348 - (bounds[2] - bounds[0])) // 2, y + 236), category, font=font(19, True), fill='#EEEEEE')
        draw.text((x + 12, y + 263), name + '.svg', font=font(11), fill='#777777')
    sheet.save(output)


def comparison_sheet(output, before, after=ICONS):
    """Both 160px and actual 32px renders, before and after, on black."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', (1650, 1100), '#000000')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), 'E64 — Icon Artwork Occupancy Comparison', font=font(29, True), fill='#EEEEEE')
    draw.text((24, 62), 'Uniform scaling only • Same 16×16 viewBox / 32×32 Web display • Actual SVG renders', font=font(17), fill='#BBBBBB')
    for index, (name, category) in enumerate(CATEGORIES):
        x, y = 18 + index % 3 * 545, 106 + index // 3 * 326
        draw.rounded_rectangle((x, y, x + 526, y + 304), radius=10, outline='#333333')
        for source, title, large_x, small_x in [(before, 'Before', x + 16, x + 410), (after, 'Optimized', x + 214, x + 463)]:
            svg = (Path(source) / (name + '.svg')).read_text()
            draw.text((large_x + 36, y + 18), title, font=font(16, True), fill='#BBBBBB')
            large, actual = render_svg(svg, 160), render_svg(svg, 32)
            sheet.paste(large, (large_x, y + 48), large)
            sheet.paste(actual, (small_x, y + 104), actual)
            draw.text((large_x + 38, y + 220), '160 × 160', font=font(14), fill='#999999')
            draw.text((small_x - 2, y + 146), title, font=font(10), fill='#BBBBBB')
        draw.text((x + 406, y + 76), '32 × 32', font=font(14), fill='#BBBBBB')
        draw.text((x + 16, y + 264), category, font=font(19, True), fill='#EEEEEE')
    sheet.save(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sheet', type=Path, default=ROOT / 'build/icon-review/all-file-icons-large.png')
    parser.add_argument('--comparison', type=Path)
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    if args.comparison and not args.before:
        parser.error('--comparison requires --before')
    review_sheet(args.sheet)
    print(args.sheet)
    if args.comparison:
        comparison_sheet(args.comparison, args.before)
        print(args.comparison)

if __name__ == '__main__':
    main()

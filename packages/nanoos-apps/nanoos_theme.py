#!/usr/bin/env python3
"""NanoOS theme engine.

Every NanoOS file (apps, GRUB theme, boot splash script, Kitty, fastfetch,
window decorations) is authored in the Glacier palette. `recolor_text()`
rewrites a file's colours into another theme:

  - accent colours (glacier cyan family)   -> the theme's accent
  - navy backgrounds, borders, muted text  -> the theme's background tint
  - near-white text                        -> the theme's foreground tint
  - everything else (status green/red/yellow, pure greys) is untouched

It understands #rrggbb, ANSI truecolour "38;2;R;G;B" and rgb()/rgba()
values, so the same function themes Python apps, Qt stylesheets, SVG,
GRUB theme.txt and terminal art.

Used by the installer (at copy time, once) and by the asset generator.
"""

import colorsys
import re

# Background, foreground, accent. Keep in sync with the installer's
# NANOOS_DESKTOP_THEMES and tools/glacier-theme/build_assets.py.
THEMES = {
    "Glacier":  ("#0b1118", "#e6eef6", "#66c7e8"),
    "Frost":    ("#111821", "#edf4fb", "#a4dcf7"),
    "Aurora":   ("#08140f", "#e1f1e9", "#6fd4a3"),
    "Ocean":    ("#06151e", "#ddf0f8", "#4fb8e6"),
    "Ember":    ("#170f0d", "#f6e8de", "#f0905f"),
    "Obsidian": ("#09090b", "#e9e9ec", "#8fa8ff"),
}
DEFAULT = "Glacier"


def theme_name(value):
    """Normalise a theme name ("obsidian", " Obsidian ") or fall back."""
    value = str(value or "").strip()
    for name in THEMES:
        if name.casefold() == value.casefold():
            return name
    return DEFAULT


def _hls(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


_G_BG, _G_FG, _G_ACCENT = (_hls(c) for c in THEMES[DEFAULT])


def _clamp(value):
    return max(0.0, min(1.0, value))


def _map_lightness(lightness, source, target):
    """Move `source` lightness to `target`, keeping 0 and 1 fixed."""
    if lightness <= source:
        return lightness * (target / source) if source else lightness
    return 1 - (1 - lightness) * ((1 - target) / (1 - source))


class Recolorer:
    def __init__(self, name):
        self.name = theme_name(name)
        bg, fg, accent = THEMES[self.name]
        self.bg, self.fg, self.accent = _hls(bg), _hls(fg), _hls(accent)
        self.identity = self.name == DEFAULT
        self._cache = {}

    def rgb(self, r, g, b):
        """Recolour one sRGB colour (0-255 ints). Returns (r, g, b)."""
        if self.identity:
            return r, g, b
        key = (r, g, b)
        if key in self._cache:
            return self._cache[key]
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        hue = h * 360
        # Only the Glacier family (cyan / navy, hue 180-228) is themed.
        if not (180 <= hue <= 228) or s < 0.05:
            out = (r, g, b)
        else:
            if l >= 0.84:                       # text / near white
                target_h = self.fg[0]
                s2 = s * (self.fg[2] / _G_FG[2] if _G_FG[2] else 1)
                l2 = l
            elif s >= 0.45 and l >= 0.08:       # accent family
                target_h = self.accent[0]
                s2 = s * (self.accent[2] / _G_ACCENT[2])
                l2 = _map_lightness(l, _G_ACCENT[1], self.accent[1])
                if l2 < 0.5:
                    s2 = min(s2, 0.72)          # dark accent shades: no neon
            else:                               # backgrounds, lines, muted
                target_h = self.bg[0]
                s2 = s * (self.bg[2] / _G_BG[2])
                l2 = l
            nr, ng, nb = colorsys.hls_to_rgb(target_h, _clamp(l2), _clamp(s2))
            out = (round(nr * 255), round(ng * 255), round(nb * 255))
        self._cache[key] = out
        return out

    def hex(self, value):
        r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
        nr, ng, nb = self.rgb(r, g, b)
        out = f"#{nr:02x}{ng:02x}{nb:02x}"
        return out.upper() if value[1:].isupper() else out


_HEX = re.compile(r"#[0-9a-fA-F]{6}(?![0-9a-fA-F])")
_ANSI = re.compile(r"38;2;(\d{1,3});(\d{1,3});(\d{1,3})")
_RGB_FN = re.compile(r"(rgba?\(\s*)(\d{1,3})(\s*,\s*)(\d{1,3})(\s*,\s*)(\d{1,3})")


def recolor_text(text, name, skip_line=None):
    """Return `text` with every Glacier colour moved to theme `name`.

    `skip_line(line) -> bool` leaves matching lines alone (e.g. the 16
    ANSI palette entries in kitty.conf, which must stay red/green/...).
    """
    recolor = Recolorer(name)
    if recolor.identity:
        return text

    def fix(segment):
        segment = _HEX.sub(lambda m: recolor.hex(m.group(0)), segment)
        segment = _ANSI.sub(
            lambda m: "38;2;%d;%d;%d" % recolor.rgb(*(int(v) for v in m.groups())),
            segment,
        )

        def rgb_fn(m):
            r, g, b = recolor.rgb(int(m.group(2)), int(m.group(4)), int(m.group(6)))
            return f"{m.group(1)}{r}{m.group(3)}{g}{m.group(5)}{b}"

        return _RGB_FN.sub(rgb_fn, segment)

    if skip_line is None:
        return fix(text)
    return "".join(
        line if skip_line(line) else fix(line)
        for line in text.splitlines(keepends=True)
    )


def recolor_file(path, name, skip_line=None):
    """Recolour a text file in place. Returns True if it changed."""
    with open(path, "r", encoding="utf-8") as handle:
        original = handle.read()
    updated = recolor_text(original, name, skip_line)
    if updated == original:
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(updated)
    return True


if __name__ == "__main__":
    import sys
    target = theme_name(sys.argv[1] if len(sys.argv) > 1 else "Obsidian")
    for sample in ("#66c7e8", "#9be3f7", "#2f8fb5", "#10293a", "#0b1118",
                   "#101b26", "#2c4256", "#7f93a7", "#e6eef6", "#65d58f",
                   "#ef6f7a", "#f2c66d", "#ffffff"):
        print(f"{sample} -> {Recolorer(target).hex(sample)}")

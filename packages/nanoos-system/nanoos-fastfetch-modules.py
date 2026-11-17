"""Rewrite the module list of a NanoOS fastfetch config, keeping its colours."""
import json, re, sys

MODULES = [
    {"type": "os",           "key": "OS"},
    {"type": "kernel",       "key": "Kernel"},
    {"type": "uptime",       "key": "Uptime"},
    {"type": "packages",     "key": "Packages"},
    {"type": "shell",        "key": "Shell"},
    {"type": "display",      "key": "Display", "compactType": "original-with-refresh-rate"},
    {"type": "de",           "key": "Desktop"},
    {"type": "wm",           "key": "Window Manager"},
    {"type": "theme",        "key": "Theme"},
    {"type": "terminal",     "key": "Terminal"},
    {"type": "terminalfont", "key": "Terminal Font"},
    {"type": "cpu",          "key": "CPU"},
    {"type": "gpu",          "key": "GPU"},
    {"type": "memory",       "key": "Memory"},
    {"type": "disk",         "key": "Disk", "folders": "/"},
    {"type": "localip",      "key": "Local IP", "showIpv4": True, "showIpv6": False, "compact": True},
]


def rewrite(path, out=None):
    raw = open(path, encoding="utf-8").read()
    header = "".join(l + "\n" for l in raw.splitlines() if l.lstrip().startswith("//"))
    body = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("//"))
    config = json.loads(body)
    old = config.get("modules", [])
    title = next((m for m in old if isinstance(m, dict) and m.get("type") == "title"), {"type": "title"})
    sep = next((m for m in old if isinstance(m, dict) and m.get("type") == "custom"), None)
    colors = next((m for m in old if isinstance(m, dict) and m.get("type") == "colors"),
                  {"type": "colors", "symbol": "circle", "paddingLeft": 1})
    config["modules"] = [title] + ([sep] if sep else []) + MODULES + ["break", colors]
    config.setdefault("display", {}).setdefault("key", {})["width"] = 17
    lines = [header + "{"]
    items = list(config.items())
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if key == "modules":
            mods = ",\n".join("    " + json.dumps(m, ensure_ascii=False) for m in value)
            lines.append(f'  "modules": [\n{mods}\n  ]{comma}')
        else:
            text = json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ")
            lines.append(f'  {json.dumps(key)}: {text}{comma}')
    lines.append("}")
    open(out or path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    rewrite(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

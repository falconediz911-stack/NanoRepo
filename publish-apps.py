"""Publish packages from out-packages/ into a signed NanoOS repo (merged with GitHub's DB).

    python3 publish-apps.py [--repo nanoos|nanoinstall] [--publish]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "NanoOS-Gaming/nanoos-installer/nanoos-gaming-rc20/tools/nanorepo"))
import publish as nanorepo

name = sys.argv[sys.argv.index("--repo") + 1] if "--repo" in sys.argv else "nanoos"
if name == "nanoos":
    spec = dict(nanorepo.REPOSITORIES["nanoos"])
elif name == "nanoinstall":
    spec = {"tag": "repo-nanoinstall",
            "title": "NanoOS repository: nanoinstall (NanoOS tools and apps)"}
else:
    raise SystemExit("unknown repo " + name)
spec["sources"] = [Path.home() / "NanoOS-Basic/NanoRepo/out-packages"]
nanorepo.OUT = Path.home() / "NanoOS-Basic/NanoRepo/out-repo"
nanorepo.require_signing_key(nanorepo.SIGNING_KEY)
assets = nanorepo.build_repository(name, spec, nanorepo.SIGNING_KEY)
if "--publish" in sys.argv:
    nanorepo.publish(name, spec, assets)

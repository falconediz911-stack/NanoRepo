"""Publish the app packages into the signed [nanoos] repo (merged with GitHub's DB)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "NanoOS-Gaming/nanoos-installer/nanoos-gaming-rc20/tools/nanorepo"))
import publish as nanorepo
spec = dict(nanorepo.REPOSITORIES["nanoos"])
spec["sources"] = [Path.home() / "NanoOS-Basic/NanoRepo/out-packages"]
nanorepo.OUT = Path.home() / "NanoOS-Basic/NanoRepo/out-repo"
nanorepo.require_signing_key(nanorepo.SIGNING_KEY)
assets = nanorepo.build_repository("nanoos", spec, nanorepo.SIGNING_KEY)
if "--publish" in sys.argv:
    nanorepo.publish("nanoos", spec, assets)

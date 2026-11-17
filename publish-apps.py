"""Publish packages from out-packages/ into a signed NanoOS repo (merged with GitHub's DB).

    python3 publish-apps.py [--repo nanoos|nanoinstall|nanoos-gaming] [--publish]
    python3 publish-apps.py --repo nanoos --remove PKGNAME [--publish]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "NanoOS-Gaming/nanoos-installer/nanoos-gaming-rc20/tools/nanorepo"))
import publish as nanorepo

name = sys.argv[sys.argv.index("--repo") + 1] if "--repo" in sys.argv else "nanoos"
if name == "nanoos":
    spec = dict(nanorepo.REPOSITORIES["nanoos"])
elif name == "nanoos-gaming":
    spec = dict(nanorepo.REPOSITORIES["nanoos-gaming"])
elif name == "nanoinstall":
    spec = {"tag": "repo-nanoinstall",
            "title": "NanoOS repository: nanoinstall (NanoOS tools and apps)"}
else:
    raise SystemExit("unknown repo " + name)
spec["sources"] = [Path.home() / "NanoOS-Basic/NanoRepo/out-packages"]
nanorepo.OUT = Path.home() / "NanoOS-Basic/NanoRepo/out-repo"
nanorepo.require_signing_key(nanorepo.SIGNING_KEY)

if "--remove" in sys.argv:
    # Drop a package from the published database (its files stay as assets).
    import shutil, subprocess
    package = sys.argv[sys.argv.index("--remove") + 1]
    staging = nanorepo.OUT / name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    if not nanorepo.fetch_published_database(name, spec, staging):
        raise SystemExit("repository not published yet")
    db = staging / f"{name}.db.tar.gz"
    nanorepo.run(["repo-remove", "--quiet", "--sign", "--key", nanorepo.SIGNING_KEY, "--verify", str(db), package], cwd=staging)
    assets = []
    for base in (f"{name}.db", f"{name}.files"):
        for suffix in ("", ".sig"):
            link, target = staging / (base + suffix), staging / (base + ".tar.gz" + suffix)
            link.unlink(missing_ok=True)
            shutil.copy2(target, link)
            assets.append(str(link))
    for asset in assets:
        if not asset.endswith(".sig"):
            nanorepo.verify(asset, nanorepo.SIGNING_KEY)
    print(f"  removed {package} from {name}")
    if "--publish" in sys.argv:
        nanorepo.publish(name, spec, assets)
    raise SystemExit(0)

assets = nanorepo.build_repository(name, spec, nanorepo.SIGNING_KEY)
if "--publish" in sys.argv:
    nanorepo.publish(name, spec, assets)

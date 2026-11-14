# NanoOS channel: `nanoos-kernel`

The NanoOS Gaming kernel: recipe, configuration, patches and changelog for each release. Kernels are published to the signed **`nanoos-gaming`** pacman repository (release `repo-nanoos-gaming`).

Kernel packages (≈170 MB) exceed GitHub's 100 MB limit for files in Git, and a ThinLTO + AutoFDO build is far too heavy for GitHub's runners. So this branch is the **source and history**; the binary is built locally and published with one command.

Layout for each release:

```
kernel/<pkgver>-<pkgrel>/PKGBUILD
kernel/<pkgver>-<pkgrel>/config.x86_64
kernel/<pkgver>-<pkgrel>/*.patch
CHANGELOG.md
```

Release steps:

1. Bump `pkgrel` (e.g. `7.2.9.zen1-2`). Every build needs a new version, otherwise pacman and the installer cannot tell builds apart.
2. Build with `makepkg`, boot-test it.
3. Copy the packages into the ISO profile `airootfs/usr/local/nanoos-gaming-kernel/`.
4. Publish (signs, verifies, merges into the online database):
   `GNUPGHOME=~/.local/share/nanorepo-signing/gnupg python3 tools/nanorepo/publish.py --repo nanoos-gaming --publish`
5. Commit the recipe and a CHANGELOG entry to this branch.

Status: empty. The current kernel (7.2.9.zen1-1, NanoSched burst v4, built 2026-11-13) was published before this branch existed.

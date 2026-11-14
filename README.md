# NanoOS channel: `nanoos-apps`

NanoOS desktop apps and tools: Welcome, Control Center, Game Mode and future apps.

**Pushing here publishes automatically.** Put each app's recipe in `packages/<package-name>/PKGBUILD` (plus its source or a pinned source URL). On push, GitHub Actions builds it in a disposable Arch container, signs it with the NanoOS repository key and merges it into the signed **`nanoos`** pacman repository (release `repo-nanoos`). NanoOS PCs get it with `sudo pacman -Syu`.

- Bump `pkgver`/`pkgrel` for every update; pacman only installs newer versions.
- No epoch (`1:`) in versions: GitHub cannot store `:` in file names.
- Publishing needs the repository secret `NANOREPO_GPG_PRIVATE_KEY_B64` (see below). Without it, packages are built and kept as workflow artifacts but not published.

```
gh secret set NANOREPO_GPG_PRIVATE_KEY_B64 -R falconediz911-stack/NanoRepo \
  --body "$(GNUPGHOME=~/.local/share/nanorepo-signing/gnupg gpg --export-secret-keys --armor D35A46A77EDBFD4F069B71ACB329E36F597CD358 | base64 -w0)"
```

Status: empty, no packages yet.

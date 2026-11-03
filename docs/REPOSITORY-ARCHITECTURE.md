# Repository architecture

## Source repository vs. Pacman repository

NanoRepo is the source-of-truth for package recipes, validation tools, documentation, and release automation. It is not itself a Pacman repository database.

A release pipeline will build package archives, sign them, generate signed repository databases with `repo-add`, and publish the artifacts to an HTTPS package host. The final host and base URL are deliberately unset until hosting, retention, and access controls are selected.

## Channels

| Pacman repository name | Source directory | Policy |
|---|---|---|
| `nanoos` | `packages/stable/` | Reviewed, tested releases |
| `nanoos-testing` | `packages/testing/` | Preview builds and release candidates |
| `nanoos-znver5` | `packages/znver5/` | Explicit opt-in Zen 5-specific packages |

A package is published to one channel at a time unless a deliberate promotion process copies the exact same artifact between channel databases. Stable promotion must preserve package checksums and provenance.

## Compatibility policy

- The generic `x86_64` channel must not require Zen 5-only instructions.
- The Zen 5 channel is opt-in and may use `-march=znver5` for eligible packages.
- Do not use `-march=native` in distributable package builds: that makes output depend on the build host.
- Do not put CPU-specific packages under generic names that could replace baseline packages accidentally.
- Package dependencies must remain resolvable within the intended channel and supported Arch base.

## Proposed publication tree

```text
repo-root/
  x86_64/
    nanoos.db
    nanoos.db.sig
    nanoos.files
    nanoos.files.sig
    nanoos-testing.db
    nanoos-testing.db.sig
    nanoos-znver5.db
    nanoos-znver5.db.sig
    *.pkg.tar.zst
    *.pkg.tar.zst.sig
```

The final publication layout may be split by channel directories instead. The publishing implementation will choose one canonical layout and generate pacman configuration examples from it; this document is a design target, not a live endpoint.

## Trust model

1. Review source changes before merge.
2. Build in clean chroots from pinned source revisions.
3. Record source commit, toolchain, build profile, checksums, and package metadata.
4. Sign package archives and repository databases with a dedicated release key.
5. Publish only after signature and repository consistency checks pass.
6. Keep private signing keys outside Git and ordinary CI logs.

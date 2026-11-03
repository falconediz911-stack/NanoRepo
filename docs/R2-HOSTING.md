# NanoRepo package hosting — Cloudflare R2

## Why R2

GitHub stores the source code, PKGBUILDs, CI workflows, and release history. It is not the binary package origin.

The published Pacman repository contains package archives, detached package signatures, repository databases, and database signatures. Cloudflare R2 provides an S3-compatible API suitable for publishing these files from GitHub Actions.

GitHub Pages is not selected for the package archive store: its published site has a 1 GB maximum, which is a poor fit for long-lived package archives and future kernel packages.

## One-time Cloudflare setup

1. Create an R2 bucket, for example `nanorepo`.
2. Create an R2 API token limited to **Object Read & Write** for that bucket only.
3. Connect a public custom domain to the bucket, proposed as `repo.nanoosproject.org`.
4. Confirm the domain serves objects over HTTPS.
5. Keep the bucket's S3 endpoint and access credentials private.

Cloudflare's S3 endpoint has the form:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

The public custom domain is used by Pacman clients; the S3 endpoint is used only by the publisher.

## GitHub Actions secrets

Add these repository Actions secrets to NanoRepo:

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`
- `NANOREPO_GPG_PRIVATE_KEY_B64` — base64-encoded ASCII-armored private signing key
- `NANOREPO_GPG_KEY_ID` — full signing-key ID
- `NANOREPO_GPG_PASSPHRASE` — passphrase for the dedicated release key

The publishing workflow is restricted to the default `main` branch. Do not store secrets in source files, workflow logs, PKGBUILDs, or artifacts. Use a dedicated NanoRepo signing key, not a personal everyday key. Protect the key and its recovery copy.

## Published object layout

```text
stable/x86_64/nanoos.db
stable/x86_64/nanoos.db.sig
stable/x86_64/*.pkg.tar.zst
stable/x86_64/*.pkg.tar.zst.sig

testing/x86_64/nanoos-testing.db
testing/x86_64/nanoos-testing.db.sig
testing/x86_64/*.pkg.tar.zst
testing/x86_64/*.pkg.tar.zst.sig

znver5/x86_64/nanoos-znver5.db
znver5/x86_64/nanoos-znver5.db.sig
znver5/x86_64/*.pkg.tar.zst
znver5/x86_64/*.pkg.tar.zst.sig
```

The publisher intentionally does not delete old package objects during sync. Retention and cleanup rules will be designed after the first signed repository is published, so a mistaken upload cannot immediately erase rollback packages.

## Current limitation

The publishing step skips with a notice until the R2 and signing secrets are configured. No package can be published until a PKGBUILD exists and a successful build produces an archive.

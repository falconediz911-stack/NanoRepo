# Activate the NanoOS GitHub update connections

This checklist activates the source workflows that are already merged into the default branches. Keep private tokens, signing keys, passphrases, and R2 credentials inside the relevant provider dashboards. Never put them in a Git commit, issue, screenshot, or chat.

## 1. ISO release → NanoOS Website and NanoRepo

Open the Actions secrets settings for:

`falconediz911-stack/NanoOS-Beta21-ISO`

Create two fine-grained GitHub personal access tokens. Each token should have access only to its named target repository and only the repository permission **Contents: Read and write**.

| Secret in the ISO repository | Token repository access |
|---|---|
| `NANOREPO_DISPATCH_TOKEN` | `falconediz911-stack/NanoRepo` only |
| `NANOOS_WEBSITE_DISPATCH_TOKEN` | `falconediz911-stack/nanoos-website` only |

Store each token as the matching repository Actions secret. Do not paste the values into source files.

The dispatch API requires Contents: write on the target repository. GitHub reference: https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event

## 2. NanoOS app source repositories → NanoRepo

The current GitHub account inventory has no separate GameMode, Welcome, Update, Installer, or kernel source repositories visible. The dispatch template is ready at:

`docs/templates/notify-nanorepo.yml`

For every actual app source repository:

1. Register its exact `owner/repository` name in `config/source-registry.json`.
2. Add its actual package name to that repository's `packages` allowlist.
3. Copy the template into that repository as `.github/workflows/notify-nanorepo.yml`.
4. Replace the placeholder package name and watched source paths.
5. Add a fine-grained token scoped only to NanoRepo with Contents: Read and write as the source repository's Actions secret `NANOREPO_DISPATCH_TOKEN`.

Do not register a source repo or package name until the matching source code and PKGBUILD exist and have been reviewed. An accepted event only starts a build when NanoRepo contains the matching `packages/<channel>/<package>/PKGBUILD`.

## 3. Configure Cloudflare R2 binary package hosting

The Pacman archive host is separate from GitHub source control.

1. Create an R2 bucket, suggested name: `nanorepo`.
2. Create an R2 S3 API token with **Object Read & Write**, scoped to that bucket only.
3. Connect a public HTTPS custom domain. The proposed domain is `repo.nanoosproject.org`; verify that the domain is available and controlled by NanoOS before using it.
4. Record the account ID, access key ID, and secret access key in a secure password manager.

Cloudflare setup reference: https://developers.cloudflare.com/r2/get-started/s3/

Add these Actions secrets to `falconediz911-stack/NanoRepo`:

- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`

## 4. NanoOS repository signing key

A dedicated Ed25519 key has been generated locally and its detached-signature test passed.

- User ID: `NanoOS Repository Signing`
- Fingerprint: `D35A46A77EDBFD4F069B71ACB329E36F597CD358`
- Long key ID: `B329E36F597CD358`
- Expires: 2028-11-03
- Public key: `keys/nanoos-repo-signing-2026.asc`
- Keyring package recipe: `packages/stable/nanoos-keyring/PKGBUILD`

The public key and keyring recipe are being reviewed in a development branch. The private key, passphrase, and revocation certificate must never be committed, attached to CI artifacts, or pasted into chat. Keep a protected offline recovery copy.

Before client trust is enabled, publish the full fingerprint through an independent trusted NanoOS channel, verify the keyring package behavior, and document key rotation and revocation. The initial key bootstrap requires an administrator to compare the full fingerprint independently, then add and locally sign the public key with Pacman. A keyring package cannot authenticate itself.

When the repository is ready for signed publishing, add these Actions secrets to NanoRepo:

- `NANOREPO_GPG_PRIVATE_KEY_B64` — base64-encoded ASCII-armored private key
- `NANOREPO_GPG_KEY_ID` — use the full fingerprint, not the short key ID
- `NANOREPO_GPG_PASSPHRASE` — signing-key passphrase

Add secrets only after the workflow and branch-protection policy have been reviewed. Never expose secret values to chat or logs.

## 5. Add and validate package recipes

The first package recipe exists and has been built in pull-request CI:

- `packages/stable/nanoos-cpu-info/PKGBUILD`
- Package: `nanoos-cpu-info` 0.1.0-1
- License: MIT
- Architecture: `any`
- Build: successful in the disposable Arch container used by pull-request CI
- Pacman install and run: successful on a bare-metal Arch system
- JSON output and package ownership listing: successful
- Pacman removal: successful
- Package upgrade: not yet tested

The initial keyring package is under development:

- `packages/stable/nanoos-keyring/PKGBUILD`
- Package: `nanoos-keyring` 20261104-1
- Contains public keyring data and owner-trust metadata only
- Arch build and Pacman population tests: pending CI and real-machine testing

Add and review further installable NanoOS packages under one of:

- `packages/stable/<package>/PKGBUILD`
- `packages/testing/<package>/PKGBUILD`
- `packages/znver5/<package>/PKGBUILD`

The Zen 5 channel is explicit opt-in only. Do not enable it on non-Zen-5 systems.

## 6. Finish NanoOS Update ISO integration

The ISO release workflow and website receiver are in place. When a real ISO GitHub Release is published with its ISO parts and checksum attached, the website writes:

`public/releases/iso-latest.json`

The NanoOS Update client has not yet been changed to consume this feed. Its source repository is not currently visible in the connected GitHub inventory, so that client change remains pending until its source is added.

## 7. Smoke-test the connections

After secrets and source repos are configured:

1. Test package upgrade behavior with a later build of `nanoos-cpu-info`.
2. Build and test `nanoos-keyring` on the real Arch machine after independently checking its public-key fingerprint.
3. Create the R2 bucket/domain and configure protected signing/publishing secrets.
4. Publish first to Testing; verify package and database signatures on the real Arch machine.
5. Push a harmless source change to a registered app repo; verify NanoRepo accepts the registered event.
6. Publish a test ISO release only when the ISO and checksum assets are ready; verify the website ISO feed is updated.
7. Only then add the Stable repository configuration to NanoOS clients.

## Current readiness

- NanoRepo workflows merged: yes.
- Static validation on `main`: passed.
- `nanoos-cpu-info` Arch package build: passed.
- AMD, Intel, and ARM-style CPU fixture tests: passed in CI.
- Bare-metal Arch Pacman install/run/JSON/ownership/removal test for `nanoos-cpu-info`: passed.
- Initial Ed25519 signing key generated and local detached-signature verification: passed.
- Public signing key source and `nanoos-keyring` recipe: under review in a development branch.
- `nanoos-keyring` Arch build and Pacman population test: pending.
- Public fingerprint through an independent channel: pending.
- R2 bucket/domain and GitHub Actions secrets: not configured.
- NanoOS Update reading the ISO feed: pending.

The proposed Pacman URL is not live until package signing, trust bootstrap, hosting, and real-machine verification are complete.

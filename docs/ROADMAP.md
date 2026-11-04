# NanoRepo roadmap

## Phase 1 — Foundation and source connections
- [x] Create NanoRepo source repository
- [x] Define stable, testing, and Zen 5 channel policies
- [x] Document repository trust and release architecture
- [x] Add Zen 5 build-profile example
- [x] Add CPU Engine design specification
- [x] Add static repository validation and CI
- [x] Add read-only CPU capability discovery prototype and unit tests
- [x] Add AMD, Intel, and ARM-style CPU-info fixture coverage
- [x] Add source-repository allowlist and dispatch validator
- [x] Add generic app-source dispatch template
- [x] Add disposable Arch-container package build workflow
- [x] Add conditional signed Cloudflare R2 publishing workflow
- [x] Add Pacman client configuration and hosting instructions
- [x] Merge NanoRepo source-connection workflow into `main`
- [x] Merge ISO release hook and website ISO-feed hook
- [ ] Add source-repository dispatch secrets

## Phase 2 — Package set
- [ ] Audit existing NanoOS app and kernel source trees
- [x] Confirm MIT licensing for the `nanoos-cpu-info` component
- [x] Add the first reviewed Stable PKGBUILD: `nanoos-cpu-info` 0.1.0-1
- [x] Build the package archive successfully in Arch-container CI
- [x] Smoke-test the extracted command on a development Arch host
- [ ] Complete Pacman install, upgrade, and removal tests in a disposable Arch VM
- [ ] Add further reviewed PKGBUILDs for the remaining NanoOS components
- [ ] `nanoos-release` and base meta-package
- [ ] NanoOS GameMode package
- [ ] NanoOS Welcome package
- [ ] NanoOS Update package
- [ ] NanoOS Installer tools package
- [ ] `nan` package
- [ ] NanoOS Gaming kernel package and matching headers
- [ ] Hardware profiles and gaming presets

## Phase 3 — CPU Engine and Zen 5
- [x] Read-only hardware and sysfs capability discovery prototype
- [ ] CPU profile policy and dry-run
- [ ] Reversible profile application and restore
- [ ] Telemetry and benchmark utilities
- [ ] Zen 5-specific package naming and build validation
- [ ] Zen 5 hardware testing and benchmark evidence

## Phase 4 — Repository operations
- [ ] Create R2 bucket and connect a public HTTPS custom domain
- [ ] Create dedicated package-signing key and publish its fingerprint
- [ ] Configure NanoRepo R2 and GPG Actions secrets
- [ ] Build the NanoOS keyring package and document trust bootstrap/revocation
- [ ] Publish a first signed Testing repository
- [ ] Verify package and database signatures in a disposable VM
- [ ] Verify install, upgrade, and rollback in disposable VMs
- [ ] Enable Stable publication after testing
- [ ] Stable promotion and retention procedure
- [ ] Add a Zen 5 opt-in client configuration after hardware validation

## Phase 5 — Release quality and client integration
- [ ] Update NanoOS Update to read `iso-latest.json`
- [ ] Add registered source workflows for each NanoOS app repository
- [ ] Reproducibility checks for selected packages
- [ ] Automated dependency and vulnerability review
- [ ] Release manifests and checksums
- [ ] Public package index and documentation

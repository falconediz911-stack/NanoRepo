# NanoRepo roadmap

## Phase 1 — Foundation and source connections
- [x] Create NanoRepo source repository
- [x] Define stable, testing, and Zen 5 channel policies
- [x] Document repository trust and release architecture
- [x] Add Zen 5 build-profile example
- [x] Add CPU Engine design specification
- [x] Add static repository validation and CI
- [x] Create `reponanoult` working branch
- [x] Add read-only CPU capability discovery prototype and unit tests
- [x] Add source-repository allowlist and dispatch validator
- [x] Add generic app-source dispatch template
- [x] Add disposable Arch-container package build workflow
- [x] Add conditional signed Cloudflare R2 publishing workflow
- [x] Add Pacman client configuration and hosting instructions
- [x] Prepare ISO release metadata workflow in the ISO repository
- [x] Prepare separate ISO feed updater in the website repository
- [ ] Merge the NanoRepo source-connection PR into main
- [ ] Merge the ISO release hook and website feed hook PRs
- [ ] Add source-repository dispatch secrets

## Phase 2 — Package set
- [ ] Audit existing NanoOS app and kernel source trees
- [ ] Confirm project/package licensing and source provenance
- [ ] Add reviewed PKGBUILDs
- [ ] nanoos-release and base meta-package
- [ ] NanoOS GameMode package
- [ ] NanoOS Welcome package
- [ ] NanoOS Update package
- [ ] NanoOS Installer tools package
- [ ] nan package
- [ ] NanoOS Gaming kernel package and matching headers
- [ ] Hardware profiles and gaming presets
- [ ] Package the read-only CPU discovery utility

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
- [ ] Publish a first signed Testing repository
- [ ] Build a NanoOS keyring package and trust bootstrap
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

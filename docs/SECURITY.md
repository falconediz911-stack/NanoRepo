# Security and trust policy

## Package authenticity

- Require package signature verification in supported client configuration.
- Sign repository databases as well as package archives.
- Publish the signing-key fingerprint through an independent trusted channel.
- Document key rotation, revocation, and recovery before production launch.

## Build isolation

- Build PKGBUILDs in disposable clean chroots.
- Review PKGBUILD source URLs, checksums, install scripts, and dependencies.
- Do not execute unreviewed PKGBUILDs on a daily-use system.
- Keep build and signing credentials separate.

## Secrets

Never commit private OpenPGP keys, access tokens, passwords, deploy credentials, or signing passphrases. Use protected release secrets or a dedicated signing environment. Do not print secrets in workflow logs.

## Vulnerability reports

Please do not publish exploitable details in public issues. Contact the NanoOS maintainers privately through a separately verified contact method. A public contact address will be added when one is designated.

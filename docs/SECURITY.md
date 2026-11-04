# Security and trust policy

## Package authenticity

- Require package signature verification in supported client configuration.
- Sign repository databases as well as package archives.
- Publish the signing-key fingerprint through an independent trusted channel.
- Document key rotation, revocation, and recovery before production launch.
- Never use `TrustAll`, `SigLevel = Never`, or disabled signature checking as a workaround for trust errors.

## Initial NanoOS signing identity

The initial repository signing key was generated locally on 2026-11-04 and successfully tested by signing and verifying a detached test-file signature.

- User ID: `NanoOS Repository Signing`
- Algorithm: Ed25519
- Full fingerprint: `D35A46A77EDBFD4F069B71ACB329E36F597CD358`
- Long key ID: `B329E36F597CD358`
- Expiration: 2028-11-03

The public key is stored at `keys/nanoos-repo-signing-2026.asc`. The private key and its passphrase must never be committed, included in a package, uploaded as a build artifact, or printed in logs. The private key is used only by a protected release-signing environment. Keep a secure offline recovery copy and the corresponding revocation certificate.

A new client must verify the full fingerprint through an independent trusted channel before adding and locally signing the public key with `pacman-key`. A keyring package cannot authenticate itself. The initial public-key bootstrap and later keyring package are separate trust steps.

Publish a new keyring before the current key expires. If the private key is suspected compromised, stop signing immediately, publish revocation information through an independently trusted channel, and issue a replacement key with a new fingerprint.

## Build isolation

- Build PKGBUILDs in disposable clean chroots or disposable build containers.
- Review PKGBUILD source URLs, checksums, install scripts, and dependencies.
- Do not execute unreviewed PKGBUILDs on a daily-use system.
- Keep build credentials and release-signing credentials separate where practical.
- Protect the default branch and review changes to package workflows before allowing them to access signing secrets.

## Secrets

Never commit private OpenPGP keys, access tokens, passwords, deploy credentials, or signing passphrases. Use protected release secrets or a dedicated signing environment. Do not print secrets in workflow logs. Restrict the signing key to NanoRepo releases, and keep Actions secrets available only to trusted main-branch workflows.

## Vulnerability reports

Please do not publish exploitable details in public issues. Contact the NanoOS maintainers privately through a separately verified contact method. A public contact address will be added when one is designated.

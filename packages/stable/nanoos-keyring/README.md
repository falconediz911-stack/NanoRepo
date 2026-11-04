# nanoos-keyring 20261104-1

Initial public signing keyring package for NanoRepo.

## Signing identity

- User ID: NanoOS Repository Signing
- Algorithm: Ed25519
- Full fingerprint: `D35A46A77EDBFD4F069B71ACB329E36F597CD358`
- Long key ID: `B329E36F597CD358`
- Created: 2026-11-04
- Expires: 2028-11-03

The private key is not stored in this repository or package. Only the public key is distributed.

## Installed keyring files

- `/usr/share/pacman/keyrings/nanoos.gpg` — binary OpenPGP public keyring
- `/usr/share/pacman/keyrings/nanoos-trusted` — GnuPG owner-trust entry for the verified repository signing key
- `/usr/share/pacman/keyrings/nanoos-repo-signing-2026.asc` — armored public key for inspection and bootstrap
- `/usr/share/licenses/nanoos-keyring/LICENSE` — package metadata notice

The package install/upgrade hook invokes `pacman-key --populate nanoos` when the local Pacman keyring is initialized.

## Initial trust bootstrap

A keyring package cannot establish its own authenticity. Before using a NanoOS repository for the first time, obtain the armored public key through an independently trusted source and compare its full fingerprint with the value published in the NanoOS release documentation:

`D35A46A77EDBFD4F069B71ACB329E36F597CD358`

Only after the fingerprint matches exactly should an administrator add and locally sign the key in Pacman's keyring:

```sh
sudo pacman-key --add nanoos-repo-signing-2026.asc
sudo pacman-key --fingerprint D35A46A77EDBFD4F069B71ACB329E36F597CD358
sudo pacman-key --lsign-key D35A46A77EDBFD4F069B71ACB329E36F597CD358
```

Then enable the NanoOS repository with required package and database signatures. Do not use `TrustAll`, `SigLevel = Never`, or disable signature checks to bypass bootstrap errors.

The key expires on 2028-11-03. Publish a replacement keyring package and communicate a fingerprint-verified rotation plan before expiry. If the key is compromised, publish revocation information and stop signing with it immediately.

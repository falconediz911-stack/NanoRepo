# NanoOS repository signing key

Initial public key for signing NanoRepo package archives and Pacman repository databases.

| Field | Value |
|---|---|
| User ID | NanoOS Repository Signing |
| Algorithm | Ed25519 |
| Fingerprint | `D35A46A77EDBFD4F069B71ACB329E36F597CD358` |
| Long key ID | `B329E36F597CD358` |
| Created | 2026-11-04 |
| Expires | 2028-11-03 |

Public key file: [`nanoos-repo-signing-2026.asc`](nanoos-repo-signing-2026.asc)

This directory must never contain secret-key exports, passphrases, GPG private-key backups, or revocation certificates. Keep those protected offline. The public fingerprint must also be published through a separate trusted NanoOS channel before repository clients rely on it.

Before the key expires, publish and verify a replacement key with a documented transition. If compromise is suspected, stop using this key and publish revocation information independently.

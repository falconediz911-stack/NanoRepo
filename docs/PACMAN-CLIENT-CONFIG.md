# NanoRepo Pacman client configuration

> The host below is a proposed name. It is not live until a Cloudflare R2 bucket is connected to a public custom domain and the publish workflow has been configured.

Proposed public base URL: `https://repo.nanoosproject.org`

Add only the channels you intend to use to `/etc/pacman.conf`.

## Stable

```ini
[nanoos]
SigLevel = Required DatabaseRequired
Server = https://repo.nanoosproject.org/stable/$arch
```

## Testing (optional)

```ini
[nanoos-testing]
SigLevel = Required DatabaseRequired
Server = https://repo.nanoosproject.org/testing/$arch
```

## AMD Zen 5 (opt-in only)

```ini
[nanoos-znver5]
SigLevel = Required DatabaseRequired
Server = https://repo.nanoosproject.org/znver5/$arch
```

Do not enable the Zen 5 channel on older or unverified CPUs. Pacman does not automatically choose packages based on CPU capabilities. Packages in this channel may contain Zen 5-only instructions.

## Initial trust bootstrap

The initial NanoOS repository signing identity is:

- User ID: `NanoOS Repository Signing`
- Algorithm: Ed25519
- Full fingerprint: `D35A46A77EDBFD4F069B71ACB329E36F597CD358`
- Long key ID: `B329E36F597CD358`
- Expiration: 2028-11-03

Obtain `nanoos-repo-signing-2026.asc` from the official NanoRepo source and compare its full fingerprint with the value above using an independent trusted publication of the fingerprint. Do not rely solely on a key file and fingerprint served from the same unverified location.

Only after the fingerprint matches exactly, add and locally sign the key:

```sh
sudo pacman-key --add nanoos-repo-signing-2026.asc
sudo pacman-key --fingerprint D35A46A77EDBFD4F069B71ACB329E36F597CD358
sudo pacman-key --lsign-key D35A46A77EDBFD4F069B71ACB329E36F597CD358
```

The `nanoos-keyring` package installs the binary keyring and owner-trust metadata under `/usr/share/pacman/keyrings/`, then invokes `pacman-key --populate nanoos` when Pacman's local keyring is initialized. The initial local fingerprint verification is still required; a keyring package cannot establish its own authenticity.

Do not weaken signature policy to bypass trust errors. In particular, do not use `TrustAll` or `SigLevel = Never`.

After the repository host is live and the signing key is trusted, refresh and update with:

```sh
sudo pacman -Syyu
```

The above configuration is a template only; the proposed URL is not currently a functioning package service.

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

## Trust bootstrap

The package-signing key must be distributed and verified independently before enabling a repository with required signatures. The NanoOS keyring package and its fingerprint/revocation procedure have not yet been created. Do not weaken `SigLevel` to bypass missing signatures.

After the repository host is live and the trusted key is installed, refresh and update with:

```sh
sudo pacman -Syyu
```

The above configuration is a template only; the proposed URL is not currently a functioning package service.

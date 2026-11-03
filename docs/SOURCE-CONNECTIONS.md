# Connecting NanoOS source repositories to NanoRepo

## Two different update pipelines

NanoOS has two kinds of deliverables and they must not be mixed.

### 1. Applications and system tools → Pacman

1. App source is committed to its registered GitHub source repository.
2. That repository sends a `repository_dispatch` event to NanoRepo.
3. NanoRepo checks the sender and package name against `config/source-registry.json`.
4. The matching PKGBUILD fetches a pinned or versioned source revision and builds a package in an isolated Arch Linux job container.
5. The package is tested, signed, added to the channel database, and published to the configured package host.
6. NanoOS clients run `pacman -Syu` to retrieve the newer package database and package files.

A push to NanoRepo paths `components/**`, `packages/**`, or `packaging/**` also starts the local package build workflow.

A package is not installable through Pacman until a real PKGBUILD exists, the package builds successfully, signatures are configured, and the package repository has been published.

### 2. ISO releases → NanoOS Update feed

An ISO is not a Pacman package. Publishing a new ISO release in `NanoOS-Beta21-ISO` sends a separate metadata event. The website workflow writes `public/releases/iso-latest.json`.

NanoOS Update must be taught to read this ISO feed (in addition to its existing app/system update feed) before clients can display or install the new ISO. Publishing metadata alone does not install or update an operating system.

## Currently registered GitHub sources

| Repository | Role | Pacman build? |
|---|---|---|
| `falconediz911-stack/NanoRepo` | Components and package recipes | Yes, for registered packages |
| `falconediz911-stack/NanoOS-Beta21-ISO` | ISO release metadata | No |
| `falconediz911-stack/nanoos-website` | Website/update metadata | No |

Only `nanoos-cpu-info` is currently registered as a NanoRepo component package name. It still needs a reviewed PKGBUILD before it can be built and published.

Other NanoOS app source repositories must be added to the registry with an explicit package name before their dispatch events are accepted. Do not register a repository until its source path, license, dependencies, install paths, and package update strategy have been reviewed.

## Connecting an app repository

Copy `docs/templates/notify-nanorepo.yml` into the app repository's default branch, then customize the watched paths and package name.

Create a fine-grained token scoped only to NanoRepo with repository permission **Contents: write**, then add it to the app source repository as the Actions secret `NANOREPO_DISPATCH_TOKEN`. GitHub documents that permission for the repository-dispatch endpoint.

Add the app repository and its package name to NanoRepo's source registry. The dispatch will be rejected until that allowlist entry exists.

## Event names

- `nanoos.tool.source.updated`: source change for a registered package; may trigger package building.
- `nanoos.iso.published`: ISO release metadata only; never triggers a Pacman package build.
- `nanoos.website.feed.updated`: website metadata only; never triggers a Pacman package build.

All dispatch payloads are treated as untrusted input and checked against the allowlist.

# NanoOS channel: `nanoos-iso`

NanoOS installer ISO releases. `latest.json` describes the newest ISO; the website and update tools read it from:

`https://raw.githubusercontent.com/falconediz911-stack/NanoRepo/nanoos-iso/latest.json`

ISOs (≈4.6 GB) exceed GitHub's 2 GiB release-file limit, so each release `iso-<version>` holds the ISO in parts, `SHA256SUMS` (full ISO and every part) and `JOIN.txt`. Publish from the ISO profile:

```
python3 tools/nanorepo/publish_iso.py ~/nanoos-iso-out/<iso> --version <version>            # dry run
python3 tools/nanorepo/publish_iso.py ~/nanoos-iso-out/<iso> --version <version> --signed --publish
```

That creates the release and updates `latest.json` on this branch. The format keeps the fields of the website's `public/releases/latest.json` (`schema_version`, `product`, `channel`, `version`, `release_notes_url`, `published_at`, `summary`) and adds an `iso` object with the parts and checksums.

Status: empty, no ISO published yet.

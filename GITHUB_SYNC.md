# GitHub sync channel (delivery)

- Remote: https://github.com/jfjdjdieifne/b (branch `main`)
- Policy: every completed, verified task is committed and pushed automatically.
  No zip requests needed — `git pull` (or the GitHub UI) is the delivery channel.
- Zip bundles remain order-only artifacts; when needed they are published as
  GitHub Releases (repo file limit), never as recurring uploads.
- NEVER committed: `uploads/` (owner data), `*.zip`, credential files, caches.
- Owner-data boundary stands: raw aggTrades / minutefacts / sidecar stay on the
  OWNER PC and are never pushed.

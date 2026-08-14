# Cloudflare scheduler

This Worker is only the five-minute clock for the existing GitHub workflow. It
does not store or serve the feed. The Python updater, SQLite database, commits,
and GitHub Pages deployment remain unchanged.

## One-time setup

1. Create a fine-grained GitHub personal access token restricted to
   `Seraangel/feed-golem` with the **Contents: Read and write** repository
   permission.
2. From this directory, authenticate and deploy the Worker:

   ```powershell
   npx wrangler login
   npx wrangler secret put GITHUB_TOKEN
   npx wrangler deploy
   ```

   Paste the GitHub token only when Wrangler asks for the secret. Do not put it
   in this repository or in `wrangler.toml`.

3. The Worker intentionally has no public URL. Verify its Cron Trigger and
   execution logs in **Cloudflare Dashboard -> Workers & Pages ->
   `feed-golem-scheduler`**.

Cloudflare invokes the Worker's `scheduled()` handler every five minutes (UTC).
The Worker sends GitHub a `repository_dispatch` event every five minutes from
06:00 through 22:55, and once per hour from 23:00 through 05:59, in the
`Europe/Berlin` time zone. This keeps the overnight rule correct across daylight
saving-time changes.

Each dispatch event is named
`cloudflare-feed-tick`, which triggers `.github/workflows/update-feed.yml`.

## Operations

- Cloudflare Dashboard -> Workers & Pages -> `feed-golem-scheduler` shows Cron
  Trigger executions and logs.
- `workers.dev` and preview URLs are disabled, so public requests cannot consume
  the Free-plan Worker request quota.
- GitHub Actions shows runs as `Repository dispatch` rather than `Scheduled`.
- To trigger a feed update immediately, continue using **Run workflow** in
  GitHub Actions.

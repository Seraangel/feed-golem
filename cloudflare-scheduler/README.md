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

3. Open `https://feed-ftip-scheduler.<your-workers-subdomain>.workers.dev/healthz`.
   It should return `{ "status": "ok" }`.

Cloudflare invokes the Worker's `scheduled()` handler every five minutes (UTC).
Each invocation sends GitHub a `repository_dispatch` event named
`cloudflare-feed-tick`, which triggers `.github/workflows/update-feed.yml`.

## Operations

- Cloudflare Dashboard -> Workers & Pages -> `feed-ftip-scheduler` shows Cron
  Trigger executions and logs.
- GitHub Actions shows runs as `Repository dispatch` rather than `Scheduled`.
- To trigger a feed update immediately, continue using **Run workflow** in
  GitHub Actions.

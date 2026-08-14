/**
 * Dispatches the RSS update workflow on an external five-minute clock.
 * This Worker deliberately contains no feed data or persistence.
 */

const GITHUB_DISPATCH_URL =
  "https://api.github.com/repos/Seraangel/feed-ftip/dispatches";

async function dispatchFeedUpdate(token) {
  if (!token) {
    throw new Error("GITHUB_TOKEN secret is not configured.");
  }

  const response = await fetch(GITHUB_DISPATCH_URL, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "User-Agent": "feed-ftip-cloudflare-scheduler",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ event_type: "cloudflare-feed-tick" }),
  });

  if (!response.ok) {
    throw new Error(
      `GitHub repository dispatch failed (${response.status}): ${await response.text()}`,
    );
  }
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(dispatchFeedUpdate(env.GITHUB_TOKEN));
  },

  async fetch(request) {
    if (new URL(request.url).pathname !== "/healthz") {
      return new Response("Not found", { status: 404 });
    }
    return Response.json({ status: "ok" });
  },
};

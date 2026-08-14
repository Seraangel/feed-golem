/**
 * Dispatches the RSS update workflow on an external five-minute clock.
 * This Worker deliberately contains no feed data or persistence.
 */

const GITHUB_DISPATCH_URL =
  "https://api.github.com/repos/Seraangel/feed-golem/dispatches";
const BERLIN_TIME = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Berlin",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function shouldDispatch(scheduledTime) {
  const values = Object.fromEntries(
    BERLIN_TIME.formatToParts(scheduledTime)
      .filter(({ type }) => type === "hour" || type === "minute")
      .map(({ type, value }) => [type, Number(value)]),
  );
  const overnight = values.hour >= 23 || values.hour < 6;

  // During 23:00–05:59 in Berlin, request one update on each full hour.
  return !overnight || values.minute === 0;
}

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
      "User-Agent": "feed-golem-cloudflare-scheduler",
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
  async scheduled(controller, env, ctx) {
    if (!shouldDispatch(new Date(controller.scheduledTime))) {
      return;
    }
    ctx.waitUntil(dispatchFeedUpdate(env.GITHUB_TOKEN));
  },

  async fetch(request) {
    if (new URL(request.url).pathname !== "/healthz") {
      return new Response("Not found", { status: 404 });
    }
    return Response.json({ status: "ok" });
  },
};

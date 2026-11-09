/* Navigation fallback only. Never store HTML, API responses or financial data. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("fetch", (event) => {
  if (
    event.request.mode !== "navigate" ||
    new URL(event.request.url).origin !== self.location.origin
  )
    return;
  event.respondWith(
    fetch(event.request, { cache: "no-store" }).catch(
      () =>
        new Response(
          '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#183e36"><title>PocketWatcher · Reconnect</title><style>body{margin:0;min-height:100dvh;display:grid;place-items:center;background:#f5f5ef;color:#183e36;font:16px system-ui}main{padding:32px;max-width:340px}h1{font-size:28px}p{line-height:1.6;color:#627567}a{display:inline-block;margin-top:16px;padding:14px 22px;border-radius:12px;background:#183e36;color:#fff;text-decoration:none}</style><main><h1>Let’s reconnect.</h1><p>Connect to the internet to open your household budget.</p><a href="/">Try again</a></main></html>',
          {
            status: 503,
            headers: {
              "Content-Type": "text/html; charset=utf-8",
              "Cache-Control": "no-store",
              "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
            },
          },
        ),
    ),
  );
});

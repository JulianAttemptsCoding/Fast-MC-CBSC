import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the event observatory shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>CBSC ZDC Event Observatory<\/title>/i);
  assert.match(html, /Loading immutable epoch evidence/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|SkeletonPreview/);
});

test("ships a labeled five-draw dashboard fixture and no starter remnants", async () => {
  const [page, layout, dashboard, packageJson, manifestText, epochText] =
    await Promise.all([
      readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
      readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
      readFile(new URL("../app/ZdcDashboard.tsx", import.meta.url), "utf8"),
      readFile(new URL("../package.json", import.meta.url), "utf8"),
      readFile(new URL("../public/demo/manifest.json", import.meta.url), "utf8"),
      readFile(new URL("../public/demo/epoch_0000.json", import.meta.url), "utf8"),
    ]);
  const manifest = JSON.parse(manifestText);
  const epoch = JSON.parse(epochText);

  assert.match(page, /ZdcDashboard/);
  assert.match(layout, /CBSC ZDC Event Observatory/);
  assert.match(dashboard, /One Geant4 truth/);
  assert.match(dashboard, /five-draw mean/i);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.equal(manifest.schema_version, 1);
  assert.equal(epoch.draws_per_condition, 5);
  assert.equal(epoch.qa.test_events_used, 0);
  assert.equal(epoch.qa.pass, true);
  assert.equal(epoch.synthetic_source, true);
  assert.match(epoch.scientific_status, /not Geant4 and not physics validation/i);

  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
  await access(new URL("../public/demo/geometry.json", import.meta.url));
  await access(new URL("../public/demo/epoch_0000.json", import.meta.url));
  await access(root);
});

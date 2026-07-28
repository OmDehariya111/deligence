import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const source = async (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("job creation submits optional context through multipart form data", async () => {
  const home = await source("src/app/page.tsx");
  assert.match(home, /new FormData\(\)/);
  assert.match(home, /context_file/);
});

test("session and report safety guards remain in place", async () => {
  const auth = await readFile(new URL("../../api/auth_routes.py", import.meta.url), "utf8");
  const report = await source("src/app/job/[id]/page.tsx");
  assert.match(auth, /path="\/"/);
  assert.doesNotMatch(report, /sandbox="allow-scripts allow-same-origin/);
  assert.doesNotMatch(report, /http:\/\/localhost:8000/);
});

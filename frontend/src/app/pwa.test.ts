import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(__dirname, "../../public");

test("manifest is installable", () => {
  const manifest = JSON.parse(readFileSync(resolve(root, "manifest.webmanifest"), "utf8"));
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.name).toBeTruthy();
  expect(manifest.short_name).toBeTruthy();
  expect(manifest.theme_color).toMatch(/^#/);
  const sizes = manifest.icons.map((icon: { sizes: string }) => icon.sizes);
  expect(sizes).toContain("192x192");
  expect(sizes).toContain("512x512");
});

test("service worker never touches API, SSE or login", () => {
  const source = readFileSync(resolve(root, "sw.js"), "utf8");
  expect(source).toMatch(/BYPASS = \["\/api\/", "\/login", "\/health"\]/);
  expect(source).toContain("text/event-stream");
  expect(source).toContain('request.method !== "GET"');
});

test("index has apple touch icon and safe-area viewport", () => {
  const html = readFileSync(resolve(__dirname, "../../index.html"), "utf8");
  expect(html).toContain('rel="apple-touch-icon"');
  expect(html).toContain("viewport-fit=cover");
  expect(html).toContain('rel="manifest"');
});

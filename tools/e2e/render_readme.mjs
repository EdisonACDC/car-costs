// Screenshots of the README as GitHub renders it (HTML from `gh api markdown`), top part and full page.
// Usage: gh api markdown -f mode=gfm -F text=@../../README.md > /tmp/README.html && node render_readme.mjs /tmp/README.html readme-en
import { chromium } from "playwright";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../..");
const [htmlFile, name] = process.argv.slice(2);
const css = fs.readFileSync(path.join(here, "node_modules/github-markdown-css/github-markdown.css"), "utf8");
const body = fs.readFileSync(htmlFile, "utf8");
const browser = await chromium.launch();
for (const scheme of ["light", "dark"]) {
  const page = await (await browser.newContext({ viewport: { width: 1012, height: 900 }, colorScheme: scheme })).newPage();
  const file = path.join(os.tmpdir(), `readme-${name}-${scheme}.html`);
  fs.writeFileSync(file, `<base href="file:///${repo.replaceAll("\\", "/")}/"><style>${css}body{margin:0;padding:32px;background:${scheme === "dark" ? "#0d1117" : "#fff"}}.markdown-body{max-width:980px;margin:0 auto}</style><article class="markdown-body">${body}</article>`);
  await page.goto(`file:///${file.replaceAll("\\", "/")}`);
  await page.waitForLoadState("networkidle").catch(() => {});
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(here, "shots", `${name}-${scheme}.png`), fullPage: true });
}
await browser.close();

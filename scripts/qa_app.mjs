import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const outputDir = path.resolve("./ai-intern-radar/tmp/app_qa");
await fs.mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });

async function check(viewport, name) {
  const page = await browser.newPage({ viewportSize: viewport, deviceScaleFactor: 1 });
  const errors = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://127.0.0.1:8501", { waitUntil: "networkidle", timeout: 60000 });
  await page.getByRole("heading", { name: "AI 实习雷达", exact: true }).waitFor({ timeout: 30000 });
  await page.screenshot({ path: path.join(outputDir, `${name}_dashboard.png`), fullPage: true });
  const bodyWidth = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
  for (const nav of ["岗位库", "外部盲测", "JD 诊断"]) {
    await page.getByText(nav, { exact: true }).first().click();
    await page.waitForTimeout(900);
    await page.getByRole("heading", { name: nav, exact: true }).waitFor({ timeout: 15000 });
  }
  await page.screenshot({ path: path.join(outputDir, `${name}_diagnosis.png`), fullPage: true });
  const visibleText = await page.locator("body").innerText();
  await page.close();
  return {
    viewport,
    horizontalOverflow: bodyWidth.scroll > bodyWidth.client + 2,
    streamlitException: /Traceback|Exception|Error running app/.test(visibleText),
    consoleErrors: errors.filter((item) => !item.includes("favicon")),
  };
}

const results = [];
results.push(await check({ width: 1440, height: 960 }, "desktop"));
results.push(await check({ width: 390, height: 844 }, "mobile"));
await browser.close();
console.log(JSON.stringify(results, null, 2));

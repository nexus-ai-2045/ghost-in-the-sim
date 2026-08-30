"use strict";

const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const url = process.argv[2] || "http://127.0.0.1:8045/";
const output = path.resolve(
  process.argv[3] || "artifacts/submission/ghost-in-the-sim-demo.webm"
);
fs.mkdirSync(path.dirname(output), { recursive: true });

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    recordVideo: { dir: path.dirname(output), size: { width: 1280, height: 720 } },
    colorScheme: "dark",
  });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      consoleErrors.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));

  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator("#operation-console").waitFor({ state: "visible" });
  await page.locator("#experience").scrollIntoViewIfNeeded();
  await wait(1400);

  await page.getByRole("button", { name: /病院を守る/ }).click();
  await wait(900);
  await page.getByRole("button", { name: /真壁と共同確認する/ }).click();
  await wait(1100);
  await page.getByRole("button", { name: "作戦開始" }).click();
  await wait(1200);

  for (let index = 0; index < 7; index += 1) {
    await page.getByRole("button", { name: "次のターン" }).click();
    await wait(650);
  }
  await page.getByText("真壁「待て。この失効は戻せない」").waitFor();
  await wait(1200);
  await page.getByRole("button", { name: /保留する/ }).click();
  await wait(1100);

  for (let index = 0; index < 4; index += 1) {
    await page.getByRole("button", { name: "次のターン" }).click();
    await wait(650);
  }
  await page.getByRole("heading", { name: "作戦完了" }).waitFor();
  await page.locator("#operation-result").scrollIntoViewIfNeeded();
  await wait(2200);

  const video = page.video();
  await context.close();
  const recorded = await video.path();
  await browser.close();
  if (consoleErrors.length) {
    throw new Error(`browser console is not clean:\n${consoleErrors.join("\n")}`);
  }
  fs.rmSync(output, { force: true });
  fs.renameSync(recorded, output);
  process.stdout.write(`${JSON.stringify({ output, url, route: "hospital-plural-hold", turns: 12 })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});


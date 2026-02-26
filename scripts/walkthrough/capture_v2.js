#!/usr/bin/env node
/**
 * Istari UI Walkthrough — Puppeteer screenshot capture (v2)
 *
 * Captures the Istari UI walkthrough with a simulated URL bar overlay.
 * Connects to an existing Chrome instance already logged into Istari.
 *
 * This version navigates existing state (doesn't upload a new file)
 * and captures each step with the URL visible.
 *
 * Prerequisites:
 *   Chrome running with --remote-debugging-port=9222
 *   Already logged into https://demo.istari.app
 *
 * Usage:
 *   node capture_v2.js
 */

const puppeteer = require("puppeteer");
const path = require("path");
const fs = require("fs");

const ISTARI_URL = process.env.ISTARI_URL || "https://demo.istari.app";
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/walkthrough/images");
const CHROME_DEBUG_URL = "http://127.0.0.1:9222";

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

let stepNumber = 0;
const screenshots = [];

async function injectUrlBar(page) {
  const currentUrl = page.url();
  await page.evaluate((url) => {
    // Remove existing overlay if any
    const old = document.getElementById("__url_bar_overlay__");
    if (old) old.remove();

    const bar = document.createElement("div");
    bar.id = "__url_bar_overlay__";
    bar.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; z-index: 999999;
      height: 40px; background: #dee1e6; display: flex; align-items: center;
      padding: 0 12px; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 13px; border-bottom: 1px solid #c4c7cc;
    `;
    const nav = document.createElement("div");
    nav.style.cssText = "display: flex; gap: 8px; margin-right: 12px; color: #5f6368;";
    nav.innerHTML = `
      <span style="font-size: 16px; opacity: 0.4;">&#x276E;</span>
      <span style="font-size: 16px; opacity: 0.4;">&#x276F;</span>
      <span style="font-size: 16px; opacity: 0.6;">&#x21BB;</span>
    `;
    bar.appendChild(nav);
    const urlBox = document.createElement("div");
    urlBox.style.cssText = `
      flex: 1; background: #fff; border-radius: 20px; padding: 6px 14px;
      font-size: 13px; color: #202124; display: flex; align-items: center;
      border: 1px solid #dfe1e5;
    `;
    urlBox.innerHTML =
      '<span style="font-size: 12px; margin-right: 4px;">🔒</span>' +
      "<span>" + url.replace("https://", "") + "</span>";
    bar.appendChild(urlBox);
    document.body.appendChild(bar);
    document.body.style.paddingTop = "40px";
  }, currentUrl);
  await sleep(300);
}

async function removeUrlBar(page) {
  await page.evaluate(() => {
    const bar = document.getElementById("__url_bar_overlay__");
    if (bar) bar.remove();
    document.body.style.paddingTop = "";
  });
}

async function screenshot(page, name, description) {
  stepNumber++;
  const filename = `${String(stepNumber).padStart(2, "0")}_${name}.png`;
  const filepath = path.join(SCREENSHOT_DIR, filename);
  const currentUrl = page.url();

  await injectUrlBar(page);
  await page.screenshot({ path: filepath, fullPage: false });
  await removeUrlBar(page);

  screenshots.push({ filename, description, step: stepNumber, url: currentUrl });
  console.log(`  [${stepNumber}] ${description}`);
  console.log(`      -> ${filename}  (${currentUrl})`);
  return filename;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  console.log("=== Istari UI Walkthrough Capture v2 ===\n");

  const browser = await puppeteer.connect({
    browserURL: CHROME_DEBUG_URL,
    defaultViewport: null,
  });
  console.log("Connected to Chrome.\n");

  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes("demo.istari.app"));

  if (!page) {
    console.log("No Istari tab found. Opening one...");
    page = await browser.newPage();
    await page.goto(ISTARI_URL, { waitUntil: "networkidle0", timeout: 30000 });
    await sleep(3000);
  } else {
    console.log(`Found Istari tab: ${page.url()}\n`);
  }

  try {
    // ── Step 1: Systems page ──────────────────────────────────
    console.log("[Step 1] Systems page");
    await page.goto(`${ISTARI_URL}/systems`, { waitUntil: "networkidle0", timeout: 15000 });
    await sleep(3000);
    await screenshot(page, "systems", "Systems page — starting point");

    // ── Step 2: Files page ────────────────────────────────────
    console.log("\n[Step 2] Files page");
    await page.goto(`${ISTARI_URL}/files`, { waitUntil: "networkidle0", timeout: 15000 });
    await sleep(3000);
    await screenshot(page, "files_page", "Files page — list of uploaded files");

    // ── Step 3: Click 'Add files' to show dialog ──────────────
    console.log("\n[Step 3] Add files dialog");
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll("button")).find(
        (b) => b.textContent?.trim() === "Add files"
      );
      if (btn) btn.click();
    });
    await sleep(2000);
    await screenshot(page, "add_files_dialog", "Add Files dialog — Upload or Connect");

    // Close dialog
    await page.keyboard.press("Escape");
    await sleep(1000);

    // ── Step 4: Navigate to research_task file ────────────────
    console.log("\n[Step 4] Find and open research_task file");

    // Try to find research_task in the file list by scrolling pages
    let foundFile = false;
    for (let pageNum = 1; pageNum <= 10; pageNum++) {
      const found = await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll("span, div, a"));
        const target = items.find(
          (el) =>
            el.textContent?.trim() === "research_task" ||
            el.textContent?.trim() === "research_task.json"
        );
        if (target) {
          const clickable = target.closest("a") || target.closest("[role='button']") || target;
          clickable.click();
          return target.textContent?.trim();
        }
        return null;
      });

      if (found) {
        console.log(`  Found "${found}" on page ${pageNum}`);
        foundFile = true;
        break;
      }

      // Go to next page
      if (pageNum < 10) {
        const hasNext = await page.evaluate(() => {
          const nextBtns = Array.from(document.querySelectorAll("button"));
          const next = nextBtns.find(
            (b) => b.getAttribute("aria-label")?.includes("next") || b.textContent?.trim() === ">"
          );
          // Also try clicking the ">" pagination button
          const pagBtns = Array.from(document.querySelectorAll("[aria-label*='next'], [aria-label*='Next']"));
          const btn = pagBtns[0] || next;
          if (btn && !btn.disabled) {
            btn.click();
            return true;
          }
          return false;
        });
        if (!hasNext) break;
        await sleep(2000);
      }
    }

    if (!foundFile) {
      // Fallback: try clicking a known .json file like Deep_Thoughts_task
      console.log("  research_task not found in pages, trying Deep_Thoughts_task...");
      await page.goto(`${ISTARI_URL}/files`, { waitUntil: "networkidle0", timeout: 15000 });
      await sleep(2000);
      await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll("span, div, a"));
        const target = items.find((el) => el.textContent?.includes("Deep_Thoughts_task"));
        if (target) {
          const clickable = target.closest("a") || target;
          clickable.click();
        }
      });
    }

    await sleep(3000);
    await screenshot(page, "file_detail", "File detail — task JSON with Create job button");

    // ── Step 5: Click 'Create job' ────────────────────────────
    console.log("\n[Step 5] Create job dialog");
    const clickedCreateJob = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find((b) => b.textContent?.trim().toLowerCase() === "create job");
      if (btn) { btn.click(); return true; }
      return false;
    });
    if (clickedCreateJob) {
      await sleep(2000);
      await screenshot(page, "create_job_dialog", "Create Job dialog — select a tool/function");

      // ── Step 6: Open function dropdown ────────────────────────
      console.log("\n[Step 6] Function dropdown");
      await page.evaluate(() => {
        const btn = Array.from(document.querySelectorAll("button")).find(
          (b) => b.textContent?.trim().toLowerCase().includes("select a tool")
        );
        if (btn) btn.click();
      });
      await sleep(2000);
      await screenshot(page, "function_dropdown", "Function dropdown — available tools");

      // ── Step 7: Select VK Executor ──────────────────────────
      console.log("\n[Step 7] Select VK Executor");
      await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll("*"));
        const vkItem = items.find(
          (el) =>
            (el.textContent?.toLowerCase().includes("vk_executor") ||
             el.textContent?.toLowerCase().includes("vibe kanban")) &&
            (el.tagName === "LI" ||
             el.getAttribute("role") === "option" ||
             el.getAttribute("role") === "menuitem" ||
             el.classList?.contains("option") ||
             el.closest("[role='listbox']"))
        );
        if (vkItem) vkItem.click();
      });
      await sleep(2000);
      await screenshot(page, "function_selected", "VK Executor selected");

      // Close dialog without executing (don't create a real job)
      await page.keyboard.press("Escape");
      await sleep(1000);
    } else {
      console.log("  WARNING: 'Create job' button not found");
    }

    // ── Step 8: Jobs page ─────────────────────────────────────
    console.log("\n[Step 8] Jobs page");
    await page.goto(`${ISTARI_URL}/jobs`, { waitUntil: "networkidle0", timeout: 15000 });
    await sleep(3000);
    await screenshot(page, "jobs_list", "Jobs page — completed VK Executor jobs");

    // ── Step 9: Click a completed VK job for detail ───────────
    console.log("\n[Step 9] Job detail");
    const clickedJob = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll("tr"));
      for (const row of rows) {
        if (row.textContent?.includes("vk_executor") && row.textContent?.includes("Completed")) {
          const link = row.querySelector("a");
          if (link) { link.click(); return true; }
          row.click();
          return true;
        }
      }
      return false;
    });
    if (clickedJob) {
      await sleep(3000);
      await screenshot(page, "job_detail", "Job detail — execution results");
    }

    // Return to a neutral page
    await page.goto(`${ISTARI_URL}/files`, { waitUntil: "networkidle0", timeout: 15000 });

  } catch (err) {
    console.error(`\nERROR: ${err.message}`);
    try {
      await screenshot(page, "error", "Error state");
    } catch {}
  } finally {
    const manifestPath = path.join(SCREENSHOT_DIR, "manifest.json");
    fs.writeFileSync(manifestPath, JSON.stringify(screenshots, null, 2));
    console.log(`\n=== Done — captured ${screenshots.length} screenshots ===`);
    console.log(`Output: ${SCREENSHOT_DIR}`);
    browser.disconnect();
  }
}

main().catch(console.error);

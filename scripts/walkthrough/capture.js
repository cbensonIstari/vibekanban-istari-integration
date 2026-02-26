#!/usr/bin/env node
/**
 * Istari UI Walkthrough — Puppeteer screenshot capture
 *
 * Connects to an existing Chrome instance (already logged into Istari)
 * and walks through uploading a task file and creating a job.
 *
 * Prerequisites:
 *   Chrome running with --remote-debugging-port=9222
 *   Already logged into https://demo.istari.app
 *
 * Usage:
 *   node capture.js
 */

const puppeteer = require("puppeteer");
const path = require("path");
const fs = require("fs");

const ISTARI_URL = process.env.ISTARI_URL || "https://demo.istari.app";
const TASK_FILE = path.resolve(
  __dirname,
  process.env.TASK_FILE_PATH || "../../examples/inputs/research_task.json"
);
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/walkthrough/images");
const CHROME_DEBUG_URL = "http://127.0.0.1:9222";

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

let stepNumber = 0;
const screenshots = [];

async function screenshot(page, name, description) {
  stepNumber++;
  const filename = `${String(stepNumber).padStart(2, "0")}_${name}.png`;
  const filepath = path.join(SCREENSHOT_DIR, filename);
  await page.screenshot({ path: filepath, fullPage: false });
  screenshots.push({ filename, description, step: stepNumber });
  console.log(`  [screenshot ${stepNumber}] ${description} -> ${filename}`);
  return filename;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  console.log("=== Istari UI Walkthrough Capture ===\n");
  console.log(`URL:        ${ISTARI_URL}`);
  console.log(`Task file:  ${TASK_FILE}`);
  console.log(`Output:     ${SCREENSHOT_DIR}\n`);

  // Connect to existing Chrome
  const browser = await puppeteer.connect({
    browserURL: CHROME_DEBUG_URL,
    defaultViewport: null,
  });
  console.log("Connected to Chrome.\n");

  // Find the existing Istari tab
  const pages = await browser.pages();
  let page = pages.find((p) => p.url().includes("demo.istari.app"));

  if (!page) {
    console.log("No Istari tab found. Opening one...");
    page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto(ISTARI_URL, { waitUntil: "networkidle0", timeout: 30000 });
    await sleep(3000);
  } else {
    console.log(`Found Istari tab: ${page.url()}`);
  }

  try {
    // ── Step 1: Dashboard / Systems ─────────────────────────────
    console.log("\n[Step 1] Systems page — starting point");
    await page.goto(`${ISTARI_URL}/systems`, {
      waitUntil: "networkidle0",
      timeout: 15000,
    });
    await sleep(2000);
    await screenshot(page, "systems", "Systems page — starting point");

    // ── Step 2: Navigate to Files ───────────────────────────────
    console.log("\n[Step 2] Navigate to Files page");
    await page.evaluate(() => {
      const link = Array.from(document.querySelectorAll("a")).find(
        (a) => a.textContent?.trim() === "Files"
      );
      if (link) link.click();
    });
    await sleep(3000);
    await screenshot(page, "files_page", "Files page — list of all uploaded files");

    // ── Step 3: Click 'Add files' ───────────────────────────────
    console.log("\n[Step 3] Open 'Add files' dialog");
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll("button")).find(
        (b) => b.textContent?.trim() === "Add files"
      );
      if (btn) btn.click();
    });
    await sleep(2000);
    await screenshot(page, "add_files_dialog", "Add files dialog — Upload tab");

    // ── Step 4: Upload the task file ────────────────────────────
    console.log("\n[Step 4] Upload task file: " + path.basename(TASK_FILE));

    // Click "Choose Files" to make the file input active, then upload
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
      await fileInput.uploadFile(TASK_FILE);
      await sleep(3000);
      await screenshot(page, "file_selected", "Task file selected — research_task.json");

      // Look for an Upload/Submit/OK button to confirm
      const uploaded = await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        // Look for a submit-type button in the dialog context
        const btn = btns.find(
          (b) =>
            b.textContent?.trim().toLowerCase() === "upload" ||
            b.textContent?.trim().toLowerCase() === "submit"
        );
        // Don't click the top-level "Add files" button again
        if (btn && !btn.textContent?.trim().includes("Add files")) {
          btn.click();
          return btn.textContent?.trim();
        }
        return null;
      });
      if (uploaded) {
        console.log(`  Clicked: "${uploaded}"`);
        await sleep(4000);
      }
    } else {
      console.log("  WARNING: No file input found");
    }

    // Close any remaining dialog
    await page.keyboard.press("Escape");
    await sleep(2000);
    await screenshot(page, "file_uploaded", "File uploaded to Istari");

    // ── Step 5: Click on the uploaded file ──────────────────────
    console.log("\n[Step 5] Open the uploaded file detail");

    // Reload the files page so our new file appears
    await page.goto(`${ISTARI_URL}/files`, { waitUntil: "networkidle0", timeout: 15000 });
    await sleep(2000);

    // Look for research_task specifically in the sidebar
    const clickedFile = await page.evaluate(() => {
      // Find all items in the file list sidebar
      const allEls = Array.from(document.querySelectorAll("a, span, div, li"));
      // Look for our file by name
      let target = allEls.find((el) =>
        el.textContent?.trim() === "research_task" ||
        el.textContent?.trim() === "research_task.json" ||
        el.textContent?.includes("research_task")
      );
      if (target) {
        // Click the nearest clickable ancestor if needed
        const clickable = target.closest("a") || target.closest("[role='button']") || target;
        clickable.click();
        return target.textContent?.trim();
      }
      // Fallback: click "Deep_Thoughts_task" which is a .json file
      target = allEls.find((el) => el.textContent?.includes("Deep_Thoughts_task"));
      if (target) {
        const clickable = target.closest("a") || target;
        clickable.click();
        return target.textContent?.trim();
      }
      return null;
    });

    if (clickedFile) {
      console.log(`  Opened: "${clickedFile}"`);
    }
    await sleep(3000);
    await screenshot(page, "file_detail", "File detail page — with Create Job button");

    // ── Step 6: Click 'Create job' ──────────────────────────────
    console.log("\n[Step 6] Click 'Create job'");

    const clickedCreateJob = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find(
        (b) => b.textContent?.trim().toLowerCase() === "create job"
      );
      if (btn) {
        btn.click();
        return true;
      }
      return false;
    });

    if (clickedCreateJob) {
      console.log("  Clicked 'Create job'");
    } else {
      console.log("  WARNING: 'Create job' button not found");
    }
    await sleep(3000);
    await screenshot(page, "create_job_dialog", "Create job dialog — select function");

    // ── Step 7: Select the VK Executor function ─────────────────
    console.log("\n[Step 7] Select VK Executor function");

    // Examine the dialog to find the function selector
    const dialogState = await page.evaluate(() => {
      const text = document.body?.innerText?.substring(0, 3000);
      const selects = Array.from(document.querySelectorAll("select"));
      const selectInfo = selects.map((s) => ({
        options: Array.from(s.options).map((o) => o.text),
      }));
      const dropdowns = Array.from(
        document.querySelectorAll(
          '[role="listbox"], [role="combobox"], [class*="select"], [class*="dropdown"]'
        )
      );
      const buttons = Array.from(document.querySelectorAll("button"))
        .map((b) => b.textContent?.trim())
        .filter((t) => t && t.length < 60);
      return { selectInfo, dropdownCount: dropdowns.length, buttons, text: text?.substring(0, 1000) };
    });

    console.log("  Selects:", JSON.stringify(dialogState.selectInfo));
    console.log("  Dropdowns:", dialogState.dropdownCount);
    console.log(
      "  Buttons:",
      dialogState.buttons.filter((b) => b.length > 1).join(" | ")
    );

    // First, click the "Select a tool/function" dropdown trigger
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll("button")).find(
        (b) => b.textContent?.trim().toLowerCase().includes("select a tool")
      );
      if (btn) btn.click();
    });
    await sleep(2000);
    await screenshot(page, "function_dropdown_open", "Function dropdown — showing available tools");

    // Now find and click the Engineering Tools / VK Executor option
    const selectedFn = await page.evaluate(() => {
      // Look for any element containing "engineering" or "vibe" in the dropdown
      const items = Array.from(document.querySelectorAll("*"));
      const vkItem = items.find(
        (el) =>
          (el.textContent?.toLowerCase().includes("engineering_tools") ||
           el.textContent?.toLowerCase().includes("vibe kanban") ||
           el.textContent?.toLowerCase().includes("vk_executor")) &&
          (el.tagName === "LI" ||
           el.getAttribute("role") === "option" ||
           el.getAttribute("role") === "menuitem" ||
           el.classList?.contains("option") ||
           el.closest("[role='listbox']"))
      );
      if (vkItem) {
        vkItem.click();
        return vkItem.textContent?.trim();
      }
      return null;
    });

    if (selectedFn) {
      console.log(`  Selected: ${selectedFn}`);
      await sleep(2000);
    } else {
      console.log("  VK Executor not in dropdown — may need to click through");
      // Try clicking text that contains "engineering" or "vk_executor"
      await page.evaluate(() => {
        const all = Array.from(document.querySelectorAll("div, span, li, a, button"));
        for (const el of all) {
          const text = el.textContent?.toLowerCase() || "";
          if (
            (text.includes("engineering") || text.includes("vk_executor")) &&
            el.offsetParent !== null &&
            el.getBoundingClientRect().height > 0
          ) {
            el.click();
            break;
          }
        }
      });
      await sleep(2000);
    }
    await screenshot(
      page,
      "function_selected",
      "Function selected — VK Executor"
    );

    // ── Step 8: Submit the job ──────────────────────────────────
    console.log("\n[Step 8] Submit the job");

    const submitted = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find(
        (b) =>
          b.textContent?.trim().toLowerCase() === "execute function" ||
          b.textContent?.trim().toLowerCase() === "create" ||
          b.textContent?.trim().toLowerCase() === "create job" ||
          b.textContent?.trim().toLowerCase() === "submit" ||
          b.textContent?.trim().toLowerCase() === "run"
      );
      if (btn && !btn.disabled) {
        btn.click();
        return btn.textContent?.trim();
      }
      return null;
    });

    if (submitted) {
      console.log(`  Submitted: "${submitted}"`);
    }
    await sleep(5000);
    await screenshot(page, "job_created", "Job created — redirected to job view");

    // ── Step 9: Navigate to Jobs page ───────────────────────────
    console.log("\n[Step 9] Jobs page — monitor progress");
    await page.goto(`${ISTARI_URL}/jobs`, {
      waitUntil: "networkidle0",
      timeout: 15000,
    });
    await sleep(3000);
    await screenshot(page, "jobs_list", "Jobs page — job appears in list");

    // ── Step 10: Wait for job progress ──────────────────────────
    console.log("\n[Step 10] Waiting 15s for agent to claim...");
    await sleep(15000);
    await page.reload({ waitUntil: "networkidle0" });
    await sleep(2000);
    await screenshot(page, "job_progress", "Job progress — agent processing");

    // ── Step 11: Wait for completion ────────────────────────────
    console.log("\n[Step 11] Waiting 30s for completion...");
    await sleep(30000);
    await page.reload({ waitUntil: "networkidle0" });
    await sleep(2000);
    await screenshot(page, "job_complete", "Job completed");

    // ── Step 12: Click on the job to see detail ─────────────────
    console.log("\n[Step 12] Open job detail for artifacts");

    // Click the most recent VK executor job
    const clickedJob = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button, a, tr"));
      const job = btns.find(
        (b) =>
          b.textContent?.includes("vk_executor") &&
          (b.tagName === "TR" || b.tagName === "A")
      );
      if (job) {
        const link = job.querySelector("a") || job;
        link.click();
        return true;
      }
      // Fallback: click first job row link
      const rows = Array.from(document.querySelectorAll("tr"));
      for (const row of rows) {
        const link = row.querySelector("a");
        if (link && link.href?.includes("/jobs/")) {
          link.click();
          return true;
        }
      }
      return false;
    });

    if (clickedJob) {
      await sleep(3000);
      await screenshot(page, "job_detail", "Job detail — execution results and artifacts");
    }

    // Navigate back to systems
    await page.goto(`${ISTARI_URL}/systems`, {
      waitUntil: "networkidle0",
      timeout: 15000,
    });

  } catch (err) {
    console.error(`\nERROR: ${err.message}`);
    try {
      await screenshot(page, "error", "Error state");
    } catch {}
  } finally {
    // Write screenshot manifest
    const manifestPath = path.join(SCREENSHOT_DIR, "manifest.json");
    fs.writeFileSync(manifestPath, JSON.stringify(screenshots, null, 2));

    console.log(`\n=== Done — captured ${screenshots.length} screenshots ===`);
    console.log(`Output: ${SCREENSHOT_DIR}`);

    // Don't close the tab or browser — just disconnect
    browser.disconnect();
  }
}

main().catch(console.error);

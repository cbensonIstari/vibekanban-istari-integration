# Istari UI Walkthrough — Vibe Kanban Executor

This walkthrough shows how to create a task for the Vibe Kanban Executor module through the Istari UI. By the end, you'll have uploaded a task file, created a job, and seen the agent execute it.

> **Prerequisites:** An Istari account with the VK Executor module installed on your agent. See the main [README](../../README.md) for setup instructions.

---

## Step 1: Open the Istari Dashboard

Navigate to your Istari instance (e.g. [`https://demo.istari.app`](https://demo.istari.app)). The left sidebar has three main sections: **Systems**, **Files**, and **Jobs**.

> URL: `https://demo.istari.app/systems`

![Systems page — starting point](images/01_systems.png)

---

## Step 2: Navigate to Files

Click **Files** in the left sidebar. This shows all uploaded files in your workspace — SysML models, JSON input files, and other artifacts. The **+ Add files** button in the top-right corner is how you upload new files.

> URL: `https://demo.istari.app/files`

![Files page — list of uploaded files](images/02_files_page.png)

---

## Step 3: Click "Add files"

Click the **+ Add files** button. A dialog appears with two tabs:

- **Upload** — Upload files from your computer
- **Connect** — Connect files from external sources

Click **+ Choose Files** to select your task JSON from your local machine.

![Add Files dialog — Upload tab](images/03_add_files_dialog.png)

<details>
<summary>Example task file contents</summary>

```json
{
  "project_id": "cb527bb0-2050-4773-b09a-ebe16e692209",
  "task": "Go learn more about CD/DC at https://cdfam.com/cd-dc-26/ and explain how it relates to Istari",
  "agent": "claude-code",
  "repo_id": "965aedf6-56d8-4178-a816-02edbceb1292"
}
```

See [Task File Format](../../README.md#4-task-file-format) for all available fields.
</details>

---

## Step 4: View the Uploaded File

After uploading, click on your file in the Files list. Istari assigns a deep link to every file:

> URL: `https://demo.istari.app/files/{file_id}/{version_id}`

The right panel shows:
- File metadata (created date, author, size, MIME type)
- Description
- JSON content preview (expandable)
- **Activity** section showing past job executions
- **+ Create job** button at the bottom

![File detail page — task JSON with deep link URL](images/04_file_detail.png)

---

## Step 5: Create a Job

Click the **+ Create job** button at the bottom of the file detail panel. The **Create Job** dialog appears with:

- **Tool/Function Combination** — dropdown to select which module processes this file
- **Advanced options** — optional configuration
- **Execute Function** — submit button

> URL remains the file deep link: `https://demo.istari.app/files/{file_id}/{version_id}`

![Create Job dialog — select a tool/function](images/05_create_job_dialog.png)

---

## Step 6: Select the VK Executor Function

Click the **Select a tool/function** dropdown to see all available tools installed on your agent. You'll see modules like:

- **Vibe Kanban** — 1 function (`@vibekanban:vk_executor`)
- **ntopci** — 2 functions
- **textract** — 2 functions

Select **Vibe Kanban**, then click **Execute Function** to submit the job.

![Function dropdown — showing Vibe Kanban and other available tools](images/06_function_dropdown.png)

---

## Step 7: Monitor the Job

Navigate to **Jobs** in the left sidebar to see all jobs. The jobs list shows:

| Column | Description |
|--------|-------------|
| **Tool / Function** | The module that processed the job (e.g. `engineering_tools / @vibekanban:vk_executor`) |
| **Job ID** | Short unique identifier (clickable deep link) |
| **Started On** | Timestamp |
| **Status** | Current state: Pending, Running, Completed, or Failed |

> URL: `https://demo.istari.app/jobs`

You can see the VK Executor jobs completing successfully alongside other module jobs (like SysGit's `extract_sysmlv2`).

![Jobs page — showing completed VK Executor jobs](images/07_jobs_list.png)

---

## Deep Links

Every resource in Istari has a deep link you can bookmark or share:

| Resource | URL Pattern |
|----------|-------------|
| Systems | `https://demo.istari.app/systems` |
| Files list | `https://demo.istari.app/files` |
| File detail | `https://demo.istari.app/files/{file_id}/{version_id}` |
| Jobs list | `https://demo.istari.app/jobs` |

---

## What Happens Behind the Scenes

When the agent executes the VK Executor module, it:

1. **Reads** the uploaded task JSON file
2. **Connects** to the Vibe Kanban MCP server
3. **Creates an issue** in your VK project with the task description
4. **Starts an AI workspace session** linked to the issue (if `repo_id` is provided)
5. **Generates** an execution report (JSON + HTML) as job artifacts

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Istari UI  │─────▶│ Istari Agent │─────▶│ VK Executor  │─────▶│ Vibe Kanban  │
│ Upload task │      │ Claims job   │      │ entrypoint.py│      │  MCP Server  │
│ Create job  │      │ Runs module  │      │              │      │              │
└─────────────┘      └──────────────┘      └──────────────┘      └──────┬───────┘
                                                                        │
                                                                        ▼
                                                                ┌──────────────┐
                                                                │  Issue + AI  │
                                                                │  Workspace   │
                                                                │  Session     │
                                                                └──────────────┘
```

The AI agent (Claude Code, Codex, Gemini, etc.) then picks up the workspace and begins working on the task autonomously.

---

## Job Lifecycle

```
PENDING → CLAIMED → VALIDATING → RUNNING → UPLOADING → COMPLETED
                                    │
                                    ├── Creates VK issue
                                    └── Starts workspace session
```

| Status | What's happening |
|--------|-----------------|
| **Pending** | Job created, waiting for an agent to claim it |
| **Running** | Agent is executing the VK Executor module |
| **Completed** | Task file processed, issue created, workspace started |
| **Failed** | Something went wrong — check agent logs |

---

## Alternative: Create Jobs via SDK

You can also create jobs programmatically using the Istari Python SDK:

```python
from istari_digital_client.client import Client

c = Client()

# Upload the task file
model = c.add_model("research_task.json", description="CD/DC research task")

# Create a job — the model IS the input
job = c.add_job(model.id, "@vibekanban:vk_executor")

print(f"Job ID: {job.id}")
```

See the main [README](../../README.md#9-end-to-end-usage) for more details.

---

## Screenshots

These screenshots were captured automatically using a [Puppeteer script](../../scripts/walkthrough/capture.js) connected to a live Istari instance. Each screenshot includes a simulated URL bar showing the current page URL. To reproduce:

```bash
# 1. Launch Chrome with remote debugging
open -a "Google Chrome" --args --remote-debugging-port=9222

# 2. Log into your Istari instance in the browser

# 3. Run the capture script
cd scripts/walkthrough
npm install
node capture_v2.js
```

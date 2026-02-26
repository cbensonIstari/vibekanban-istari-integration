# Vibe Kanban Executor — Istari Integration Module

## Create issues and start AI workspace sessions from the Istari platform

**Module Key:** `@vibekanban:vk_executor` | **Version:** 1.0.0 | **Function:** `@vibekanban:vk_executor`

---

## Table of Contents

1. [Overview](#1-overview)
2. [How It Works](#2-how-it-works)
3. [Prerequisites](#3-prerequisites)
4. [Task File Format](#4-task-file-format)
5. [Module Structure](#5-module-structure)
6. [Building the Module](#6-building-the-module)
7. [Testing](#7-testing)
8. [Deployment](#8-deployment)
9. [End-to-End Usage](#9-end-to-end-usage)
10. [Troubleshooting](#10-troubleshooting)
11. [Lessons Learned](#11-lessons-learned)
12. [Links](#12-links)

---

## 1. Overview

This module integrates [Vibe Kanban](https://vibekanban.com) with the [Istari Digital](https://istari.app) platform. When a user uploads a task file through the Istari UI and creates a job, this module:

1. **Creates an issue** in Vibe Kanban with the task description
2. **Starts an AI workspace session** linked to the issue, using the specified AI agent (Claude Code, Codex, Gemini, etc.)

The AI agent then picks up the workspace and begins working on the task autonomously.

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

---

## 2. How It Works

The Istari agent uses a **file-based contract** to communicate with modules:

```
python3 entrypoint.py <input_file> <output_file> <temp_dir>
```

| Argument | Description |
|---|---|
| `input_file` | JSON written by the agent with the uploaded model path |
| `output_file` | JSON the module writes listing output artifacts |
| `temp_dir` | Scratch directory for intermediate files |

**Input file** (written by the agent):
```json
{
  "task_file": {
    "type": "user_model",
    "value": "/path/to/uploaded/task.json"
  }
}
```

**Output file** (written by the module):
```json
[
  {"name": "execution_report", "type": "file", "path": "/tmp/report.json"},
  {"name": "execution_report_html", "type": "file", "path": "/tmp/report.html"}
]
```

The module communicates with Vibe Kanban through its **MCP server** (`npx vibe-kanban@latest --mcp`), sending JSON-RPC messages over stdio to create issues and start workspace sessions.

---

## 3. Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | >= 3.9 | Module runtime |
| Node.js | >= 18 | Vibe Kanban MCP server (`npx`) |
| Istari Agent | >= 11.0.0 | Job execution |
| Istari CLI (`stari`) | >= 0.21 | Publishing modules |
| pytest | any | Running tests |

**Credentials needed:**

| Credential | Where to get it |
|---|---|
| Istari CLI token | Istari UI > Settings > API Tokens |
| Istari Agent token | Istari UI > Admin > Agents |
| Vibe Kanban project ID | VK UI > Project Settings |
| Vibe Kanban repo ID | VK UI > Repo Settings (optional, needed for workspace sessions) |

---

## 4. Task File Format

The task file uploaded through the Istari UI is a simple JSON:

```json
{
  "project_id": "cb527bb0-2050-4773-b09a-ebe16e692209",
  "task": "Implement user authentication for the API",
  "agent": "claude-code",
  "repo_id": "965aedf6-56d8-4178-a816-02edbceb1292"
}
```

| Field | Required | Description |
|---|---|---|
| `project_id` | Yes | Vibe Kanban project UUID |
| `task` | Yes | What the AI agent should do |
| `agent` | No | AI agent to use (default: `claude-code`) |
| `repo_id` | No | VK repo UUID — needed to start a workspace session |
| `base_branch` | No | Branch to work from (default: `main`) |
| `dry_run` | No | Set to `"true"` to skip execution |

**Supported agents:** `claude-code`, `codex`, `gemini`, `amp`, `copilot`, `cursor_agent`, `qwen-code`, `droid`, `opencode`

**Minimal task file** (creates issue only, no workspace):
```json
{
  "project_id": "your-project-uuid",
  "task": "Fix the login page CSS on mobile",
  "agent": "claude-code"
}
```

---

## 5. Module Structure

```
vibekanban-istari-integration/
├── README.md
├── module_manifest.json            # Istari module definition
├── function_schemas/
│   └── vk_executor.json            # Input/output schema (user_model + artifacts)
├── src/
│   ├── entrypoint.py               # Istari agent entrypoint
│   └── vk_executor.py              # Core logic: MCP client, plan, execute, report
├── tests/
│   └── test_vk_executor.py         # 40 unit tests (mocked MCP client)
├── test_files/
│   └── vk_executor/
│       └── input.json              # Test input in Istari agent format
├── examples/
│   ├── inputs/
│   │   ├── sample_task.json        # Full task with repo_id
│   │   └── minimal_task.json       # Minimal task (issue only)
│   └── outputs/
│       └── sample_report.json      # Example execution report
└── scripts/
    ├── test.sh                     # Run the test suite
    ├── install.sh                  # Install module into local agent
    └── publish.sh                  # Publish to Istari registry + install
```

---

## 6. Building the Module

No build step is needed — the module is pure Python with no compiled dependencies.

**Verify the module manifest:**
```bash
stari module lint module_manifest.json
```

**Package for distribution:**
```bash
zip -r vibekanban-vk-executor.zip \
  src/ function_schemas/ module_manifest.json \
  -x "__pycache__/*"
```

---

## 7. Testing

**Run the full test suite:**
```bash
scripts/test.sh
# or directly:
python3 -m pytest tests/ -v
```

The tests use a mocked `VKMcpClient` — no running MCP server required. They cover:

- Manifest loading and validation
- Execution planning (tasks, subtasks, workspaces)
- Plan execution with success and error paths
- Report generation (JSON and HTML)
- I/O contract (input unwrapping, output writing)
- End-to-end pipeline

**Local dry run** (no VK connection needed):
```bash
cd src/
python3 entrypoint.py ../examples/inputs/sample_task.json /tmp/output.json /tmp
```

> Note: This will attempt to connect to the VK MCP server. For a true dry run, add `"dry_run": "true"` to the task file.

---

## 8. Deployment

### 8.1 Publish to Istari Registry

```bash
stari client publish module_manifest.json
```

This uploads the module and registers the function version. The agent token's user must have `execute` permission on the function version (granted automatically for the publishing user's organization).

### 8.2 Install Locally for the Agent

```bash
scripts/install.sh
```

Or manually:
```bash
# macOS
DEST="$HOME/Library/Application Support/istari_agent/istari_modules/vibekanban"
mkdir -p "$DEST"
cp -r src/ function_schemas/ module_manifest.json "$DEST/"
```

### 8.3 Restart the Agent

```bash
# macOS
pkill -f istari_agent
open /Applications/istari_agent/istari_agent_*.app
```

### 8.4 Verify the Agent Sees the Module

Check the agent logs for:
```
Registered function: @vibekanban:vk_executor v1.0.0
```

---

## 9. End-to-End Usage

### From the Istari UI

1. Navigate to your project in the Istari UI
2. Upload a task JSON file (see [Task File Format](#4-task-file-format))
3. Create a job selecting **VK Executor** as the function
4. The agent claims the job and runs the module
5. Check the job artifacts for the execution report

### From the Istari SDK (Python)

```python
from istari_digital_client.client import Client

c = Client()

# Upload the task file
model = c.add_model("task.json", description="My VK task")

# Create a job (the model IS the task_file input)
job = c.add_job(model.id, "@vibekanban:vk_executor")

print(f"Job ID: {job.id}")
```

### Job Lifecycle

```
PENDING → CLAIMED → VALIDATING → RUNNING → UPLOADING → COMPLETED
                                    │
                                    ├── Creates VK issue
                                    └── Starts workspace session
```

---

## 10. Troubleshooting

### Agent sees 0 unclaimed jobs

**Root cause:** The function schema must have at least one `user_model` type input. If all inputs are `parameter` type, the agent's job-matching logic won't return any jobs.

**Fix:** Ensure `function_schemas/vk_executor.json` has:
```json
"inputs": {
  "task_file": {
    "type": "user_model",
    ...
  }
}
```

### Workspace created but no AI session starts

**Root cause:** The task file is missing `repo_id`. Without a repo, `start_workspace_session` is called with `repos: []`, which creates a workspace with no code to work on.

**Fix:** Add `repo_id` to the task JSON:
```json
{
  "project_id": "...",
  "task": "...",
  "agent": "claude-code",
  "repo_id": "your-repo-uuid"
}
```

### Issue created but workspace fails

**Root cause:** The VK MCP server may not be installed or Node.js is missing.

**Fix:** Verify Node.js is available:
```bash
npx -y vibe-kanban@latest --mcp <<< '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'
```

### `add_model` returns an object, not a string

The Istari SDK's `add_model()` returns a `Model` object. Use `.id` to get the string UUID:

```python
model = c.add_model("task.json", description="...")
job = c.add_job(model.id, "@vibekanban:vk_executor")  # .id not model
```

### `add_job` parameters error

The `parameters` argument to `add_job` is keyword-only. For `user_model` inputs, you don't need parameters at all — the uploaded model file IS the input:

```python
# Correct — no parameters needed
c.add_job(model_id, "@vibekanban:vk_executor")

# Wrong — will fail
c.add_job(model_id, "@vibekanban:vk_executor", {})
```

### Agent token vs CLI token permissions

The Istari agent token and CLI token are different users with different permission scopes:

| Token | Can create jobs | Can claim jobs | Can execute functions |
|---|---|---|---|
| CLI token | Yes | No | No |
| Agent token | No (403) | Yes | Yes |

**Workflow:** Use the CLI token to create jobs. The agent token claims and executes them.

---

## 11. Lessons Learned

These are hard-won lessons from building this integration:

### Schema: `user_model` is required

The Istari agent only matches jobs that have at least one `user_model` type input in the function schema. Using only `parameter` type inputs causes the agent to see zero available jobs, even though the job exists. This is the single most important thing to get right.

### The file-based contract is the interface

Everything flows through three files: `input.json`, `output.json`, and `temp_dir`. The agent writes the input, your module writes the output. Getting this contract right is more important than the business logic.

### Two-token architecture

Jobs are created with the **CLI token** (regular user) and executed with the **Agent token** (service account). They are different users in different permission scopes. Don't try to use the agent token to create jobs (403) or the CLI token to run the agent (wrong user type).

### The model IS the input

For `user_model` inputs, you don't pass separate parameters when creating a job. The uploaded model file (your task JSON) is automatically mapped to the `user_model` input. Call `add_job(model_id, function_name)` with no extra arguments.

### `stari client publish` is the source of truth

Publishing via `stari client publish module_manifest.json` registers the function version with proper permissions. Local-only installs work for the agent to run the code, but the registry needs to know about the function for job matching to work.

---

## 12. Links

| Resource | URL |
|---|---|
| Vibe Kanban | https://vibekanban.com |
| Istari Digital | https://istari.app |
| Istari Build Module 101 | https://5005554d.istari-documentation.pages.dev/tutorials/integration-sdk/build-module-101/ |
| Istari SDK (PyPI) | `pip install istari-digital-client` |
| Reference integration (SysGit) | https://github.com/cbensonIstari/sysgit-integration |

---

## Quick Reference

```bash
# Run tests
scripts/test.sh

# Publish to Istari
stari client publish module_manifest.json

# Install locally
scripts/install.sh

# Create a job via SDK
python3 -c "
from istari_digital_client.client import Client
c = Client()
model = c.add_model('task.json', description='My task')
job = c.add_job(model.id, '@vibekanban:vk_executor')
print(f'Job: {job.id}')
"
```

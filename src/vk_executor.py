"""VK Executor: drive Vibe Kanban via MCP from a simple task definition.

Architecture:
- Pure logic functions: validate, plan, report (fully testable)
- VKMcpClient: thin wrapper around VK's MCP stdio server (mockable)
- execute_plan: orchestrates MCP calls using the client
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


# ── Constants ──────────────────────────────────────────────────

VALID_EXECUTORS = {
    "claude-code", "codex", "gemini", "amp", "copilot",
    "cursor_agent", "qwen-code", "droid", "opencode",
}

VALID_PRIORITIES = {"Urgent", "High", "Medium", "Low"}

REQUIRED_MANIFEST_KEYS = {"version", "tasks", "project"}

REQUIRED_TASK_KEYS = {"title", "executor"}


# ── MCP Client ─────────────────────────────────────────────────

class VKMcpClient:
    """Thin wrapper around Vibe Kanban's MCP stdio server.

    Spawns `npx vibe-kanban@latest --mcp` and communicates via JSON-RPC
    over stdio. In tests, mock this class.
    """

    def __init__(self, command="npx", args=None):
        self.command = command
        self.args = args or ["-y", "vibe-kanban@latest", "--mcp"]
        self._process = None
        self._initialized = False
        self._next_id = 1

    def _ensure_initialized(self):
        """Spawn the MCP server and perform the initialize handshake."""
        if self._initialized:
            return
        if self._process is None:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        # MCP initialize handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "vk-executor", "version": "1.0.0"},
            },
        }
        self._next_id += 1
        self._process.stdin.write(json.dumps(init_req) + "\n")
        self._process.stdin.flush()
        self._process.stdout.readline()  # consume init response
        # Send initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self._process.stdin.write(json.dumps(notif) + "\n")
        self._process.stdin.flush()
        self._initialized = True

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Send a JSON-RPC tool call to the MCP server and parse the response."""
        self._ensure_initialized()

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        self._next_id += 1
        self._process.stdin.write(json.dumps(request) + "\n")
        self._process.stdin.flush()
        response_line = self._process.stdout.readline()
        if not response_line:
            return {}
        envelope = json.loads(response_line)
        if "error" in envelope:
            raise RuntimeError(f"MCP error: {envelope['error'].get('message', envelope['error'])}")
        # MCP tools/call returns result.content[0].text as JSON string
        result = envelope.get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return result

    def list_projects(self, organization_id: str) -> list:
        result = self._call_tool("list_projects", {"organization_id": organization_id})
        return result.get("projects", [])

    def create_task(self, project_id: str, title: str, description: str) -> dict:
        return self._call_tool("create_issue", {
            "project_id": project_id,
            "title": title,
            "description": description,
        })

    def list_tasks(self, project_id: str) -> list:
        result = self._call_tool("list_issues", {"project_id": project_id})
        return result.get("issues", [])

    def start_workspace(self, task_id: str, title: str, executor: str,
                        repo_id: str = "", base_branch: str = "main") -> dict:
        args = {
            "title": title,
            "executor": executor.upper(),
            "repos": [{"repo_id": repo_id, "base_branch": base_branch}] if repo_id else [],
        }
        if task_id:
            args["issue_id"] = task_id
        return self._call_tool("start_workspace_session", args)

    def close(self):
        if self._process:
            self._process.terminate()
            self._process = None


# ── Load & Validate ────────────────────────────────────────────

def load_manifest(path: str) -> dict:
    """Load a .vk.json manifest from disk."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    text = p.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}")


def validate_manifest(manifest: dict) -> list:
    """Validate a .vk.json manifest. Returns list of error strings (empty = valid)."""
    errors = []

    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"Missing required key: '{key}'")

    if "tasks" in manifest:
        tasks = manifest["tasks"]
        if not isinstance(tasks, list):
            errors.append("'tasks' must be a list")
        elif len(tasks) == 0:
            errors.append("No tasks found -- tasks list is empty")
        else:
            for i, task in enumerate(tasks):
                if not isinstance(task, dict):
                    errors.append(f"Task {i} is not a dict")
                    continue
                if "title" not in task:
                    errors.append(f"Task {i} missing required key: 'title'")
                if "executor" in task and task["executor"] not in VALID_EXECUTORS:
                    errors.append(
                        f"Task {i} has invalid executor: '{task['executor']}'. "
                        f"Must be one of: {', '.join(sorted(VALID_EXECUTORS))}"
                    )
                if "priority" in task and task["priority"] not in VALID_PRIORITIES:
                    errors.append(
                        f"Task {i} has invalid priority: '{task['priority']}'. "
                        f"Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
                    )

    return errors


# ── Plan Execution ─────────────────────────────────────────────

def plan_execution(manifest: dict) -> dict:
    """Build an execution plan from a manifest. Pure logic, no I/O."""
    tasks = manifest.get("tasks", [])
    defaults = manifest.get("defaults", {})
    default_executor = defaults.get("executor", "claude-code")
    default_repo = defaults.get("repo", "")
    default_branch = defaults.get("base_branch", "main")

    steps = []
    total_subtasks = 0

    for task in tasks:
        executor = task.get("executor", default_executor)
        repo = task.get("repo", default_repo)
        branch = task.get("base_branch", default_branch)

        steps.append({
            "action": "create_task",
            "title": task["title"],
            "description": task.get("description", ""),
            "priority": task.get("priority", "Medium"),
            "tags": task.get("tags", []),
            "parent_title": None,
        })

        steps.append({
            "action": "start_workspace",
            "title": task["title"],
            "executor": executor,
            "repo": repo,
            "base_branch": branch,
        })

        for sub in task.get("subtasks", []):
            total_subtasks += 1
            sub_title = sub if isinstance(sub, str) else sub.get("title", "")
            steps.append({
                "action": "create_task",
                "title": sub_title,
                "description": f"Subtask of: {task['title']}",
                "priority": task.get("priority", "Medium"),
                "tags": task.get("tags", []),
                "parent_title": task["title"],
            })

    total_tasks = len(tasks)
    total_workspaces = len([s for s in steps if s["action"] == "start_workspace"])

    return {
        "steps": steps,
        "summary": {
            "total_tasks": total_tasks,
            "total_subtasks": total_subtasks,
            "total_workspaces": total_workspaces,
        },
    }


# ── Execute Plan ───────────────────────────────────────────────

def execute_plan(plan: dict, client: VKMcpClient, project_id: str) -> list:
    """Execute a plan against a VK MCP client. Returns results per step."""
    results = []
    title_to_task_id = {}

    for step in plan["steps"]:
        action = step["action"]

        if action == "create_task":
            try:
                resp = client.create_task(project_id, step["title"], step["description"])
                task_id = resp.get("issue_id", resp.get("id", ""))
                title_to_task_id[step["title"]] = task_id
                results.append({
                    "action": action,
                    "title": step["title"],
                    "status": "success",
                    "task_id": task_id,
                    "detail": resp,
                })
            except Exception as e:
                results.append({
                    "action": action,
                    "title": step["title"],
                    "status": "error",
                    "error": str(e),
                })

        elif action == "start_workspace":
            task_id = title_to_task_id.get(step["title"], "")

            try:
                resp = client.start_workspace(
                    task_id, step["title"], step["executor"],
                    repo_id=step.get("repo", ""),
                    base_branch=step.get("base_branch", "main"),
                )
                results.append({
                    "action": action,
                    "title": step["title"],
                    "status": "success",
                    "task_id": task_id,
                    "workspace_id": resp.get("workspace_id", ""),
                    "executor": step["executor"],
                    "detail": resp,
                })
            except Exception as e:
                results.append({
                    "action": action,
                    "title": step["title"],
                    "status": "error",
                    "error": str(e),
                })

    return results


# ── Execution Report ───────────────────────────────────────────

def build_execution_report(manifest: dict, plan: dict,
                           results: list, project_id: str) -> dict:
    """Build a JSON execution report from plan + results."""
    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")

    return {
        "project": manifest.get("project", ""),
        "project_id": project_id,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "source": manifest.get("source", {}),
        "summary": {
            "total_steps": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "total_tasks": plan["summary"]["total_tasks"],
            "total_workspaces": plan["summary"]["total_workspaces"],
        },
        "results": results,
    }


def build_execution_report_html(report: dict) -> str:
    """Generate HTML execution report."""
    project = report.get("project", "Unknown")
    summary = report.get("summary", {})
    results = report.get("results", [])

    rows = ""
    for r in results:
        status_class = "success" if r["status"] == "success" else "error"
        task_id = r.get("task_id", "-")
        ws_id = r.get("workspace_id", "-")
        executor = r.get("executor", "-")
        error = r.get("error", "")
        detail = f"Task: {task_id}" if r["action"] == "create_task" else f"WS: {ws_id} ({executor})"
        if error:
            detail = f"Error: {error}"
        rows += (
            f'<tr class="{status_class}">'
            f"<td>{r['action']}</td>"
            f"<td>{r['title']}</td>"
            f"<td>{r['status']}</td>"
            f"<td>{detail}</td>"
            f"</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>VK Execution Report - {project}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
         max-width: 900px; margin: 2em auto; padding: 0 1em; line-height: 1.6; color: #24292e; }}
  h1 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
  th, td {{ border: 1px solid #dfe2e5; padding: 8px 12px; text-align: left; }}
  th {{ background: #f6f8fa; font-weight: 600; }}
  .success {{ background: #f0fff0; }}
  .error {{ background: #fff0f0; }}
  .summary {{ background: #f0f7ff; border: 1px solid #c8e1ff; border-radius: 6px; padding: 1em; margin-bottom: 1em; }}
</style>
</head>
<body>
<h1>Execution Report: {project}</h1>
<div class="summary">
  <strong>Project:</strong> {project}<br/>
  <strong>Total Steps:</strong> {summary.get('total_steps', 0)}<br/>
  <strong>Succeeded:</strong> {summary.get('succeeded', 0)}<br/>
  <strong>Failed:</strong> {summary.get('failed', 0)}
</div>
<table>
<tr><th>Action</th><th>Title</th><th>Status</th><th>Detail</th></tr>
{rows}</table>
</body>
</html>"""


# ── I/O Contract ──────────────────────────────────────────────

def read_input(input_path: str) -> dict:
    """Read and parse the agent-provided input.json.

    Handles both flat format and Istari's typed wrapper format:
        {"key": {"type": "...", "value": "actual_value"}}
    """
    with open(input_path, "r") as f:
        raw = json.load(f)

    parsed = {}
    for key, val in raw.items():
        if isinstance(val, dict) and "value" in val:
            parsed[key] = val["value"]
        else:
            parsed[key] = val
    return parsed


def write_output(output_path: str, files: list):
    """Write the agent-expected output.json."""
    with open(output_path, "w") as f:
        json.dump(files, f, indent=2)

#!/usr/bin/env python3
"""Istari integration entrypoint for Vibe Kanban.

Creates a VK issue and starts an AI workspace session from a simple task file:

    {
      "project_id": "uuid",
      "task": "Description of what to do",
      "agent": "claude-code",
      "repo_id": "uuid"           // optional
    }

Usage:
    python3 entrypoint.py <input_file> <output_file> [temp_dir]

When run via the Istari agent, input_file contains a pointer to the uploaded
task file (user_model). When run locally, input_file IS the task file.
"""

import json
import sys
from pathlib import Path

from vk_executor import (
    validate_manifest,
    plan_execution,
    execute_plan,
    build_execution_report,
    build_execution_report_html,
    VKMcpClient,
    read_input,
    write_output,
)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 entrypoint.py <input.json> <output.json> [temp_dir]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    temp_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(".")

    inputs = read_input(input_path)

    # When run via Istari agent, input.json has task_file pointing to the
    # uploaded JSON. When run locally, input.json IS the task file directly.
    if "task_file" in inputs:
        task_data = json.loads(Path(inputs["task_file"]).read_text())
    else:
        task_data = inputs

    project_id = task_data.get("project_id", "")
    if not project_id:
        print("ERROR: 'project_id' is required", file=sys.stderr)
        sys.exit(1)

    task = task_data.get("task", "")
    if not task:
        print("ERROR: 'task' is required", file=sys.stderr)
        sys.exit(1)

    agent = task_data.get("agent", "claude-code")
    repo_id = task_data.get("repo_id", "")
    base_branch = task_data.get("base_branch", "main")
    dry_run = str(task_data.get("dry_run", "false")).lower() == "true"

    # Build manifest from the simple inputs
    manifest = {
        "version": "1.0.0",
        "project": task,
        "defaults": {
            "executor": agent,
            "repo": repo_id,
            "base_branch": base_branch,
        },
        "tasks": [
            {
                "title": task,
                "executor": agent,
            }
        ],
    }

    errors = validate_manifest(manifest)
    if errors:
        print("Manifest validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    plan = plan_execution(manifest)
    print(f"Task: {task}")
    print(f"Agent: {agent}")
    print(f"Project: {project_id}")
    print(f"Repo: {repo_id or '(none)'}")

    if dry_run:
        print("DRY RUN -- skipping execution")
        results = [{"action": s["action"], "title": s["title"], "status": "skipped"}
                   for s in plan["steps"]]
    else:
        client = VKMcpClient()
        try:
            results = execute_plan(plan, client, project_id)
        finally:
            client.close()

    report = build_execution_report(manifest, plan, results, project_id)
    stem = task.replace(" ", "_").lower()[:50]

    output_files = []

    report_path = temp_dir / f"{stem}_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    output_files.append({
        "name": "execution_report",
        "type": "file",
        "path": str(report_path.resolve()),
    })
    print(f"Wrote report: {report_path}")

    succeeded = report["summary"]["succeeded"]
    failed = report["summary"]["failed"]
    print(f"Results: {succeeded} succeeded, {failed} failed")

    html = build_execution_report_html(report)
    html_path = temp_dir / f"{stem}_report.html"
    html_path.write_text(html)
    output_files.append({
        "name": "execution_report_html",
        "type": "file",
        "path": str(html_path.resolve()),
    })

    write_output(output_path, output_files)
    print("Done.")


if __name__ == "__main__":
    main()

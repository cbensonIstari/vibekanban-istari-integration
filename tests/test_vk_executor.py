"""Tests for vk_executor — pure logic functions + mocked MCP client."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src/ to path so we can import without installing
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vk_executor import (
    REQUIRED_MANIFEST_KEYS,
    REQUIRED_TASK_KEYS,
    VALID_EXECUTORS,
    VALID_PRIORITIES,
    VKMcpClient,
    build_execution_report,
    build_execution_report_html,
    execute_plan,
    load_manifest,
    plan_execution,
    read_input,
    validate_manifest,
    write_output,
)


# ── Fixtures ───────────────────────────────────────────────────

SAMPLE_MANIFEST = {
    "version": "1.0.0",
    "project": "Test Project",
    "defaults": {
        "executor": "claude-code",
        "repo": "repo-uuid-123",
        "base_branch": "main",
    },
    "tasks": [
        {
            "title": "Build the widget",
            "description": "Implement the widget feature",
            "executor": "claude-code",
            "priority": "High",
            "tags": ["feature"],
        }
    ],
}


def make_mock_client():
    client = MagicMock(spec=VKMcpClient)
    client.create_task.return_value = {"issue_id": "task-001"}
    client.start_workspace.return_value = {"workspace_id": "ws-001"}
    return client


# ── Load Manifest ──────────────────────────────────────────────

class TestLoadManifest:
    def test_loads_valid_json(self, tmp_path):
        p = tmp_path / "test.json"
        p.write_text(json.dumps(SAMPLE_MANIFEST))
        result = load_manifest(str(p))
        assert result["project"] == "Test Project"

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_manifest("/nonexistent/path.json")

    def test_raises_on_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json {{{")
        with pytest.raises(ValueError):
            load_manifest(str(p))


# ── Validate Manifest ─────────────────────────────────────────

class TestValidateManifest:
    def test_valid_manifest_has_no_errors(self):
        assert validate_manifest(SAMPLE_MANIFEST) == []

    def test_missing_version(self):
        m = {k: v for k, v in SAMPLE_MANIFEST.items() if k != "version"}
        errors = validate_manifest(m)
        assert any("version" in e for e in errors)

    def test_missing_tasks(self):
        m = {k: v for k, v in SAMPLE_MANIFEST.items() if k != "tasks"}
        errors = validate_manifest(m)
        assert any("tasks" in e for e in errors)

    def test_empty_tasks(self):
        m = {**SAMPLE_MANIFEST, "tasks": []}
        errors = validate_manifest(m)
        assert any("empty" in e for e in errors)

    def test_missing_task_title(self):
        m = {**SAMPLE_MANIFEST, "tasks": [{"executor": "claude-code"}]}
        errors = validate_manifest(m)
        assert any("title" in e for e in errors)

    def test_invalid_executor(self):
        m = {**SAMPLE_MANIFEST, "tasks": [{"title": "x", "executor": "bad-bot"}]}
        errors = validate_manifest(m)
        assert any("executor" in e for e in errors)

    def test_invalid_priority(self):
        m = {**SAMPLE_MANIFEST, "tasks": [{"title": "x", "priority": "Critical"}]}
        errors = validate_manifest(m)
        assert any("priority" in e for e in errors)


# ── Plan Execution ─────────────────────────────────────────────

class TestPlanExecution:
    def test_returns_steps_per_task(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        # 1 task = create_task + start_workspace = 2 steps
        assert len(plan["steps"]) == 2

    def test_create_task_steps(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        creates = [s for s in plan["steps"] if s["action"] == "create_task"]
        assert len(creates) == 1
        assert creates[0]["title"] == "Build the widget"

    def test_start_workspace_steps(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        workspaces = [s for s in plan["steps"] if s["action"] == "start_workspace"]
        assert len(workspaces) == 1

    def test_step_has_executor(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        ws = [s for s in plan["steps"] if s["action"] == "start_workspace"][0]
        assert ws["executor"] == "claude-code"

    def test_step_has_repo_and_branch(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        ws = [s for s in plan["steps"] if s["action"] == "start_workspace"][0]
        assert ws["repo"] == "repo-uuid-123"
        assert ws["base_branch"] == "main"

    def test_subtasks_included(self):
        m = {**SAMPLE_MANIFEST, "tasks": [
            {"title": "Parent", "executor": "claude-code",
             "subtasks": ["Sub A", "Sub B"]}
        ]}
        plan = plan_execution(m)
        creates = [s for s in plan["steps"] if s["action"] == "create_task"]
        assert len(creates) == 3  # parent + 2 subtasks

    def test_plan_summary(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        assert plan["summary"]["total_tasks"] == 1
        assert plan["summary"]["total_workspaces"] == 1

    def test_empty_tasks_returns_empty_plan(self):
        m = {**SAMPLE_MANIFEST, "tasks": []}
        plan = plan_execution(m)
        assert plan["steps"] == []


# ── Execute Plan ───────────────────────────────────────────────

class TestExecutePlan:
    def test_creates_tasks_via_client(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        execute_plan(plan, client, "proj-1")
        client.create_task.assert_called_once()

    def test_starts_workspaces_via_client(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        execute_plan(plan, client, "proj-1")
        client.start_workspace.assert_called_once()

    def test_returns_results_per_step(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        results = execute_plan(plan, client, "proj-1")
        assert len(results) == 2

    def test_result_has_status(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        results = execute_plan(plan, client, "proj-1")
        assert all(r["status"] == "success" for r in results)

    def test_handles_client_error_gracefully(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        client.create_task.side_effect = RuntimeError("MCP error")
        results = execute_plan(plan, client, "proj-1")
        assert results[0]["status"] == "error"
        assert "MCP error" in results[0]["error"]

    def test_workspace_uses_task_id_from_create(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        client = make_mock_client()
        client.create_task.return_value = {"issue_id": "task-xyz"}
        execute_plan(plan, client, "proj-1")
        client.start_workspace.assert_called_once()
        call_args = client.start_workspace.call_args
        assert call_args[0][0] == "task-xyz"


# ── Execution Report ──────────────────────────────────────────

class TestBuildExecutionReport:
    def test_has_summary(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        results = [{"status": "success", "action": "create_task", "title": "x"}]
        report = build_execution_report(SAMPLE_MANIFEST, plan, results, "proj-1")
        assert "summary" in report

    def test_has_project_info(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        report = build_execution_report(SAMPLE_MANIFEST, plan, [], "proj-1")
        assert report["project_id"] == "proj-1"
        assert report["project"] == "Test Project"

    def test_counts_successes_and_errors(self):
        plan = plan_execution(SAMPLE_MANIFEST)
        results = [
            {"status": "success", "action": "create_task", "title": "a"},
            {"status": "error", "action": "start_workspace", "title": "a"},
        ]
        report = build_execution_report(SAMPLE_MANIFEST, plan, results, "p")
        assert report["summary"]["succeeded"] == 1
        assert report["summary"]["failed"] == 1


class TestBuildExecutionReportHtml:
    def test_has_doctype(self):
        report = {"project": "X", "summary": {}, "results": []}
        html = build_execution_report_html(report)
        assert "<!DOCTYPE html>" in html

    def test_contains_project_name(self):
        report = {"project": "My Project", "summary": {}, "results": []}
        html = build_execution_report_html(report)
        assert "My Project" in html

    def test_contains_table(self):
        report = {"project": "X", "summary": {}, "results": []}
        html = build_execution_report_html(report)
        assert "<table>" in html


# ── I/O Contract ──────────────────────────────────────────────

class TestReadInput:
    def test_unwraps_typed_values(self, tmp_path):
        p = tmp_path / "input.json"
        p.write_text(json.dumps({
            "task_file": {"type": "user_model", "value": "/path/to/file.json"}
        }))
        result = read_input(str(p))
        assert result["task_file"] == "/path/to/file.json"

    def test_passes_flat_values(self, tmp_path):
        p = tmp_path / "input.json"
        p.write_text(json.dumps({"project_id": "abc", "task": "do stuff"}))
        result = read_input(str(p))
        assert result["project_id"] == "abc"


class TestWriteOutput:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / "output.json"
        files = [{"name": "report", "type": "file", "path": "/tmp/r.json"}]
        write_output(str(p), files)
        result = json.loads(p.read_text())
        assert result[0]["name"] == "report"


# ── MCP Client Interface ──────────────────────────────────────

class TestVKMcpClientInterface:
    def test_has_create_task_method(self):
        assert hasattr(VKMcpClient, "create_task")

    def test_has_start_workspace_method(self):
        assert hasattr(VKMcpClient, "start_workspace")

    def test_has_list_projects_method(self):
        assert hasattr(VKMcpClient, "list_projects")

    def test_has_list_tasks_method(self):
        assert hasattr(VKMcpClient, "list_tasks")


# ── Constants ──────────────────────────────────────────────────

class TestConstants:
    def test_required_manifest_keys(self):
        assert "version" in REQUIRED_MANIFEST_KEYS
        assert "tasks" in REQUIRED_MANIFEST_KEYS
        assert "project" in REQUIRED_MANIFEST_KEYS

    def test_required_task_keys(self):
        assert "title" in REQUIRED_TASK_KEYS
        assert "executor" in REQUIRED_TASK_KEYS


# ── End-to-End (mocked MCP) ───────────────────────────────────

class TestEndToEnd:
    def test_full_pipeline(self):
        client = make_mock_client()
        errors = validate_manifest(SAMPLE_MANIFEST)
        assert errors == []

        plan = plan_execution(SAMPLE_MANIFEST)
        results = execute_plan(plan, client, "proj-e2e")
        report = build_execution_report(SAMPLE_MANIFEST, plan, results, "proj-e2e")

        assert report["summary"]["succeeded"] == 2
        assert report["summary"]["failed"] == 0

        html = build_execution_report_html(report)
        assert "<!DOCTYPE html>" in html

# encoding: utf-8
import json
import subprocess
from datetime import datetime
from pathlib import Path


PROJECT_STATE_FILE = "project.json"


def find_project_root(start_path):
    current = Path(start_path).resolve()
    for candidate in (current, *current.parents):
        if (candidate / PROJECT_STATE_FILE).is_file():
            return candidate
    return current


def load_project_state(repo_root):
    state_path = find_project_root(repo_root) / PROJECT_STATE_FILE
    with state_path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def get_git_revision(repo_root):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def build_capture_metadata(
    repo_root,
    hardware_revision=None,
    mount_position=None,
    test_type=None,
    operator=None,
    power_source=None,
    trigger_source=None,
):
    project_state = load_project_state(repo_root)

    if hardware_revision:
        project_state["hardware_revision"] = hardware_revision
    if mount_position:
        project_state["mount_position"] = mount_position
    if test_type:
        project_state["test_type"] = test_type

    return {
        "project": project_state.get("project", "kineshoot"),
        "interface_revision": project_state.get("interface_revision"),
        "hardware_revision": project_state.get("hardware_revision"),
        "software_revision": project_state.get("software_revision"),
        "firmware_protocol": project_state.get("firmware_protocol"),
        "mount_position": project_state.get("mount_position"),
        "test_type": project_state.get("test_type"),
        "operator": operator,
        "power_source": power_source,
        "trigger_source": trigger_source,
        "git_sha": get_git_revision(repo_root),
        "metadata_created_at": datetime.now().astimezone().isoformat(),
    }

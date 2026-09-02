"""Audit current project entry points without rewriting dated evidence or release snapshots."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

import yaml

REQUIRED_ACTIVE_DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "README_CN.md",
    "docs/architecture.md",
    "docs/development_framework.md",
    "docs/project_summary.md",
    "docs/project_structure.md",
    "docs/quickstart.md",
    "research/README.md",
    "research/reports/README.md",
    "research/reports/release/README.md",
    "research/reports/release/platform_evidence_manifest.yml",
    "research/reports/planning/device_input_spec_extracted_text.md",
    "specs/001-software-platform-target/quickstart.md",
    "specs/001-software-platform-target/spec.md",
    "specs/001-software-platform-target/plan.md",
    "specs/001-software-platform-target/tasks.md",
    "specs/001-software-platform-target/checklists/platform_requirements.md",
    ".specify/memory/constitution.md",
    ".specify/templates/tasks-template.md",
)
OPTIONAL_ACTIVE_DOCUMENTS = (
    "research/reports/planning/osteo_vision_platform_target_zh.md",
    "research/reports/planning/platform_input_boundary_zh.md",
    "research/reports/planning/three_priority_capabilities_target_20260717_zh.md",
)
PLATFORM_MANIFEST = "research/reports/release/platform_evidence_manifest.yml"
STALE_RULES = (
    (re.compile(r"\bcurrent\s+V[123]\b", re.IGNORECASE), "stage_label", "Replace current-stage V1/V2/V3 wording."),
    (re.compile(r"当前\s*V[123]\s*平台"), "stage_label", "Replace current-stage V1/V2/V3 wording."),
    (re.compile(r"local\s+V1\s+platform", re.IGNORECASE), "stage_label", "Use the current platform name."),
    (
        re.compile(r"python\s+check_(?:env|all)\.py"),
        "retired_quality_entry",
        "Use tools/check_project_readiness.py or Makefile quality targets.",
    ),
    (
        re.compile(r"research/planning/"),
        "retired_research_path",
        "Use research/reports/planning or the dated archive path.",
    ),
    (
        re.compile(r"software_(?:focused_realistic_platform|platform_target_tasks)_zh\.md"),
        "superseded_target_path",
        "Use the current platform target under research/reports/planning.",
    ),
    (
        re.compile(r"legacy_feasibility_report\.md"),
        "archived_feasibility_path",
        "Use the current official platform alignment report.",
    ),
    (
        re.compile(r"官方设备实时视频流"),
        "unsupported_official_interface",
        "Official material confirms JPEG and MP4 file output only.",
    ),
)
# Active documentation stays product-focused. Historical archives and vendor snapshots
# are intentionally outside ``active_documents`` and keep their original wording.
ACTIVITY_LANGUAGE_RULES = (
    (
        re.compile(r"\u6311\u6218\u676f|\u6bd4\u8d5b|\u7ade\u8d5b|\u8d5b\u9898|\u7b54\u8fa9|\u8bc4\u59d4"),
        "activity_specific_language",
        "Remove activity-specific wording from active documentation.",
    ),
)
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    path: str
    line: int | None
    message: str


def canonical_version(value: str) -> str:
    return re.sub(r"(?<=\d)rc(?=\d)", "-rc.", value.strip().lower())


def active_documents(root: Path) -> list[Path]:
    documents = [root / relative for relative in REQUIRED_ACTIVE_DOCUMENTS]
    documents.extend(root / relative for relative in OPTIONAL_ACTIVE_DOCUMENTS if (root / relative).exists())
    return documents


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _audit_text(path: Path, root: Path) -> list[Finding]:
    relative = path.relative_to(root).as_posix()
    if not path.exists():
        return [Finding("error", "missing_active_document", relative, None, "Required active document is missing.")]
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        return [Finding("error", "invalid_utf8", relative, None, str(exc))]
    findings: list[Finding] = []
    for pattern, code, message in STALE_RULES:
        for match in pattern.finditer(text):
            findings.append(Finding("error", code, relative, _line_number(text, match.start()), message))
    for pattern, code, message in ACTIVITY_LANGUAGE_RULES:
        for match in pattern.finditer(text):
            findings.append(Finding("error", code, relative, _line_number(text, match.start()), message))
    for match in LINK_PATTERN.finditer(text):
        target = unquote(match.group(1).strip().split(maxsplit=1)[0].strip("<>"))
        if not target or target.startswith(("#", "http://", "https://", "mailto:", "data:")):
            continue
        target = target.split("#", 1)[0]
        local = (path.parent / target).resolve(strict=False)
        root_relative = (root / target).resolve(strict=False)
        if not local.exists() and not root_relative.exists():
            findings.append(
                Finding(
                    "error",
                    "broken_local_link",
                    relative,
                    _line_number(text, match.start()),
                    f"Missing local link target: {target}",
                )
            )
    return findings


def _json_version(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("version") or payload.get("packages", {}).get("", {}).get("version") or "")


def audit_versions(root: Path) -> list[Finding]:
    pyproject = root / "pyproject.toml"
    with pyproject.open("rb") as handle:
        python_version = str(tomllib.load(handle)["project"]["version"])
    expected = canonical_version(python_version)
    version_files = (
        root / "package.json",
        root / "package-lock.json",
        root / "frontend/package.json",
        root / "frontend/package-lock.json",
    )
    findings: list[Finding] = []
    for path in version_files:
        relative = path.relative_to(root).as_posix()
        if not path.exists():
            findings.append(Finding("error", "missing_version_file", relative, None, "Version file is missing."))
            continue
        try:
            observed = canonical_version(_json_version(path))
        except (json.JSONDecodeError, OSError) as exc:
            findings.append(Finding("error", "invalid_version_file", relative, None, str(exc)))
            continue
        if observed != expected:
            findings.append(
                Finding(
                    "error",
                    "version_mismatch",
                    relative,
                    None,
                    f"Expected {expected}; observed {observed or '<missing>'}.",
                )
            )
    return findings


def audit_platform_manifest(root: Path, expected_version: str) -> list[Finding]:
    manifest_path = root / PLATFORM_MANIFEST
    if not manifest_path.is_file():
        return [
            Finding(
                "error", "missing_platform_manifest", PLATFORM_MANIFEST, None, "Platform evidence manifest is missing."
            )
        ]
    try:
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [Finding("error", "invalid_platform_manifest", PLATFORM_MANIFEST, None, str(exc))]
    if not isinstance(payload, dict):
        return [
            Finding("error", "invalid_platform_manifest", PLATFORM_MANIFEST, None, "Manifest must be a mapping.")
        ]

    findings: list[Finding] = []
    observed_version = canonical_version(str(payload.get("project_version") or ""))
    if observed_version != expected_version:
        findings.append(
            Finding(
                "error",
                "platform_manifest_version_mismatch",
                PLATFORM_MANIFEST,
                None,
                f"Expected {expected_version}; observed {observed_version or '<missing>'}.",
            )
        )
    required = payload.get("evidence_files")
    if not isinstance(required, list):
        findings.append(
            Finding(
                "error",
                "invalid_platform_evidence_list",
                PLATFORM_MANIFEST,
                None,
                "evidence_files must be a list.",
            )
        )
        required = []
    for value in required:
        relative = str(value or "").strip()
        if not relative or not _repository_relative_path(root, relative).is_file():
            findings.append(
                Finding(
                    "error",
                    "missing_platform_evidence",
                    relative or PLATFORM_MANIFEST,
                    None,
                    "Required versioned platform evidence is missing.",
                )
            )

    local_evidence = payload.get("local_runtime_evidence")
    if isinstance(local_evidence, list):
        for value in local_evidence:
            relative = str(value or "").strip()
            if relative and not _repository_relative_path(root, relative).is_file():
                findings.append(
                    Finding(
                        "warning",
                        "missing_local_runtime_evidence",
                        relative,
                        None,
                        "Local runtime evidence is absent and must be regenerated before final packaging.",
                    )
                )

    strict_config = str(payload.get("strict_config") or "").strip()
    strict_path = _repository_relative_path(root, strict_config) if strict_config else None
    if strict_path is None or not strict_path.is_file():
        findings.append(
            Finding(
                "error",
                "missing_strict_config",
                strict_config or PLATFORM_MANIFEST,
                None,
                "Strict config is missing.",
            )
        )
    else:
        findings.extend(_audit_strict_model_binding(strict_path, root))
    findings.extend(_audit_release_tag(root, expected_version))
    return findings


def _repository_relative_path(root: Path, value: str) -> Path:
    candidate = (root / value).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return root / ".invalid-external-path"
    return candidate


def _audit_strict_model_binding(path: Path, root: Path) -> list[Finding]:
    relative = path.relative_to(root).as_posix()
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        return [Finding("error", "invalid_strict_config", relative, None, str(exc))]
    runtime = payload.get("runtime") if isinstance(payload, dict) else None
    tasks = runtime.get("tasks") if isinstance(runtime, dict) else None
    segmentation = tasks.get("segmentation") if isinstance(tasks, dict) else None
    model_id = str(segmentation.get("model_id") or "").strip() if isinstance(segmentation, dict) else ""
    findings: list[Finding] = []
    if not model_id:
        findings.append(
            Finding(
                "error",
                "strict_segmentation_model_missing",
                relative,
                None,
                "Strict runtime requires runtime.tasks.segmentation.model_id.",
            )
        )
    if isinstance(runtime, dict) and runtime.get("allow_heuristic_keyframe_fallback") is not False:
        findings.append(
            Finding(
                "error",
                "strict_heuristic_fallback_enabled",
                relative,
                None,
                "Strict runtime must disable heuristic keyframe fallback.",
            )
        )
    return findings


def _audit_release_tag(root: Path, expected_version: str) -> list[Finding]:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return [Finding("warning", "release_tag_missing", ".git", None, "No release tag is available.")]
    observed = canonical_version(result.stdout.strip().removeprefix("v"))
    if observed == expected_version:
        return []
    return [
        Finding(
            "warning",
            "release_tag_version_drift",
            ".git",
            None,
            f"Expected tag v{expected_version}; latest tag is {result.stdout.strip()}.",
        )
    ]


def run_audit(root: Path) -> dict[str, object]:
    root = root.resolve()
    findings: list[Finding] = []
    for path in active_documents(root):
        findings.extend(_audit_text(path, root))
    try:
        findings.extend(audit_versions(root))
        with (root / "pyproject.toml").open("rb") as handle:
            expected_version = canonical_version(str(tomllib.load(handle)["project"]["version"]))
        findings.extend(audit_platform_manifest(root, expected_version))
    except (KeyError, OSError, tomllib.TOMLDecodeError) as exc:
        findings.append(Finding("error", "invalid_pyproject_version", "pyproject.toml", None, str(exc)))
    errors = [finding for finding in findings if finding.level == "error"]
    warnings = [finding for finding in findings if finding.level == "warning"]
    return {
        "schema_version": "osteo-vision-active-documentation-audit-v1",
        "root": str(root),
        "documents_checked": len(active_documents(root)),
        "passed": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [asdict(finding) for finding in findings],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def main() -> int:
    payload = run_audit(parse_args().root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Safely remove transient workspace output under a verified repository root."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REPO_MARKERS = ("pyproject.toml", ".gitignore")
ROOT_TRANSIENT_DIRS = (
    ".codex_tmp",
    ".mypy_cache",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "frontend/dist",
    "frontend/test-results",
    "frontend/playwright-report",
)
ROOT_TRANSIENT_GLOBS = (".codex_tmp*", ".pytest_tmp*", ".pytest-tmp*", "*.egg-info")
RECURSIVE_CACHE_NAMES = ("__pycache__",)
RECURSIVE_CACHE_ROOTS = ("osteo_vision_core", "backend", "tests", "scripts", "tools", "app")
TRANSIENT_FILES = ("artifacts_tavily_multimodal.json", ".coverage")
TRANSIENT_ARTIFACT_BUCKETS = (
    "artifacts/e2e",
    "artifacts/ui",
)


@dataclass(frozen=True)
class Candidate:
    path: str
    kind: str
    size_bytes: int


@dataclass(frozen=True)
class RemovalFailure:
    path: str
    error: str


def validate_repo_root(root: Path) -> Path:
    resolved = root.resolve()
    missing = [marker for marker in REPO_MARKERS if not (resolved / marker).exists()]
    if missing:
        raise ValueError(f"Refusing cleanup outside an osteo-vision repository; missing: {', '.join(missing)}")
    return resolved


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError:
        return False
    return path.resolve(strict=False) != root


def _path_size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        try:
            return path.lstat().st_size
        except OSError:
            return 0
    total = 0
    pending = [path]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink() or entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _candidate(path: Path, root: Path) -> Candidate:
    relative = path.relative_to(root).as_posix()
    kind = "directory" if path.is_dir() and not path.is_symlink() else "file"
    return Candidate(path=relative, kind=kind, size_bytes=_path_size(path))


def _unique_existing(paths: Iterable[Path], root: Path) -> list[Path]:
    unique: dict[str, Path] = {}
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        if not _is_within_root(path, root):
            raise ValueError(f"Cleanup candidate escapes repository root: {path}")
        unique[str(path.resolve(strict=False)).casefold()] = path
    ordered = sorted(unique.values(), key=lambda item: (len(item.parts), item.as_posix().casefold()))
    compacted: list[Path] = []
    resolved_parents: list[Path] = []
    for path in ordered:
        resolved = path.resolve(strict=False)
        if any(_is_same_or_descendant(resolved, parent) for parent in resolved_parents):
            continue
        compacted.append(path)
        resolved_parents.append(resolved)
    return sorted(compacted, key=lambda item: item.as_posix().casefold())


def _is_same_or_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def collect_candidates(root: Path, *, include_artifacts: bool = False) -> list[Candidate]:
    root = validate_repo_root(root)
    paths: list[Path] = [root / relative for relative in ROOT_TRANSIENT_DIRS]
    paths.extend(root / relative for relative in TRANSIENT_FILES)
    for pattern in ROOT_TRANSIENT_GLOBS:
        paths.extend(root.glob(pattern))
    for cache_name in RECURSIVE_CACHE_NAMES:
        paths.append(root / cache_name)
    for relative_root in RECURSIVE_CACHE_ROOTS:
        search_root = root / relative_root
        if not search_root.is_dir():
            continue
        for cache_name in RECURSIVE_CACHE_NAMES:
            paths.extend(search_root.rglob(cache_name))
    if include_artifacts:
        for relative in TRANSIENT_ARTIFACT_BUCKETS:
            bucket = root / relative
            if not bucket.is_dir():
                continue
            paths.extend(child for child in bucket.iterdir() if child.name != ".gitkeep")
    return [_candidate(path, root) for path in _unique_existing(paths, root)]


def remove_candidates(root: Path, candidates: Iterable[Candidate]) -> list[Candidate]:
    root = validate_repo_root(root)
    allowed_paths = {item.path for item in collect_candidates(root, include_artifacts=True)}
    removed: list[Candidate] = []
    for candidate in candidates:
        path = _validated_removal_path(root, candidate, allowed_paths)
        if _remove_path(path):
            removed.append(candidate)
    return removed


def remove_candidates_best_effort(
    root: Path,
    candidates: Iterable[Candidate],
) -> tuple[list[Candidate], list[RemovalFailure]]:
    root = validate_repo_root(root)
    allowed_paths = {item.path for item in collect_candidates(root, include_artifacts=True)}
    removed: list[Candidate] = []
    failures: list[RemovalFailure] = []
    for candidate in candidates:
        path = _validated_removal_path(root, candidate, allowed_paths)
        try:
            if _remove_path(path):
                removed.append(candidate)
        except OSError as exc:
            failures.append(RemovalFailure(path=candidate.path, error=str(exc)))
    return removed, failures


def _validated_removal_path(root: Path, candidate: Candidate, allowed_paths: set[str]) -> Path:
    if candidate.path not in allowed_paths:
        raise ValueError(f"Cleanup candidate is outside the transient allowlist: {candidate.path}")
    path = root / candidate.path
    if not _is_within_root(path, root):
        raise ValueError(f"Cleanup candidate escapes repository root: {path}")
    return path


def _remove_path(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def _summary(
    root: Path,
    candidates: list[Candidate],
    *,
    applied: bool,
    removed: list[Candidate] | None = None,
    failures: list[RemovalFailure] | None = None,
) -> dict[str, object]:
    removal_failures = failures or []
    return {
        "schema_version": "osteo-vision-workspace-cleanup-v1",
        "root": str(root),
        "mode": "apply" if applied else "preview",
        "passed": not removal_failures,
        "candidate_count": len(candidates),
        "reclaimable_bytes": sum(item.size_bytes for item in candidates),
        "candidates": [asdict(item) for item in candidates],
        "removed_count": len(removed or []),
        "removed": [asdict(item) for item in (removed or [])],
        "failure_count": len(removal_failures),
        "failures": [asdict(item) for item in removal_failures],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true", help="Delete discovered candidates after path validation.")
    parser.add_argument(
        "--include-artifacts",
        action="store_true",
        help="Also clear disposable E2E and UI artifacts while preserving .gitkeep files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = validate_repo_root(args.root)
        candidates = collect_candidates(root, include_artifacts=args.include_artifacts)
        removed: list[Candidate] = []
        failures: list[RemovalFailure] = []
        if args.apply:
            removed, failures = remove_candidates_best_effort(root, candidates)
    except (OSError, ValueError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(
        json.dumps(
            _summary(root, candidates, applied=args.apply, removed=removed, failures=failures),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

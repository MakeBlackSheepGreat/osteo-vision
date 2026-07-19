from __future__ import annotations

from copy import deepcopy

import pytest

from tools.download_pmcanalseg_navigation_starter import (
    EXPECTED_LICENSE,
    EXPECTED_VERSION,
    PINNED_FILES,
    SELECTED_PATIENTS,
    _validate_dataset_metadata,
)


def _metadata() -> dict[str, object]:
    files = []
    for spec in PINNED_FILES:
        if spec["role"] == "information":
            directory = ""
            label = "Information.xlsx"
        else:
            directory = f"{spec['region']}/{spec['patient']}"
            label = "image.nii.gz" if spec["role"] == "image" else "label.nii.gz"
        files.append(
            {
                "label": label,
                "directoryLabel": directory,
                "restricted": False,
                "dataFile": {
                    "id": spec["id"],
                    "filesize": spec["size"],
                    "md5": spec["md5"],
                },
            }
        )
    return {
        "status": "OK",
        "data": {
            "protocol": "doi",
            "authority": "10.7910",
            "identifier": "DVN/RTIGTP",
            "latestVersion": {
                "versionNumber": EXPECTED_VERSION,
                "versionState": "RELEASED",
                "license": {"name": EXPECTED_LICENSE},
                "files": files,
            },
        },
    }


def test_validated_metadata_requires_all_pinned_pairs() -> None:
    specs = _validate_dataset_metadata(_metadata())

    assert len(specs) == len(PINNED_FILES)
    for patient in SELECTED_PATIENTS:
        assert len([spec for spec in specs if spec["patient"] == patient]) == 4
    assert all(str(spec["download_url"]).startswith("https://dataverse.harvard.edu/") for spec in specs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("versionNumber", EXPECTED_VERSION + 1),
        ("versionState", "DRAFT"),
    ],
)
def test_validated_metadata_fails_closed_on_version_change(field: str, value: object) -> None:
    payload = _metadata()
    payload["data"]["latestVersion"][field] = value  # type: ignore[index]

    with pytest.raises(RuntimeError):
        _validate_dataset_metadata(payload)


def test_validated_metadata_fails_closed_on_license_change() -> None:
    payload = _metadata()
    payload["data"]["latestVersion"]["license"] = {"name": "Custom"}  # type: ignore[index]

    with pytest.raises(RuntimeError, match="license"):
        _validate_dataset_metadata(payload)


@pytest.mark.parametrize("mutation", ["restricted", "size", "md5", "directory"])
def test_validated_metadata_fails_closed_on_file_change(mutation: str) -> None:
    payload = deepcopy(_metadata())
    entry = payload["data"]["latestVersion"]["files"][0]  # type: ignore[index]
    if mutation == "restricted":
        entry["restricted"] = True
    elif mutation == "size":
        entry["dataFile"]["filesize"] += 1
    elif mutation == "md5":
        entry["dataFile"]["md5"] = "0" * 32
    else:
        entry["directoryLabel"] = "unexpected"

    with pytest.raises(RuntimeError):
        _validate_dataset_metadata(payload)

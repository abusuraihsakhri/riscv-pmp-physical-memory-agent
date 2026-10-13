"""CSV inputs must not coerce the string 'False' to true."""
import csv
from pathlib import Path
import pytest

from riscv_pmp_agent.cli import main, parse_csv_bool


@pytest.mark.parametrize(("raw", "expected"), [
    ("false", False), ("False", False), (" 0 ", False),
    ("NO", False), ("", False), ("true", True), (" YES ", True), ("1", True),
])
def test_csv_boolean_cases(raw, expected):
    assert parse_csv_bool(raw) is expected


def test_invalid_boolean_rejected():
    with pytest.raises(ValueError, match="is_critical_flag"):
        parse_csv_bool("perhaps")


def test_cli_batch_false_does_not_escalate(tmp_path: Path):
    input_path = tmp_path / "records.csv"
    output_path = tmp_path / "output.csv"
    with input_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "task_id", "target_identifier", "primary_metric",
            "secondary_metric", "status_descriptor", "is_critical_flag",
        ])
        writer.writeheader()
        writer.writerow({
            "task_id": "CLI-FALSE", "target_identifier": "PMP-TEST",
            "primary_metric": 10, "secondary_metric": 5,
            "status_descriptor": "NOMINAL", "is_critical_flag": "False",
        })
    assert main(["batch", "-i", str(input_path), "-o", str(output_path)]) == 0
    with output_path.open(encoding="utf-8", newline="") as file:
        row = next(csv.DictReader(file))
    assert row["overall_status"] == "NOMINAL_OPTIMAL"
    assert row["critical_count"] == "0"

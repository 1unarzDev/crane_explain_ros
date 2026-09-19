"""Append-only JSONL artifact writer, independent of ROS for unit testing."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class ArtifactWriter:
    def __init__(
        self, root: str | Path, episode_id: str, run_id: str, bt_xml: str | None,
        sync_interval_records: int = 100,
    ):
        if sync_interval_records < 1:
            raise ValueError("sync_interval_records must be positive")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.stream = (self.root / "events.jsonl").open("x", encoding="utf-8")
        self.sync_interval_records = sync_interval_records
        self.records_since_sync = 0
        manifest: dict[str, Any] = {
            "schema": "crane-explain-ros-capture/v1",
            "episode_id": episode_id,
            "run_id": run_id,
            "pid": os.getpid(),
            "persistence": {
                "flush_each_record": True,
                "fsync_interval_records": sync_interval_records,
                "fsync_on_close": True,
            },
            "limitations": [
                "topic delivery does not prove internal consumption",
                "action status is not the NavigateToPose result/error payload",
                "goal and result payloads require explicit harness_event records",
            ],
        }
        if bt_xml:
            source = Path(bt_xml)
            payload = source.read_bytes()
            (self.root / "behavior_tree.xml").write_bytes(payload)
            manifest["bt_xml_source"] = str(source.resolve())
            manifest["bt_xml_sha256"] = hashlib.sha256(payload).hexdigest()
        with (self.root / "manifest.json").open("x", encoding="utf-8") as output:
            json.dump(manifest, output, indent=2, sort_keys=True)
            output.write("\n")

    def write(self, record: dict[str, Any]) -> None:
        self.stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        self.stream.flush()
        self.records_since_sync += 1
        if self.records_since_sync >= self.sync_interval_records:
            os.fsync(self.stream.fileno())
            self.records_since_sync = 0

    def close(self) -> None:
        if not self.stream.closed:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.records_since_sync = 0
            self.stream.close()

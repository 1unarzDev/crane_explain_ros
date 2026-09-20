import json
from pathlib import Path

from crane_explain_ros.writer import ArtifactWriter


def test_writer_retains_manifest_limitations_and_events(tmp_path):
    xml = tmp_path / "tree.xml"
    xml.write_text("<root/>", encoding="utf-8")
    writer = ArtifactWriter(tmp_path / "artifact", "opaque-e1", "run-1", str(xml))
    writer.write({"type": "client_deadline", "id": "d1"})
    writer.close()
    manifest = json.loads((tmp_path / "artifact/manifest.json").read_text())
    assert len(manifest["bt_xml_sha256"]) == 64
    assert manifest["persistence"] == {
        "flush_each_record": True,
        "fsync_interval_records": 100,
        "fsync_on_close": True,
    }
    assert (
        "action status is not the NavigateToPose result/error payload"
        in manifest["limitations"]
    )
    assert json.loads((tmp_path / "artifact/events.jsonl").read_text())["id"] == "d1"


def test_writer_rejects_nonpositive_sync_interval(tmp_path):
    try:
        ArtifactWriter(tmp_path / "artifact", "opaque-e1", "run-1", None, 0)
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("expected invalid sync interval to be rejected")


def test_writer_retains_exact_runtime_manifest_identity(tmp_path):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(
        json.dumps({"schema": "runtime-provenance/v1", "image_digest": "sha256:abc"})
        + "\n",
        encoding="utf-8",
    )

    writer = ArtifactWriter(
        tmp_path / "artifact",
        "opaque-e1",
        "run-1",
        None,
        runtime_manifest=str(runtime),
    )
    writer.close()

    manifest = json.loads((tmp_path / "artifact/manifest.json").read_text())
    retained = tmp_path / "artifact/runtime_manifest.json"
    assert retained.read_bytes() == runtime.read_bytes()
    assert (
        manifest["runtime_manifest_sha256"]
        == __import__("hashlib").sha256(runtime.read_bytes()).hexdigest()
    )


def test_capture_uses_transient_local_harness_qos():
    capture = (
        Path(__file__).parents[1] / "crane_explain_ros" / "capture.py"
    ).read_text()
    harness = capture.split("harness_qos = QoSProfile(", 1)[1].split(")", 1)[0]
    assert "ReliabilityPolicy.RELIABLE" in harness
    assert "DurabilityPolicy.TRANSIENT_LOCAL" in harness
    assert "depth=20" in harness

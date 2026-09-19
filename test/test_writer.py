import json

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
    assert "action status is not the NavigateToPose result/error payload" in manifest["limitations"]
    assert json.loads((tmp_path / "artifact/events.jsonl").read_text())["id"] == "d1"


def test_writer_rejects_nonpositive_sync_interval(tmp_path):
    try:
        ArtifactWriter(tmp_path / "artifact", "opaque-e1", "run-1", None, 0)
    except ValueError as exc:
        assert "must be positive" in str(exc)
    else:
        raise AssertionError("expected invalid sync interval to be rejected")

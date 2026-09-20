from types import SimpleNamespace

from crane_explain_ros.capture import EvidenceCapture


class RecordingWriter:
    def __init__(self):
        self.records = []

    def write(self, record):
        self.records.append(record)


def test_jazzy_goal_status_array_does_not_require_header():
    writer = RecordingWriter()
    capture = SimpleNamespace(writer=writer)
    stamp = SimpleNamespace(sec=12, nanosec=34)
    goal_id = SimpleNamespace(uuid=bytes.fromhex("00" * 15 + "01"))
    goal_info = SimpleNamespace(goal_id=goal_id, stamp=stamp)
    message = SimpleNamespace(
        status_list=[SimpleNamespace(goal_info=goal_info, status=2)]
    )

    EvidenceCapture.on_status(capture, message)

    record = writer.records[0]
    assert record["type"] == "action_status"
    assert record["statuses"] == [
        {
            "goal_id": "00" * 15 + "01",
            "accepted_stamp": {"sec": 12, "nanosec": 34},
            "status": 2,
        }
    ]
    assert isinstance(record["received_wall_time_ns"], int)

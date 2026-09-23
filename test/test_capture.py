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


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def test_command_capture_retains_values_and_bounded_provenance():
    writer = RecordingWriter()
    capture = SimpleNamespace(writer=writer)
    message = SimpleNamespace(linear=vector(0.4, 0.0, 0.0), angular=vector(0.0, 0.0, -0.2))

    EvidenceCapture.on_command(capture, message)

    record = writer.records[0]
    assert record["type"] == "nav2_command"
    assert record["linear_mps"] == {"x": 0.4, "y": 0.0, "z": 0.0}
    assert record["angular_radps"]["z"] == -0.2
    assert record["provenance"] == "delivered-nav2-command-not-proof-of-actuator-acceptance"


def test_odometry_capture_retains_pose_twist_frames_and_stamp():
    writer = RecordingWriter()
    capture = SimpleNamespace(writer=writer)
    pose = SimpleNamespace(
        position=vector(1.0, 2.0, 3.0),
        orientation=SimpleNamespace(x=0.0, y=0.0, z=0.1, w=0.99),
    )
    twist = SimpleNamespace(linear=vector(0.25, 0.0, 0.0), angular=vector(0.0, 0.0, 0.05))
    message = SimpleNamespace(
        header=SimpleNamespace(stamp=SimpleNamespace(sec=12, nanosec=34), frame_id="odom"),
        child_frame_id="base_link",
        pose=SimpleNamespace(pose=pose),
        twist=SimpleNamespace(twist=twist),
    )

    EvidenceCapture.on_odometry(capture, message)

    record = writer.records[0]
    assert record["type"] == "measured_odometry"
    assert record["stamp"] == {"sec": 12, "nanosec": 34}
    assert record["frame_id"] == "odom"
    assert record["child_frame_id"] == "base_link"
    assert record["position_m"]["x"] == 1.0
    assert record["linear_velocity_mps"]["x"] == 0.25
    assert record["provenance"] == "delivered-odometry-not-proof-of-nav2-consumption"

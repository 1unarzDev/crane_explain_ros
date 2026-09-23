"""Passive Nav2 topic observer plus explicit harness-side event ingress.

The action protocol sends goals/results over services, not ordinary topics. This observer records
feedback and goal status passively. The action-owning experiment harness must publish JSON records
for sent goals, returned result/error payloads, client cancellations, and client deadlines on the
configured harness topic. That distinction is retained in every artifact manifest.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import rclpy
from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from nav2_msgs.msg import BehaviorTreeLog
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_system_default,
)
from std_msgs.msg import String

from .writer import ArtifactWriter


def stamp(value: Any) -> dict[str, int]:
    return {"sec": int(value.sec), "nanosec": int(value.nanosec)}


def duration(value: Any) -> float:
    return float(value.sec) + float(value.nanosec) / 1_000_000_000


class EvidenceCapture(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("crane_explanation_evidence_capture")
        self.writer = ArtifactWriter(
            args.output,
            args.episode_id,
            args.run_id,
            args.bt_xml,
            runtime_manifest=args.runtime_manifest,
        )
        base = args.action.rstrip("/")
        self.create_subscription(BehaviorTreeLog, args.bt_topic, self.on_bt, 10)
        self.create_subscription(
            NavigateToPose.Impl.FeedbackMessage,
            base + "/_action/feedback",
            self.on_feedback,
            qos_profile_system_default,
        )
        self.create_subscription(
            GoalStatusArray,
            base + "/_action/status",
            self.on_status,
            qos_profile_system_default,
        )
        self.create_subscription(
            Twist, args.command_topic, self.on_command, qos_profile_system_default
        )
        self.create_subscription(
            Odometry, args.odom_topic, self.on_odometry, qos_profile_system_default
        )
        harness_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=20,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            String, args.harness_topic, self.on_harness, harness_qos
        )
        self.writer.write({"type": "capture_started", "wall_time_ns": time.time_ns()})

    def on_bt(self, message: BehaviorTreeLog) -> None:
        for event in message.event_log:
            self.writer.write(
                {
                    "type": "bt_transition",
                    "message_stamp": stamp(message.timestamp),
                    "event_stamp": stamp(event.timestamp),
                    "node_name": event.node_name,
                    "node_uid": event.uid,
                    "previous_status": event.previous_status,
                    "current_status": event.current_status,
                }
            )

    def on_feedback(self, message: Any) -> None:
        feedback = message.feedback
        self.writer.write(
            {
                "type": "navigate_to_pose_feedback",
                "goal_id": bytes(message.goal_id.uuid).hex(),
                "navigation_time_s": duration(feedback.navigation_time),
                "estimated_time_remaining_s": duration(
                    feedback.estimated_time_remaining
                ),
                "number_of_recoveries": int(feedback.number_of_recoveries),
                "distance_remaining": float(feedback.distance_remaining),
                "current_pose_stamp": stamp(feedback.current_pose.header.stamp),
                "current_pose_frame": feedback.current_pose.header.frame_id,
            }
        )

    def on_status(self, message: GoalStatusArray) -> None:
        self.writer.write(
            {
                "type": "action_status",
                "received_wall_time_ns": time.time_ns(),
                "statuses": [
                    {
                        "goal_id": bytes(item.goal_info.goal_id.uuid).hex(),
                        "accepted_stamp": stamp(item.goal_info.stamp),
                        "status": int(item.status),
                    }
                    for item in message.status_list
                ],
            }
        )

    def on_command(self, message: Twist) -> None:
        self.writer.write(
            {
                "type": "nav2_command",
                "received_wall_time_ns": time.time_ns(),
                "linear_mps": {
                    "x": float(message.linear.x),
                    "y": float(message.linear.y),
                    "z": float(message.linear.z),
                },
                "angular_radps": {
                    "x": float(message.angular.x),
                    "y": float(message.angular.y),
                    "z": float(message.angular.z),
                },
                "provenance": "delivered-nav2-command-not-proof-of-actuator-acceptance",
            }
        )

    def on_odometry(self, message: Odometry) -> None:
        pose = message.pose.pose
        twist = message.twist.twist
        self.writer.write(
            {
                "type": "measured_odometry",
                "received_wall_time_ns": time.time_ns(),
                "stamp": stamp(message.header.stamp),
                "frame_id": message.header.frame_id,
                "child_frame_id": message.child_frame_id,
                "position_m": {
                    "x": float(pose.position.x),
                    "y": float(pose.position.y),
                    "z": float(pose.position.z),
                },
                "orientation_xyzw": {
                    "x": float(pose.orientation.x),
                    "y": float(pose.orientation.y),
                    "z": float(pose.orientation.z),
                    "w": float(pose.orientation.w),
                },
                "linear_velocity_mps": {
                    "x": float(twist.linear.x),
                    "y": float(twist.linear.y),
                    "z": float(twist.linear.z),
                },
                "angular_velocity_radps": {
                    "x": float(twist.angular.x),
                    "y": float(twist.angular.y),
                    "z": float(twist.angular.z),
                },
                "provenance": "delivered-odometry-not-proof-of-nav2-consumption",
            }
        )

    def on_harness(self, message: String) -> None:
        try:
            event = json.loads(message.data)
        except (TypeError, json.JSONDecodeError) as exc:
            self.writer.write({"type": "invalid_harness_event", "error": str(exc)})
            return
        if not isinstance(event, dict) or event.get("type") not in {
            "navigate_to_pose_goal",
            "navigate_to_pose_result",
            "client_cancel",
            "client_deadline",
            "crane_identity",
            "observation_identity",
        }:
            self.writer.write(
                {"type": "invalid_harness_event", "error": "unsupported type"}
            )
            return
        self.writer.write({"type": "harness_event", "event": event})

    def destroy_node(self) -> bool:
        self.writer.write({"type": "capture_stopped", "wall_time_ns": time.time_ns()})
        self.writer.close()
        return super().destroy_node()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", required=True, help="new, non-existing artifact directory"
    )
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bt-xml")
    parser.add_argument(
        "--runtime-manifest",
        help="immutable JSON runtime/source manifest copied and hashed into the capture",
    )
    parser.add_argument("--bt-topic", default="/behavior_tree_log")
    parser.add_argument("--action", default="/navigate_to_pose")
    parser.add_argument("--harness-topic", default="/crane/explanation_event")
    parser.add_argument("--command-topic", default="/nav2/cmd_vel")
    parser.add_argument("--odom-topic", default="/crane/odom")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    rclpy.init(args=None)
    node = EvidenceCapture(args)
    try:
        rclpy.spin(node)
    except (ExternalShutdownException, KeyboardInterrupt):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

# crane_explain_ros

ROS 2 Jazzy passive evidence capture for the CRANE explanation-fidelity study. The package records
Nav2 `BehaviorTreeLog`, `NavigateToPose` feedback and goal status, an exact copy/hash of the BT XML,
and explicit experiment-harness events.

Goals and results use ROS action services, so a topic-only observer cannot recover their payloads.
The action-owning harness must publish JSON on `/crane/explanation_event` for goal, result/error,
client cancellation/deadline, CRANE episode/run/tick identity, and observation identity. Status is
never mislabeled as the result payload.

```bash
cd /workspace/astro_dock
ln -s /workspace/crane_explain_ros src/crane_explain_ros  # once, if kept outside src
colcon build --packages-select crane_explain_ros
. install/setup.bash
ros2 run crane_explain_ros capture --ros-args -- \
  --output /results/opaque-e1 --episode-id opaque-e1 --run-id run-1 \
  --bt-xml /path/to/exact_tree.xml
```

Current status: **IMPLEMENTED**; writer unit and isolated Jazzy-container `colcon build` **TESTED**;
live Nav2 capture **NOT_RUN**. No C++ BT hook is used.

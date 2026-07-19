# ros2（骨架）

**占坑**：有硬件伙伴后再加 `rclpy` 依赖与 Service 封装。

拟定映射（待实现）：

| ROS2 | NovaPanda |
|------|-----------|
| Service / Action 完成事件 | `deliverable` 证据字段 |
| Node 持钥旁路进程 | `AdopterRuntime` / SDK |
| Topic 名 `idle/busy` | **不得**写入 Exchange `state` |

社区 PR 欢迎；合并前须通过 `adapter_author_checklist` 且不引入强制 ROS 依赖到 CORE 包。

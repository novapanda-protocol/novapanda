"""物理资源适配 v3 占位（energy.* / actuation.*）。"""



from __future__ import annotations



from typing import Any



PHYSICAL_VERSION = "0.3-placeholder"



RESERVED_TYPES = frozenset({

    "energy.electric.dc",

    "actuation.robot.task",

})



_DELIVERABLE_CHECKS: dict[str, tuple[str, ...]] = {

    "energy.electric.dc": ("session_id", "kwh_delivered", "meter_signature"),

    "actuation.robot.task": ("task_id", "completion_proof", "duration_secs"),

}





def is_reserved_physical_type(resource_type: str) -> bool:

    return resource_type in RESERVED_TYPES





def validate_physical_deliverable(resource_type: str, deliverable: Any) -> list[str]:

    """校验物理类 deliverable 最小字段（energy 可接 ISO15118 模拟器）。"""

    errors: list[str] = []

    if resource_type not in RESERVED_TYPES:

        errors.append(f"非预留物理类型: {resource_type}")

        return errors

    if not isinstance(deliverable, dict):

        return ["deliverable 必须为 object"]

    for field in _DELIVERABLE_CHECKS[resource_type]:

        if field not in deliverable:

            errors.append(f"缺少字段: {field}")

    if resource_type == "energy.electric.dc":

        kwh = deliverable.get("kwh_delivered")

        if kwh is not None and not isinstance(kwh, (int, str)):

            errors.append("kwh_delivered 须为整数或字符串")

        from .iso15118_sim import validate_sim_deliverable



        errors.extend(validate_sim_deliverable(deliverable))

    return errors





def iso15118_session_stub(session_id: str) -> dict:

    """兼容旧 stub：委托 iso15118_sim。"""

    from .iso15118_sim import get_session



    sess = get_session(session_id)

    if sess is None:

        return {

            "adapter": "iso15118-stub/v0",

            "session_id": session_id,

            "status": "unknown",

            "note": "Use POST /v3/iso15118/sessions to create sim session",

        }

    return {

        "adapter": sess.get("sim_version", "iso15118-sim/v1"),

        "session_id": session_id,

        "status": sess.get("status"),

        "kwh_delivered": sess.get("kwh_delivered"),

    }


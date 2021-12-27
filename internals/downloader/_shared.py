from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from internals.db import VTHellJob, VTHellJobStatus
    from internals.vth import SanicVTHell


__all__ = ("quick_update_dispatch",)


async def quick_update_dispatch(
    data: VTHellJob,
    app: SanicVTHell,
    status: VTHellJobStatus,
    notify: bool = False,
    extras: Dict[str, Any] = {},
):
    data.status = status
    data.error = None
    data.last_status = None
    await data.save()
    data_update = {"id": data.id, "status": status.value}
    if extras:
        extras.pop("id", None)
        extras.pop("status", None)
        if extras:
            data_update.update(extras)
    await app.wshandler.emit("job_update", data_update)
    if app.first_process and app.ipc:
        await app.ipc.emit("ws_job_update", data_update)
    if notify:
        await app.dispatch(
            "internals.notifier.discord",
            context={"app": app, "data": data, "emit_type": "update"},
        )

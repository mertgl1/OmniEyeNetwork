from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class DeviceCommandRequest:
    key: str
    hostname: str
    ip_address: str
    port: int
    username: str
    password: str
    device_type: str
    commands: Dict[str, str]
    enable_secret: str = ""
    paging_disable_command: Optional[str] = None
    ssh_strict: bool = False


@dataclass(frozen=True)
class DeviceCommandResult:
    outputs: Optional[Dict[str, str]] = None
    error_type: Optional[str] = None


def run_device_commands(
    requests: list[DeviceCommandRequest],
    max_workers: int = 20,
) -> Dict[str, DeviceCommandResult]:
    """Run per-device command sets concurrently through Nornir and Netmiko."""
    if not requests:
        return {}

    from nornir.core import Nornir
    from nornir.core.configuration import Config
    from nornir.core.inventory import (
        ConnectionOptions,
        Defaults,
        Groups,
        Host,
        Hosts,
        Inventory,
    )
    from nornir.core.plugins.connections import ConnectionPluginRegister
    from nornir.core.task import Result, Task
    from nornir.plugins.runners import ThreadedRunner
    from nornir_netmiko.connections import Netmiko

    ConnectionPluginRegister.register("netmiko", Netmiko)

    if len({request.key for request in requests}) != len(requests):
        raise ValueError("Nornir request keys must be unique.")

    hosts = Hosts()
    for request in requests:
        if not request.username or not request.password:
            raise ValueError(f"SSH credentials are missing for device {request.key}.")

        hosts[request.key] = Host(
            name=request.key,
            hostname=request.ip_address,
            port=request.port,
            username=request.username,
            password=request.password,
            platform=request.device_type,
            data={
                "commands": request.commands,
                "enable_secret": request.enable_secret,
                "paging_disable_command": request.paging_disable_command,
            },
            connection_options={
                "netmiko": ConnectionOptions(
                    extras={
                        "secret": request.enable_secret,
                        "timeout": 20,
                        "session_timeout": 60,
                        "ssh_strict": request.ssh_strict,
                        "system_host_keys": request.ssh_strict,
                    }
                )
            },
        )

    inventory = Inventory(hosts=hosts, groups=Groups(), defaults=Defaults())
    nornir = Nornir(
        inventory=inventory,
        config=Config(),
        runner=ThreadedRunner(num_workers=max(1, min(max_workers, len(requests)))),
    )

    def execute(task: Task) -> Result:
        connection = task.host.get_connection("netmiko", task.nornir.config)
        enable_secret = task.host.data["enable_secret"]
        if enable_secret:
            connection.enable()

        paging_command = task.host.data["paging_disable_command"]
        if paging_command:
            connection.send_command(paging_command)

        outputs = {
            name: connection.send_command(command)
            for name, command in task.host.data["commands"].items()
        }
        return Result(host=task.host, result=outputs)

    try:
        aggregate = nornir.run(task=execute, raise_on_error=False)
        results: Dict[str, DeviceCommandResult] = {}
        for key, host_results in aggregate.items():
            if host_results.failed:
                results[key] = DeviceCommandResult(error_type="DeviceCommandFailed")
                continue

            task_result = next(
                (item for item in reversed(host_results) if isinstance(item.result, dict)),
                None,
            )
            if task_result is None:
                results[key] = DeviceCommandResult(error_type="MissingCommandOutput")
            else:
                results[key] = DeviceCommandResult(outputs=task_result.result)
        return results
    finally:
        nornir.close_connections()

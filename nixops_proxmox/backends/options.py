from nixops.backends import MachineOptions
from typing import Mapping, Union, Optional, Sequence
from nixops.resources import ResourceOptions
from typing_extensions import Literal

class IPOptions(ResourceOptions):
    gateway: Optional[str]
    address: str
    prefixLength: Optional[int]

class NetworkOptions(ResourceOptions):
    model: str
    bridge: str
    tag: Optional[int]
    trunks: Sequence[str]
    ip: Mapping[Union[Literal["v4"], Literal["v6"]],
            IPOptions]

class DiskOptions(ResourceOptions):
    volume: str
    size: str
    aio: Optional[str]
    enableSSDEmulation: bool
    enableDiscard: bool

class UefiOptions(ResourceOptions):
    enable: bool
    volume: str

class ProxmoxOptions(ResourceOptions):
    serverUrl: str
    username: str
    password: Optional[str]
    tokenName: Optional[str]
    tokenValue: Optional[str]
    useSSH: bool
    node: Optional[str]
    pool: Optional[str]

    partitions: str # Kickstart format.
    postPartitioningLocalCommands: Optional[str] # Fix up nixpart.
    network: Sequence[NetworkOptions]
    disks: Sequence[DiskOptions]
    uefi: UefiOptions

    nbCpus: int
    nbCores: int
    memory: int

    startOnBoot: bool
    protectVM: bool
    hotplugFeatures: Optional[str]
    cpuLimit: Optional[int]
    cpuUnits: Optional[int]
    cpuType: str
    arch: Optional[str]
    expertArgs: Optional[str]

    usePrivateIPAddress: bool


class ProxmoxMachineOptions(MachineOptions):
    proxmox: ProxmoxOptions

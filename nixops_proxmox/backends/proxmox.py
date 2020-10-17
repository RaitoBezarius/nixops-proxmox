# -*- coding: utf-8 -*-
import time
from nixops.backends import MachineDefinition, MachineState
from nixops.nix_expr import Function, Call, RawValue, py2nix
from typing import Optional
import nixops.known_hosts
from ipaddress import ip_address, IPv4Address, IPv6Address
from itertools import dropwhile, takewhile, chain
import nixops_proxmox.proxmox_utils
from proxmoxer.core import ResourceException
from nixops.ssh_util import SSHCommandFailed
from urllib.parse import quote
from collections import defaultdict
from .options import ProxmoxMachineOptions, DiskOptions, NetworkOptions, UefiOptions

def to_prox_bool(b):
    return 1 if b else 0

def can_reach(ip):
    # TODO: try ssh.
    return not ip_address(ip).is_link_local

def first_or_none(S):
    if not S:
        return None

    return S.pop()

def first_reachable_or_none(S):
    # TODO: compute.
    return first_or_none(S)

class VirtualMachineDefinition(MachineDefinition):
    """Definition of a Proxmox VM"""

    config: ProxmoxMachineOptions

    @classmethod
    def get_type(cls):
        return "proxmox"

    def __init__(self, name, config):
        super().__init__(name, config)

        for key in ('serverUrl', 'username', 'tokenName',
                'tokenValue', 'password', 'useSSH', 'disks',
                'node', 'pool', 'nbCpus', 'nbCores', 'memory',
                'startOnBoot', 'protectVM', 'hotplugFeatures',
                'cpuLimit', 'cpuUnits', 'cpuType', 'arch',
                'postPartitioningLocalCommands',
                'partitions', 'expertArgs', 'installISO', 'network',
                'uefi', 'useSSH'):
            setattr(self, key, getattr(self.config.proxmox, key))

        if not self.serverUrl:
            raise Exception("No server URL defined for Proxmox machine: {0}!".format(self.name))

    def show_type(self):
        return "{0} [{1}]".format(self.get_type(), self.serverUrl)

    def host_key_type(self):
        return (
            "ed25519"
            if nixops.util.parse_nixos_version(self.config.nixosRelease) >= ["15", "09"]
            else "dsa"
        )

class VirtualMachineState(MachineState[VirtualMachineDefinition]):
    """State of a Proxmox VM"""

    @classmethod
    def get_type(cls):
        return "proxmox"

    state = nixops.util.attr_property("state", MachineState.MISSING, int)

    public_ipv4 = nixops.util.attr_property("publicIPv4", None)
    public_ipv6 = nixops.util.attr_property("publicIPv6", None)
    private_ipv4 = nixops.util.attr_property("privateIPv4", None)
    private_ipv6 = nixops.util.attr_property("privateIPv6", None)

    public_dns_name = nixops.util.attr_property("publicDNSName", None)

    use_private_ip_address = nixops.util.attr_property(
            "proxmox.usePrivateIPAddress",
            False,
            type=bool
    )

    serverUrl = nixops.util.attr_property("proxmox.serverUrl", None)
    node = nixops.util.attr_property("proxmox.node", None)
    username = nixops.util.attr_property("proxmox.username", None)
    password = nixops.util.attr_property("proxmox.password", None)

    tokenName = nixops.util.attr_property("proxmox.tokenName", None)
    tokenValue = nixops.util.attr_property("proxmox.tokenValue", None)

    useSSH = nixops.util.attr_property("proxmox.useSSH", False)

    verifySSL = nixops.util.attr_property("proxmox.verifySSL", False)

    partitions = nixops.util.attr_property("proxmox.partitions", None)

    public_host_key = nixops.util.attr_property("proxmox.publicHostKey", None)
    private_host_key = nixops.util.attr_property("proxmox.privateHostKey", None)

    first_boot = nixops.util.attr_property(
            "proxmox.firstBoot",
            True,
            type=bool
    )
    installed = nixops.util.attr_property(
            "proxmox.installed",
            False,
            type=bool)
    partitioned = nixops.util.attr_property(
            "proxmox.partitioned",
            False,
            type=bool)


    def __init__(self, depl, name, id):
        super().__init__(depl, name, id)
        self._conn = None
        self._node = None
        self._vm = None
        self._cached_instance = None

    def _reset_state(self):
        with self.depl._db:
            self.state = MachineState.MISSING
            self.vm_id = None
            self._reset_network_knowledge()
            self.public_host_key = None
            self.private_host_key = None
            self._conn = None
            self._node = None
            self._vm = None
            self._cached_instance = None

    def _reset_network_knowledge(self):
        for ip in (self.public_ipv4,
                self.public_ipv6,
                self.private_ipv4,
                self.private_ipv6):
            if ip and self.public_host_key:
                nixops.known_hosts.remove(
                        ip,
                        self.public_host_key)

        with self.depl._db:
            self.public_ipv4 = None
            self.public_ipv6 = None
            self.private_ipv4 = None
            self.private_ipv6 = None

    def _learn_known_hosts(self, public_key: Optional[str] = None):
        if public_key is None:
            public_key = self.public_host_key
        for ip in (self.public_ipv4, self.public_ipv6,
                self.private_ipv4, self.private_ipv6):
            if ip:
                nixops.known_hosts.add(ip, public_key)

    def get_ssh_name(self):
        if self.use_private_ip_address:
            if not self.private_ipv4 and not self.private_ipv6:
                raise Exception(
                    f"Proxmox machine '{self.name}' does not have a private (v4 or v6) address (yet)")
            return self.private_ipv6 or self.private_ipv4
        else:
            if not self.public_ipv4 and not self.public_ipv6:
                raise Exception(
                        f"Proxmox machine '{self.name}' does not have a public (v4 or v6) address (yet)")
            return self.public_ipv6 or self.public_ipv4

    def get_ssh_private_key_file(self):
        if self._ssh_private_key_file:
            return self._ssh_private_key_file

    def get_ssh_flags(self, *args, **kwargs):
        file = self.get_ssh_private_key_file()
        super_flags = super(VirtualMachineState, self).get_ssh_flags(*args, **kwargs)

        return super_flags + (["-i", file] if file else []) + (["-o", "StrictHostKeyChecking=accept-new"] if self.has_temporary_key() else [])

    def get_physical_spec(self):
        return {
        }

    def get_keys(self):
        keys = super().get_keys()

        return keys

    @property
    def public_ip(self):
        return self.public_ipv6 or self.public_ipv4

    @property
    def private_ip(self):
        return self.private_ipv6 or self.public_ipv6

    def show_type(self):
        s = super(VirtualMachineState, self).show_type()
        return f"{s}"

    @property
    def resource_id(self):
        return self.vm_id

    def address_to(self, m):
        if isinstance(m, VirtualMachineState):
            return self.public_ipv6 or self.public_ipv4 # TODO: compute the shared optimal IP.

        return self.public_ipv6 or self.public_ipv4

    def _connect(self):
        if self._conn:
            return self._conn
        self._conn = nixops_proxmox.proxmox_utils.connect(
                self.serverUrl, self.username,
                password=self.password,
                token_name=self.tokenName, token_value=self.tokenValue,
                use_ssh=self.useSSH,
                verify_ssl=self.verifySSL)
        return self._conn

    def _connect_node(self, node: Optional[str] = None):
        self._node = self._connect().nodes(node or self.node)
        return self._node

    def _connect_vm(self, vm_id: Optional[int] = None):
        self._vm = self._connect_node().qemu(vm_id or self.resource_id)
        return self._vm

    def _get_instance(self, instance_id: Optional[int] = None, *, allow_missing: bool = False, update: bool = False):
        if not instance_id:
            instance_id = self.resource_id

        assert instance_id, "Cannot get instance of a non-created virtual machine!"
        if not self._cached_instance:
            try:
                instance = self._connect_vm(instance_id).status.current.get()
            except Exception as e:
                if allow_missing:
                    instance = None
                else:
                    raise

            self._cached_instance = instance
        elif update:
            self._cached_instance = self._connect_vm(instance_id).status.current.get()

        # TODO: Set start time.
        return self._cached_instance

    def _get_network_interfaces(self, instance_id: Optional[int] = None):
        if not instance_id:
            instance_id = self.resource_id

        assert instance_id, "Cannot get instance of a non-created virtual machine!"
        ins = self._get_instance(instance_id, update=True)

        assert bool(ins['agent']), "Cannot get network interfaces without QEMU Agent!"
        try:
            net_interfaces = {if_["name"]: if_ for if_ in self._connect_vm().agent.get("network-get-interfaces").get("result")}
            assert net_interfaces.get("lo") is not None, "No loopback interface in the result!"
        except Exception as e:
            return {}

        return net_interfaces

    def _execute_command_with_agent(self, command, stdin_data: str='', *, instance_id: Optional[int] = None):
        res = self._connect_vm(instance_id).agent.exec.post(**{
            "command": command,
            "input-data": stdin_data
        })

        get_status = lambda: self._connect_vm(instance_id).agent("exec-status").get(pid=int(res['pid']))
        current_status = get_status()
        while not current_status["exited"]:
            current_status = get_status()

        return current_status["exitcode"], current_status.get("out-data", "")

    def _file_write_through_agent(self, content, filename, *, instance_id: Optional[int] = None):
        self._connect_vm(instance_id).agent("file-write").post(
                content=content,
                file=filename
        )
        # TODO: ensure file exists.

    def _provision_ssh_key_through_agent(self, instance_id: Optional[int] = None):
        self.log_start("provisionning SSH key through QEMU Agent... ")
        self._execute_command_with_agent("mkdir -p /root/.ssh")
        self._file_write_through_agent(f"""# This was generated by NixOps during initial installation phase.
# Do not edit.
{self.public_host_key}""", "/root/.ssh/authorized_keys")
        self._execute_command_with_agent("chown -R root /root/.ssh")
        self._execute_command_with_agent("chmod 755 /root/.ssh/authorized_keys")
        self.log_end("provisionned")

    def _partition_disks(self, partitions, postPartitionHook: Optional[str] = None, instance_id: Optional[int] = None):
        self.log_start("partitioning disks... ")
        try:
            # Ensure /mnt is umounted.
            self.run_command("umount -R /mnt || true")
            # out = self.run_command("nixpart -L -p -", capture_stdout=True,
            #        stdin_string=partitions)
            #if postPartitionHook:
            #    out_posthook = self.run_command(postPartitionHook)
            self._file_write_through_agent(f"#!/run/current-system/sw/bin/bash\n{partitions}", "/tmp/partition.sh")
            self.run_command(f"chmod +x /tmp/partition.sh")
            out = self.run_command(f"/tmp/partition.sh", capture_stdout=True)
        except SSHCommandFailed as failed_command:
            # Require a reboot.
            if failed_command.exitcode == 100:
                self.log(failed_command.message)
                self.reboot()
                return
            else:
                raise

        self.log_end("partitioned")
        with self.depl._db:
            self.partitions = partitions
            self.fs_info = out
            self.partitioned = True

        # self._mount_disks(partitions, instance_id)
        return out

    def _mount_disks(self, partitions, instance_id: Optional[int] = None):
        assert self.partitioned, "The system has not been partitioned yet!"
        self.log_start("mounting disks... ")
        try:
            # Ensure /mnt is umounted.
            self.run_command("umount -R /mnt || true")
            out = self.run_command("nixpart -m -", capture_stdout=True,
                    stdin_string=partitions)
        except SSHCommandFailed as failed_command:
            # Require a reboot.
            if failed_command.exitcode == 100:
                self.log(failed_command.message)
                self.reboot()
                return
            else:
                raise

        self.log_end("disk mounted")
        return out

    def _configure_initial_nix(self, uefi: bool, instance_id: Optional[int] = None):
        self.log_start("generating the initial configuration... ")
        # 1. We generate the HW configuration and the standard configuration.
        out = self.run_command("nixos-generate-config --root /mnt", capture_stdout=True)
        # 2. We will override the configuration.nix
        nixos_cfg = {
            "imports": [
                RawValue("./hardware-configuration.nix")
            ],
            ("boot", "kernelParams"): [
                "console=ttyS0"
            ],
            ("services", "openssh", "enable"): True,
            ("services", "qemuGuest", "enable"): True,
            ("services", "mingetty", "autologinUser"): "root",
            ("networking", "firewall", "allowedTCPPorts"): [ 22 ],
            ("users", "users", "root"): {
                ("openssh", "authorizedKeys", "keys"): [ self.public_host_key ],
                ("initialPassword"): ""
            },
            ("users", "mutableUsers"): False
        }

        if uefi:
            nixos_cfg[("boot", "loader")] = {
                ("efi", "canTouchEfiVariables"): True,
                ("systemd-boot", "enable"): True
            }
        else:
            # Use nix2py to read self.fs_info.
            nixos_cfg[("boot", "loader", "grub", "devices")] = ""

        nixos_initial_postinstall_conf = py2nix(Function("{ config, pkgs, ... }", nixos_cfg))
        self.run_command(f"cat <<EOF > /mnt/etc/nixos/configuration.nix\n{nixos_initial_postinstall_conf}\nEOF")
        self.run_command("echo preinstall > /mnt/.install_status")
        self.log_end("initial configuration generated")
        self.log_start("installing NixOS... ")
        out = self.run_command("nixos-install", capture_stdout=True)
        self.log_end("NixOS installed")
        self.run_command("echo installed > /mnt/.install_status")

    def _wait_for_ip(self):
        self.log_start("waiting for at least a reachable IP address... ")

        def _instance_ip_ready(net_ifs):
            potential_ips = []
            for name, if_ in net_ifs.items():
                if name == "lo":
                    continue

                potential_ips.extend(if_.get('ip-addresses', []))

            if not potential_ips:
                return False

            return any((can_reach(i['ip-address']) for i in potential_ips))

        while True:
            instance = self._get_instance(update=True)
            self.log_continue(f"[{instance['status']}]")

            if instance['status'] == 'running':
                net_ifs = self._get_network_interfaces()
                if net_ifs:
                    self.log_continue(f"[{', '.join(net_ifs.keys())}]")

            if instance['status'] == "stopped":
                raise Exception(
                        f"Proxmox VM '{self.resource_id}' failed to start (state is '{instance['status']}')"
                )

            if _instance_ip_ready(net_ifs):
                break

            time.sleep(3)

        ip_addresses = list(chain.from_iterable(map(lambda i: ip_address(i['ip-address']), if_['ip-addresses']) for name, if_ in net_ifs.items() if if_['ip-addresses'] and name != "lo"))
        private_ips = {str(ip) for ip in ip_addresses if ip.is_private and not ip.is_link_local}
        public_ips = {str(ip) for ip in ip_addresses if not ip.is_private}
        ip_v6 = {str(ip) for ip in ip_addresses if isinstance(ip, IPv6Address)}
        ip_v4 = {str(ip) for ip in ip_addresses if isinstance(ip, IPv4Address)}

        with self.depl._db:
            self.private_ipv4 = first_reachable_or_none(private_ips & ip_v4)
            self.public_ipv4 = first_reachable_or_none(public_ips & ip_v4)
            self.private_ipv6 = first_reachable_or_none(private_ips & ip_v6)
            self.public_ipv6 = first_reachable_or_none(public_ips & ip_v6)
            self.ssh_pinged = False

        self.log_end(
            f"[IPv4: {self.public_ipv4} / {self.private_ipv4}][IPv6: {self.public_ipv6} / {self.private_ipv6}]")

        if not self.has_temporary_key():
            self._learn_known_hosts()

    def _ip_for_ssh_key(self):
        if self.use_private_ip_address:
            return self.private_ipv6 or self.private_ipv4
        else:
            return self.public_ipv6 or self.private_ipv6

    def has_temporary_key(self):
        return "NixOps auto-generated key" in self.public_host_key

    def _reinstall_host_key(self, key_type):
        self.log_start("reinstalling new host keys... ")
        attempts = 0

        while True:
            try:
                exitcode, new_key = self._execute_command_with_agent(f"cat /etc/ssh/ssh_host_{key_type}_key.pub")
                new_key = str(new_key).rstrip()
                if exitcode != 0:
                    raise Exception(f"Failed to read SSH host key of type '{key_type}' from Proxmox VM '{self.name}' during reinstallation")
                break
            except Exception as e:
                # TODO: backoff exp should be used here.
                attempts += 1
                if attempts >= 10:
                    raise e # bubble the error.
                self.log(f"failed to read SSH host key (attempt {attempts + 1}/10), retrying...")
                time.sleep(1)

        self._learn_known_hosts(new_key)
        self.log_end("installed")

    def create_after(self, resources, defn):
        return {}

    def _get_free_vmid(self):
        return self._connect().cluster.nextid.get()

    def _allocate_disk_image(self, filename, size, storage, vmid):
        try:
            return self._connect_node().storage(storage).content.post(
                    filename=filename,
                    size=size,
                    vmid=vmid)
        except ResourceException as e:
            if "already exists" in str(e):
                return f'{storage}:{filename}'
            else:
                raise e

    def create_instance(self, defn, vmid):
        tags = [f'{name}={value}' for name, value in {"Name": f"{self.depl.description} [{self.name}]"}.items()]
        # tags.update(defn.tags)
        # tags.update(self.get_common_tags())

        if not self.public_host_key:
            (private, public) = nixops.util.create_key_pair(
                    type=defn.host_key_type()
            )

            with self.depl._db:
                self.public_host_key = public
                self.private_host_key = private

        options = {
                'vmid': vmid,
                'name': defn.name,
                # 'tags': (','.join(tags)),
                'agent': "enabled=1,type=virtio",
                'vga': 'qxl',
                'arch': defn.arch,
                'args': defn.expertArgs,
                'bios': ("ovmf" if defn.uefi.enable else "seabios"),
                'cores': defn.nbCores or 1,
                'cpu': defn.cpuType or "cputype=kvm64",
                'cpulimit': defn.cpuLimit or 0,
                'cpuunits': defn.cpuUnits or 1024,
                'description': "NixOps-managed VM",
                'pool': defn.pool,
                'hotplug': defn.hotplugFeatures or "1",
                'memory': defn.memory,
                'onboot': to_prox_bool(defn.startOnBoot),
                'ostype': "l26", # Linux kernel 2.6 - 5.X
                'protection': to_prox_bool(defn.protectVM),
                'cdrom': defn.installISO,
                'serial0': 'socket',
                'scsihw': 'virtio-scsi-pci',
                'start': 1,
                'unique': 1,
                'archive': 0,
        }

        for index, net in enumerate(defn.network):
            options[f"net{index}"] = (",".join(
            [
                f"model={net.model}",
                f"bridge={net.bridge}"
            ]
            + ([f"tag={net.tag}"] if net.tag else [])
            + ([f"trunks={';'.join(net.trunks)}"] if net.trunks else [])))

            if net.ip:
                ipConfig = []
                if net.ip.v4:
                    ipConfig.append(f"gw={net.ip.v4.gateway}")
                    ipConfig.append(f"ip={net.ip.v4.address}/{net.ip.v4.prefixLength}")
                if net.ip.v6:
                    ipConfig.append(f"gw6={net.ip.v6.gateway}")
                    ipConfig.append(f"ip6={net.ip.v6.address}/{net.ip.v6.prefixLength}")
                if ipConfig:
                    options[f"ipconfig{index}"] = ",".join(ipConfig)


        max_indexes = defaultdict(lambda: 0)
        for index, disk in enumerate(defn.disks):
            filename = f"vm-{vmid}-disk-{index}"
            options[f"scsi{index}"] = (",".join([
                f"file={disk.volume}:{filename}",
                f"size={disk.size}",
                f"ssd={1 if disk.enableSSDEmulation else 0}",
                f"discard={'on' if disk.enableDiscard else 'ignore'}"
            ]
            + ([f"aio={disk.aio}"] if disk.aio else [])))
            self._allocate_disk_image(filename, disk.size, disk.volume, vmid)
            max_indexes[disk.volume] += 1

        if defn.uefi:
            filename = f'vm-{vmid}-disk-{max_indexes[defn.uefi.volume] + 1}'
            options['efidisk0'] = f'{defn.uefi.volume}:{filename}'
            self._allocate_disk_image(filename,
                    '4M',
                    defn.uefi.volume,
                    vmid)

        return vmid, self._connect_node().qemu.post(**options)

    def _qemu_agent_is_running(self):
        try:
            self._execute_command_with_agent("true")
            return True
        except Exception as e:
            if "not running" in str(e):
                return False
            else:
                raise e

    def is_in_live_cd(self):
        return bool(self._execute_command_with_agent("test -e /.install_status")[0])

    def wait_for_running(self):
        instance = self._get_instance(update=True)
        while instance['status'] != 'running':
            time.sleep(1)
            instance = self._get_instance(update=True)

    def wait_for_qemu_agent(self):
        self.wait_for_running()
        while not self._qemu_agent_is_running():
            time.sleep(1)

    def _postinstall(self, key_type, check):
        # Re-install new host key.
        self._reinstall_host_key(key_type)
        self.write_ssh_private_key(self.private_host_key)
        # Ensure we have SSH.
        self.wait_for_ssh(check=check)
        self.run_command("echo postinstall > /.install_status")
        self.installed = True
        self.state = self.UP

    def after_activation(self, defn):
        pass

    def create(self, defn: VirtualMachineDefinition, check, allow_reboot, allow_recreate):
        if self.state != self.UP:
            check = True

        self.set_common_state(defn)

        self.serverUrl = defn.serverUrl
        assert self.serverUrl is not None, "There is no Proxmox server URL set, set 'deployment.proxmox.serverUrl'"

        self.username = defn.username
        self.password = defn.password

        self.useSSH = defn.useSSH

        nodes = self._connect().nodes.get()
        assert len(nodes) == 1, "There is no node or multiple nodes, ensure you set 'deployment.proxmox.node' or verify your Proxmox cluster."
        self.node = defn.node or nodes[0]['node']

        # self.private_key_file = defn.private_key or None

        if self.resource_id and allow_reboot:
            self.stop()
            check = True

        if self.vm_id and check:
            instance = self._get_instance(allow_missing=True)

            if instance is None:
                if not allow_recreate:
                    raise Exception(
                            f"Proxmox VM '{self.name}' went away; use '--allow-recreate' to create a new one")

                    self.log(
                            f"Proxmox VM '{self.name}' went away (state: '{instance['status'] if instance else 'gone'}', will recreate")
                    self._reset_state()
            elif instance.get("status") == "stopped":
                self.log(f"Proxmox VM '{self.name}' was stopped, restarting...")
                # Change the memory allocation.
                self._reset_network_knowledge()
                self.start()

        # Create the QEMU.
        if not self.resource_id:
            created = False
            while not created:
                vmid = self._get_free_vmid()
                self.log(
                        f"creating the Proxmox VM (in node {self.node}, free supposedly VM id: {vmid}, memory {defn.memory} MiB)...")
                try:
                    vmid, instance = self.create_instance(defn, vmid)
                    created = True
                except Exception as e:
                    if "already exist" in str(e):
                        self.log(
                            f"vmid collision, trying another one.")
                    else:
                        print('Failure', e)


            with self.depl._db:
                self.vm_id = int(vmid)
                self.memory = defn.memory
                self.cpus = defn.nbCpus
                self.cores = defn.nbCores
                self.state = self.RESCUE

        if self.state not in (self.UP, self.RESCUE) or check:
            while True:
                if self._get_instance(allow_missing=True):
                    break
                self.log(
                    f"Proxmox VM instance '{self.vm_id}' not known yet, waiting...")
                time.sleep(3)

        instance = self._get_instance()
        # common_tags = dict(defn.tags)
        #if defn.owners:
        #    common_tags["Owners"] = ", ".join(defn.owners)
        # self.update_tags(self.vm_id, user_tags=common_tags, check=check)

        self.wait_for_qemu_agent()
        self.state = self.RESCUE if self.is_in_live_cd() else self.UP

        # provision ourselves through agent only if we are in a live CD.
        if self.state == self.RESCUE:
            self.log("In live CD (rescue mode)")
            self._provision_ssh_key_through_agent()
            self.write_ssh_private_key(self.private_host_key)
            time.sleep(1) # give some time to SSH/IP to be ready.

        if self.public_ip or (self.use_private_ip_address and not self.private_ip) or check:
            self._wait_for_ip()
            time.sleep(1)

        if self.state == self.RESCUE:
            self.wait_for_ssh(check=check)
            # Partition table changed.
            if self.partitions and self.partitions != defn.partitions:
                # TODO: use remapper.
                if self.depl.logger.confirm("Partition table changed, do you want to re-run the partitionning phase?"):
                    self.partitioned = False

            if self.partitioned:
                self._partition_disks(defn.partitions, defn.postPartitioningLocalCommands)
            else:
                rebooted = self._partition_disks(defn.partitions, defn.postPartitioningLocalCommands)
                if rebooted:
                    time.sleep(1)
                    self._provision_ssh_key_through_agent()
                    self.write_ssh_private_key(self.private_host_key)
                    self.wait_for_ssh(check=check)
            self._configure_initial_nix(defn.uefi.enable)
            self.reboot()
            time.sleep(1)
            self.wait_for_qemu_agent()
            self._postinstall(defn.host_key_type(), check)

        # Maybe, we installed but the process has crashed before.
        if self.state != self.RESCUE and not self.installed:
            self._postinstall(defn.host_key_type(), check)

        if self.first_boot and self.installed:
            self.first_boot = False

        self.write_ssh_private_key(self.private_host_key)

    def destroy(self, wipe=False):
        if not self.vm_id:
            return True

        if not self.depl.logger.confirm(
                f"Are you sure you want to destroy Proxmox VM '{self.name}'?"):
            return False

        if wipe:
            self.warn("wipe is not supported on Proxmox")

        self.log_start("destroying Proxmox VM...")

        instance = None
        if self.vm_id:
            instance = self._get_instance(allow_missing=True)

        if instance:
            self._connect_vm().status.stop.post()

            instance = self._get_instance(update=True)
            while instance['status'] != 'stopped':
                self.log_continue(f"[{instance['status']}]")
                time.sleep(3)
                instance = self._get_instance(update=True)

            self._connect_vm().delete(purge=1)

        self.log_end("")
        self._reset_network_knowledge()

        return True

    def stop(self, hard: bool = False):
        if not self.depl.logger.confirm(
                f"are you sure you want to stop machine '{self.name}'?"):
            return

        self.log_start("stopping Proxmox VM...")

        self._connect_vm().status.shutdown.post()
        self.state = self.STOPPING

        def check_stopped():
            instance = self._get_instance(update=True)
            self.log_continue(f"[{instance['state']}]")

            if instance['state'] == 'stopped':
                return True

            if instance['state'] != "running":
                raise Exception(
                    f"Proxmox VM '{self.vm_id}' failed to stop (state is '{instance['state']}')"
                )

            return False

        if not nixops.util.check_wait(
                check_stopped, initial=3, max_tries=300, exception=False):
            self.log_end("(timed out)")
            self.log_start("force-stopping Proxmox VM... ")
            self._connect_vm().status.stop.post()
            nixops.util.check_wait(
                    check_stopped, initial=3, max_tries=100
            )

        self.log_end("")
        self.state = self.STOPPED
        self.ssh_master = None

    def start(self):
        self.log("starting Proxmox VM machine...")

        self._connect_vm().status.start()
        self.state = self.STARTING
        with self._check_ip_changes() as addresses:
            self._wait_for_ip()
            self._warn_for_ip_changes(addresses)
        self.wait_for_ssh(check=True)
        self.send_keys()


    def _check(self, res):
        if not self.vm_id:
            res.exists = False
            return

        instance = self._get_instance(allow_missing=True)

        if instance is None:
            self.state = self.MISSING
            self.vm_id = None
            return

        res.exists = True

        if instance.state == "running":
            res.is_up = True
            res.disks_ok = True
            # TODO: check IP and adjust.
            super()._check(res)
        elif instance.state == "stopped":
            res.is_up = False
            self.state = self.STOPPED

    def reboot(self, hard: bool = False):
        self.log("rebooting Proxmox VM machine...")
        status = self._connect_vm().status
        if hard:
            status.reset.post()
        else:
            status.reboot.post()
        self.state = self.STARTING

    def get_console_output(self):
        if not self.vm_id:
            raise Exception(
                    f"Cannot get console output of non-existant machine '{self.name}'"
            )

        # TODO: connect to serial if available.
        return "(not available)"

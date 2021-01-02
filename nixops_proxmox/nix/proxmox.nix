{ config, pkgs, lib, utils, ... }:
with lib;
let
  cfg = config.deployment.proxmox;
  ipOptions = { config, ... }: {
    options = {
      gateway = mkOption {
        example = "192.168.1.254";
        type = types.nullOr types.str;
        description = "Gateway for this interface (optional)";
      };
      address = mkOption {
        example = "192.168.1.10";
        type = types.str;
        description = ''
          Static address for this interface.
          If dynamic addressing is desired, you can set:
          - dhcp for DHCP (valid for IPv4/IPv6)
          - auto for SLAAC (valid only for IPv6)

          Mandatory.
        '';
      };
      prefixLength = mkOption {
        example = 48;
        default = null;
        type = types.nullOr types.str;
        description = "Prefix length for the static address (optional)";
      };
    };
  };
  networkOptions = { config, ... }: {
    options = {
      model = mkOption {
        default = "virtio";
        example = "e1000";
        type = types.str;
        description = ''Network interface model.
          By default, virtio is the most optimal one and used.
          e1000 is an acceptable alternative.
        '';
      };
      bridge = mkOption {
        type = types.str;
        example = "vmbr0";
        description = ''Proxmox's bridge.
          It will be bridged with the virtual machine interface.
          Proxmox's bridges always starts with vmbr.

          Mandatory.
        '';
      };
      tag = mkOption {
        type = types.nullOr types.int;
        example = 100;
        default = null;
        description = "VLAN tag for this interface (optional)";
      };
      trunks = mkOption {
        default = [];
        type = types.listOf types.int;
        example = [ 100 200 300 ];
        description = "VLAN trunks for this interface (optional)";
      };
      ip.v4 = mkOption {
        type = types.nullOr (types.submodule ipOptions);
        default = null;
      };
      ip.v6 = mkOption {
        type = types.nullOr (types.submodule ipOptions);
        default = null;
      };
    };
  };
  disksOptions = { config, ... }: {
    options = {
      volume = mkOption {
        type = types.str;
        example = "local";
        description = "Storage volume where to store the disk";
      };
      size = mkOption {
        type = types.either types.int types.str;
        example = "2G";
        description = "Disk size in kilobytes (suffixes available: M, G)";
      };
      aio = mkOption {
        type = types.nullOr types.str;
        example = "native";
        default = null;
        description = "Asynchronous IO mode (native or thread)";
      };
      enableSSDEmulation = mkEnableOption "Enable SSD emulation";
      enableDiscard = mkEnableOption "Enable Discard feature";
    };
  };
  uefiOptions = { config, ... }: {
    options = {
      enable = mkEnableOption "Enable UEFI on the machine";
      volume = mkOption {
        type = types.str;
        example = "local";
        description = "Storage volume where to store the EFI disk";
      };
    };
  };
in
{
  options = {
    deployment.proxmox.serverUrl = mkOption {
      example = "https://my-proxmox-ip:8006/api/…";
      type = types.str;
      description = ''
        The Proxmox API endpoint URL.
        Mandatory.
      '';
    };
    deployment.proxmox.username = mkOption {
      type = types.str;
      description = ''
        The Proxmox account username.
        Must have the correct rights to perform the operations.
      '';
    };
    deployment.proxmox.tokenName = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Proxmox token name (API token)
      '';
    };
    deployment.proxmox.tokenValue = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Proxmox token value (API token)
      '';
    };
    deployment.proxmox.password = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Proxmox password (username/password authentication)

        It is better to use an API token or SSH authentication!
      '';
    };
    deployment.proxmox.verifySSL = mkOption {
      default = false;
      type = types.bool;
      description = ''
        Whether to verify the SSL certificate of the Proxmox node.
      '';
    };
    deployment.proxmox.useSSH = mkOption {
      default = false;
      type = types.bool;
      description = ''
        Use SSH authentication to manipulate Proxmox API.
        Require that the host is configured to SSH to Proxmox host.
      '';
    };
    deployment.proxmox.node = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Node name for Proxmox host (optional)
        By default, it will select the first one found.
      '';
    };
    deployment.proxmox.pool = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = ''
        Attach this virtual machine to the designed pool (optional)
      '';
    };
    deployment.proxmox.network = mkOption {
      type = types.listOf (types.submodule networkOptions);
      description = ''
        Network description (in order) of the virtual machine.
        At least one *reachable* network interface should be configured, otherwise NixOps will fail.
      '';
    };
    deployment.proxmox.partitions = mkOption {
      default = "";
      type = types.str;
      example = ''
        wipefs -f /dev/sda

        parted --script /dev/sda -- mklabel gpt
        parted --script /dev/sda -- mkpart primary fat32 1MiB 1024MiB
        parted --script /dev/sda -- mkpart primary btrfs 1024MiB 100%

        parted --script /dev/sda -- set 1 boot on

        mkfs.vfat /dev/sda1 -n NIXBOOT
        mkfs.btrfs /dev/sda2 -f -L nixroot

        mount -t btrfs /dev/sda2 /mnt
        mkdir -p /mnt/boot && mount /dev/sda1 /mnt/boot
      '';
      description = ''
        Bash partitioning script.
      '';
    };
    deployment.proxmox.disks = mkOption {
      type = types.listOf (types.submodule disksOptions);
      description = ''
        Disk description (in order) of the virtual machine.
        At least one usable disk should be configure, otherwise NixOps will fail.
      '';
    };
    deployment.proxmox.uefi = mkOption {
      type = types.submodule uefiOptions;
      description = ''
        UEFI configuration for the virtual machine (optional)
      '';
    };
    deployment.proxmox.nbCpus = mkOption {
      type = types.int;
      default = 1;
      description = "Amount of CPU allocated";
    };
    deployment.proxmox.nbCores = mkOption {
      type = types.int;
      default = 1;
      description = "Amount of cores allocated";
    };
    deployment.proxmox.memory = mkOption {
      type = types.int;
      default = 1024;
      description = "Amount of memory allocated in MB (note it will use the ballooning device)";
    };
    deployment.proxmox.startOnBoot = mkOption {
      type = types.bool;
      default = false;
      description = "This will make the virtual machine start at boot of the Proxmox host";
    };
    deployment.proxmox.protectVM = mkOption {
      type = types.bool;
      default = false;
      description = "This will prevent the virtual machine from accidental deletion (disk and VM)";
    };
    deployment.proxmox.hotplugFeatures = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Hotplug features string for QEMU";
    };
    deployment.proxmox.cpuLimit = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "CPU-time rate-limits";
    };
    deployment.proxmox.cpuUnits = mkOption {
      type = types.nullOr types.int;
      default = null;
      description = "CPU-units rate-limits";
    };
    deployment.proxmox.cpuType = mkOption {
      type = types.str;
      default = "kvm64";
      description = "CPU type string";
    };
    deployment.proxmox.arch = mkOption {
      type = types.nullOr (types.enum [ "aarch64" "x86_64" ]);
      default = null;
      description = ''
        QEMU architecture.

        The default value will not pass anything in the Proxmox API request.
        Usage of this option is only permitted to the <literal>root</literal>
        user by the Proxmox API and only when using username/password
        authentication.
      '';
    };
    deployment.proxmox.expertArgs = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Raw QEMU options, for experts only!";
    };
    deployment.proxmox.installISO = mkOption {
      type = types.str;
      description = ''
        Install ISO for NixOS.
        This ISO must support cloud-init initialization and QEMU agent.
        So that Proxmox can run the partitionning phase then the NixOS install.
      '';
    };
  };

  config = mkIf (config.deployment.targetEnv == "proxmox") {
    nixpkgs.system = mkOverride 900 (if cfg.arch == "aarch64" then "aarch64-linux" else "x86_64-linux");
  };
}

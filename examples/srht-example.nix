{
  network.description = "sr.ht network on Proxmox"; # This is mainly inspired and built on the top of the work eadwu, please thank him !!

  git = { ... }: {
    imports = [ ./sourcehut/git.nix ];
  };

  hg = { ... }: {
    imports = [ ./sourcehut/hg.nix ];
  };

  man = { ... }: {
    imports = [ ./sourcehut/meta.nix ];
  };

  paste = { ... }: {
    imports = [ ./sourcehut/paste.nix ];
  };

  todo = { ... }: {
    imports = [ ./sourcehut/todo.nix ];
  };

  meta = { ... }: {
    imports = [ ./sourcehut/meta.nix ];
    services.sourcehut.settings = { 
      "meta.sr.ht::settings".registration = "no";
    };
  };

  defaults = { config, pkgs, ... }: {
    imports = [ ./proxmox-info.nix ./proxmox-uefi.nix ];
    deployment.targetEnv = "proxmox";

    deployment.proxmox = {
      nbCores = mkDefault 2;
      memory = mkDefault 512;
      disks = [
        ({ volume = "sata-vmdata"; size="15G"; }) # Change it to your preferred volume.
      ];
      partitions = ''
        set -x
        wipefs -f /dev/sda

        parted --script /dev/sda -- mklabel gpt
        parted --script /dev/sda -- mkpart primary fat32 1MiB 1024MiB
        parted --script /dev/sda -- mkpart primary btrfs 1024MiB -1GiB
        parted --script /dev/sda -- mkpart primary linux-swap -1GiB 100%
        parted --script /dev/sda -- set 1 boot on

        sleep 0.5

        mkfs.vfat /dev/sda1 -n NIXBOOT
        mkfs.btrfs /dev/sda2 -f -L nixroot
        mkswap /dev/sda3 -L nixswap

        swapon /dev/sda3
        mount -t btrfs -o defaults,compress=zstd /dev/sda2 /mnt
        mkdir -p /mnt/boot
        mount /dev/sda1 /mnt/boot
      '';
    };

    fileSystems = {
      "/" = {
        device = "/dev/sda2";
        fsType = "btrfs";
        options = [ "compress=zstd" "space_cache" "noatime" ];
      };
      "/boot" = {
        device = "/dev/sda1";
        fsType = "vfat";
      };
      swapDevices = [ { device = "/dev/sda3"; } ];
    };

    networking.firewall.allowedTCPPorts = [ 80 443 ];

    services.nginx = {
      enable = true;
      recommendedTlsSettings = true;
      recommendedOptimisation = true;
      recommendedGzipSettings = true;
      recommendedProxySettings = true;
    };

    services.sourcehut.enable = true;
    services.sourcehut.settings = {
      "sr.ht".site-name = "sourcehut demo on Proxmox";
      "sr.ht".site-info = config.services.sourcehut.settings."meta.sr.ht".origin;
      "sr.ht".site-blurb = "the demonstration";
      "sr.ht".environment = "production";
      "sr.ht".owner-name = "Raito";
      "sr.ht".owner-email = "";

      # nix run nixos.pwgen -c "pwgen -s 32 1"
      "sr.ht".secret-key = "IAmNotASecretKey";
      webhooks.private-key = "";

      "git.sr.ht".origin = "";
      "hg.sr.ht".origin = "";
      "man.sr.ht".origin = "";
      "paste.sr.ht".origin = "";
      "todo.sr.ht".origin = "";
      "meta.sr.ht".origin = "";
    };
  };
}

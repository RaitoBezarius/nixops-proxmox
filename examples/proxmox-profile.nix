{ config, pkgs, ... }:
{
  imports = [ ];
  deployment.proxmox = {
    profile = "default";
    node = "askeladd"; # TODO: move me in profile.
    pool = "demo-pool"; # TODO: move me in profile.
    uefi = {
      enable = true;
      volume = "sata-vmdata";
    };
    network = [
      ({ bridge = "vmbr2"; tag = 400; })
      ({ bridge = "vmbr2"; tag = 300; })
    ];
    installISO = "local:iso/Raito-NixOS.iso";
  };

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
}

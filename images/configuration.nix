{ pkgs, lib, ... }:
{
  imports = [
    <nixpkgs/nixos/modules/profiles/qemu-guest.nix>
  ];
  boot.kernelParams = [
    "console=ttyS0"
  ];

  environment.systemPackages = with pkgs; [ (python2Packages.nixpart0.overrideAttrs (attrs: {
        patches = [ ./nixpart-silence-sanity-check.patch ./nixpart-print-format.patch ];
      }))
    ];

  services.qemuGuest.enable = true;
  services.sshd.enable = true;
  networking.firewall.allowedTCPPorts = [ 22 ];
  services.mingetty.autologinUser = lib.mkDefault "root";
}

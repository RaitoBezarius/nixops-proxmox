{ pkgs, lib, ... }:
{
  imports = [
    <nixpkgs/nixos/modules/installer/cd-dvd/iso-image.nix>
    <nixpkgs/nixos/modules/profiles/qemu-guest.nix>
  ];
  boot.kernelParams = [
    "console=ttyS0"
  ];

  # TODO: if nixpart project gets ready, then well.
  # environment.systemPackages = with pkgs; [ (python2Packages.nixpart0.overrideAttrs (attrs: {
  #      patches = [ ./nixpart-silence-sanity-check.patch ./nixpart-print-format.patch ];
  #    }))
  #  ];

  # Enable QEMU Agent
  # FIXME(Ryan): Replace it by upstream once #113909 is fixed.
  services.udev.extraRules = ''
    SUBSYSTEM=="virtio-ports", ATTR{name}=="org.qemu.guest_agent.0", TAG+="systemd" ENV{SYSTEMD_WANTS}="qemu-guest-agent.service"
  '';
  systemd.services.qemu-guest-agent = {
    description = "Run the QEMU Guest Agent";
    serviceConfig = {
      RuntimeDirectory = "qemu-ga";
      ExecStart = "${pkgs.qemu.ga}/bin/qemu-ga -t /var/run/qemu-ga";
      Restart = "always";
      RestartSec = 0;
    };
  };

  services.sshd.enable = true;
  networking.firewall.allowedTCPPorts = [ 22 ];
  services.getty.autologinUser = lib.mkDefault "root";
}

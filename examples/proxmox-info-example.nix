{ config, pkgs, ... }:
{
  deployment.proxmox = {
    serverUrl = "proxmox.example.com";
    username = "root@pam";
    password = "...";
    node = "node1";
  };
}

# NixOps plugin for Proxmox (DEPRECATED)

**2023 update** : This project is now deprecated. I moved away from Proxmox and NixOps because it is difficult to maintain the desired guarantees in those ecosystems with the way Nixpkgs is moving.
If you are still interested into professional solutions for Proxmox with NixOS, please reach out to me, I have much better ideas on how to achieve interesting results with Proxmox and declarative state, unfortunately, it is hard to work on nixops-proxmox *and* NixOps (and sometimes even *Proxmox*!) at the same time. I decided to go for https://github.com/astro/microvm.nix for the future of my infrastructure while taking the problem in the other direction: make Nix expressions easy to manipulate from a web UI rather than making state be manipulated by Nix expression and an diffing engine.

This plugin enable you to deploy and provision NixOS machines on a Proxmox node, with full control over the parameters of the virtual machine.

**Warning** : It is highly unstable and being developed right now. You can see what's lacking at the bottom of this README. Do not use in production.

**2020 NixCon** : A demo will be available shorty after the talk, here and on the talk URL: <https://cfp.nixcon.org/nixcon2020/talk/7RKBTE/>

# Instructions

You would have to copy a `proxmox-info-example.nix` file to tailor to your Proxmox cluster.

Then, you can try any example which relies on a `proxmox-info.nix` using classical `nixops deploy`.

Destroy is mostly safe in the sense it will destroy only the created VMID.

# Hacking on it

```shell
nix-shell shell.nix # Get you in a shell with most of the dependencies.
poetry shell # Get you what you need.
nixops list-plugins # Ensure, proxmox is listed here.
# Go hack on it!
```

# TODO

**Nice to have but unknown** : Skip the install phase and copy closure on `/mnt` directly from the live CD, so that we directly reboot on NixOS.

**High priority** :

- Investigate broken / dead states in post-installation phase (mostly due to SSH stuff)
- Better debugging
- Fix SSH authentication: broken `pvesh` when giving too much arguments.
- A better partitioning mechanism (nixpart is broken atm, blivet is hard to package in NixOS, etc.)
- Automatic `fileSystems` generation through a better partitioning mechanism (<3)
- Support for full disk encryption (through `autoLuks` for example).
- Better IPv6/IPv4 selection: currently, it prefers IPv6 over IPv4 but it'd be nice to attempt to reach the VM.
- A real physical specification.
- Sound RESCUE/UP state machine.
- RESCUE operations: resize partitions, repair bootloader, etc.

**Medium priority** :

- Ensure that all authentication methods are working fine.
- Backups & snapshots.

**Low priority** :

- Containers support (`proxmox-ct` machine definition)
- Testing over a Proxmox test node.

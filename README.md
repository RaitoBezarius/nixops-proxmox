# NixOps plugin for Proxmox

This plugin enable you to deploy and provision NixOS machines on a Proxmox node, with full control over the parameters of the virtual machine.

**Warning** : It is highly unstable and being developed right now. You can see what's lacking at the bottom of this README. Do not use in production.

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

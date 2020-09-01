{
  config_exporters = { optionalAttrs, ... }: [
    (config: { proxmox = optionalAttrs (config.deployment.targetEnv == "proxmox") config.deployment.proxmox; })
  ];

  options = [
    ./proxmox.nix
  ];

  resources = { evalResources, zipAttrs, resourcesByType, ... }: {
    # TODO: storage.
  };
}

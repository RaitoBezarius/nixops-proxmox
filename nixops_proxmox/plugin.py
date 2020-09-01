import os.path
import nixops.plugins
from nixops.plugins import Plugin


class NixopsProxmoxPlugin(Plugin):
    @staticmethod
    def nixexprs():
        return [os.path.dirname(os.path.abspath(__file__)) + "/nix"]

    @staticmethod
    def load():
        return [
            "nixops_proxmox.backends.proxmox"
        ]


@nixops.plugins.hookimpl
def plugin():
    return NixopsProxmoxPlugin()

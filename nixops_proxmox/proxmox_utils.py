# -*- coding: utf-8 -*-

from proxmoxer import ProxmoxAPI
from typing import Optional

def connect(
        server_url: str,
        username: str,
        *,
        password: Optional[str] = None,
        token_name: Optional[str] = None,
        token_value: Optional[str] = None,
        verify_ssl: bool = False,
        use_ssh: bool = False):

    api = ProxmoxAPI(server_url,
            user=username,
            password=password,
            token_name=token_name,
            token_value=token_value,
            verify_ssl=verify_ssl,
            backend=('ssh_paramiko' if use_ssh else 'https'))

    # check if API is working.
    a, b = api.get_tokens()
    if not (a or b):
        raise Exception(f"Failed to connect to Proxmox server '{server_url}@{username}', verify credentials")

    return api



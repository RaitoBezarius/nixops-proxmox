{ nixpkgs ? <nixpkgs>
}:

let
  pkgs = import nixpkgs { config = {}; overlays = []; };

in rec {

  nixops-proxmox = pkgs.lib.genAttrs [ "x86_64-linux" "i686-linux" "x86_64-darwin" ] (system:
    let
      pkgs = import nixpkgs { inherit system; };
      nixops-proxmox = import ./default.nix { inherit pkgs; };
    in nixops-proxmox);

}

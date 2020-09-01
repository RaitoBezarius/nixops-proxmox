{ pkgs }:

self: super: {
  nixops = super.nixops.overridePythonAttrs (
    { nativeBuildInputs ? [], ... }: {
      format = "pyproject";
      nativeBuildInputs = nativeBuildInputs ++ [ self.poetry ];
    }
  );
  nixos-modules-contrib = super.nixos-modules-contrib.overridePythonAttrs (
    { nativeBuildInputs ? [], ... }: {
      format = "pyproject";
      nativeBuildInputs = nativeBuildInputs ++ [ self.poetry ];
    }
  );
}

{ pkgs, lib ? pkgs.lib, stdenv ? pkgs.stdenv }:

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

  /*cryptography = super.cryptography.overridePythonAttrs (
    old: {
      nativeBuildInputs = (old.nativeBuildInputs or [ ])
        ++ lib.optional (lib.versionAtLeast old.version "3.4") [ self.setuptools-rust ]
        ++ lib.optional (stdenv.buildPlatform != stdenv.hostPlatform) self.python.pythonForBuild.pkgs.cffi
        ++ lib.optional (lib.versionAtLeast old.version "3.5")
        (with pkgs.rustPlatform; [ cargoSetupHook rust.cargo rust.rustc ]);
      buildInputs = (old.buildInputs or [ ]) ++ [ pkgs.openssl ];
    } // lib.optionalAttrs (lib.versionAtLeast old.version "3.4" && lib.versionOlder old.version "3.5") {
      CRYPTOGRAPHY_DONT_BUILD_RUST = "1";
    } // lib.optionalAttrs (lib.versionAtLeast old.version "3.5") rec {
      cargoDeps =
        let
          getCargoHash = version:
            if lib.versionOlder version "3.6" then "sha256-tQoQfo+TAoqAea86YFxyj/LNQCiViu5ij/3wj7ZnYLI="
            # This hash could no longer be valid for cryptography versions
            # different from 3.6.0
            else "sha256-Y6TuW7AryVgSvZ6G8WNoDIvi+0tvx8ZlEYF5qB0jfNk=";
        in
        pkgs.rustPlatform.fetchCargoTarball {
          src = old.src;
          sourceRoot = "${old.pname}-${old.version}/${cargoRoot}";
          name = "${old.pname}-${old.version}";
          sha256 = getCargoHash old.version;
        };
      cargoRoot = "src/rust";
    }
  );*/
}

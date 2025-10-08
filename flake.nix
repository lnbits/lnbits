{
  description = "LNbits, free and open-source Lightning wallet and accounts system (uv2nix)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";

    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    build-system-pkgs.url = "github:pyproject-nix/build-system-pkgs";

    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
    uv2nix.inputs.nixpkgs.follows = "nixpkgs";
    build-system-pkgs.inputs.nixpkgs.follows = "nixpkgs";
    uv2nix.inputs.pyproject-nix.follows = "pyproject-nix";
    build-system-pkgs.inputs.pyproject-nix.follows = "pyproject-nix";
  };

  outputs = { self, nixpkgs, flake-utils, uv2nix, pyproject-nix, build-system-pkgs, ... }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ]
      (system:
        let
          pkgs = import nixpkgs { inherit system; };
          lib = pkgs.lib;

          python = pkgs.python312;

          # Read uv.lock / pyproject via uv2nix
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          # Prefer wheels when available
          uvLockedOverlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

          # Helper for extending lists safely (works if a is null)
          plus = a: b: lib.unique (((if a == null then [] else a)) ++ b);

          # Extra build inputs for troublesome sdists
          myOverrides = (final: prev: {
            # embit needs setuptools at build time
            embit = prev.embit.overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
            });

            # http-ece (pywebpush dep) needs setuptools
            "http-ece" = prev."http-ece".overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
            });

            # pyqrcode needs setuptools
            pyqrcode = prev.pyqrcode.overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
            });

            # tlv8 needs setuptools
            tlv8 = prev.tlv8.overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
            });

            # secp256k1 Python binding:
            #  - setuptools, pkg-config
            #  - cffi + pycparser
            #  - system libsecp256k1 for headers/libs
            secp256k1 = prev.secp256k1.overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [
                prev.setuptools
                pkgs.pkg-config
                prev.cffi
                prev.pycparser
              ];
              buildInputs = plus (old.buildInputs or []) [ pkgs.secp256k1 ];
              propagatedBuildInputs = plus (old.propagatedBuildInputs or []) [ prev.cffi prev.pycparser ];
              env = (old.env or { }) // { PKG_CONFIG = "${pkgs.pkg-config}/bin/pkg-config"; };
            });

            # pynostr uses setuptools-scm for versioning
            pynostr = prev.pynostr.overrideAttrs (old: {
              nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools-scm ];
            });
          });

          # Compose Python package set honoring uv.lock
          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages { inherit python; })
              .overrideScope (lib.composeManyExtensions [
                build-system-pkgs.overlays.default
                uvLockedOverlay
                myOverrides
              ]);

          projectName = "lnbits";

          # Build a venv from the locked spec (this installs the resolved wheels)
          runtimeVenv = pythonSet.mkVirtualEnv "${projectName}-env" workspace.deps.default;

          # Wrapper so `nix run` behaves like `uv run` (use local source tree for templates/static/extensions)
          lnbitsApp = pkgs.writeShellApplication {
            name = "lnbits";
            text = ''
              export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
              export REQUESTS_CA_BUNDLE=$SSL_CERT_FILE
              export PYTHONPATH="$PWD:${PYTHONPATH:-}"
              exec ${runtimeVenv}/bin/lnbits "$@"
            '';
          };

          lnbitsCliApp = pkgs.writeShellApplication {
            name = "lnbits-cli";
            text = ''
              export PYTHONPATH="$PWD:${PYTHONPATH:-}"
              exec ${runtimeVenv}/bin/lnbits-cli "$@"
            '';
          };
        in
        {
          # nix build → produces the venv in ./result
          packages.default = runtimeVenv;
          packages.${projectName} = runtimeVenv;

          # nix run . → launches via wrapper that imports from source tree
          apps.default = { type = "app"; program = "${lnbitsApp}/bin/lnbits"; };
          apps.${projectName} = self.apps.${system}.default;
          apps."${projectName}-cli" = { type = "app"; program = "${lnbitsCliApp}/bin/lnbits-cli"; };

          # dev shell with locked deps + tools
          devShells.default = pkgs.mkShell {
            packages = [
              runtimeVenv
              pkgs.uv
              pkgs.ruff
              pkgs.black
              pkgs.mypy
              pkgs.pre-commit
              pkgs.openapi-generator-cli
            ];
          };

          overlays.default = final: prev: {
            ${projectName} = self.packages.${final.stdenv.hostPlatform.system}.${projectName};
            replaceVars = prev.replaceVars or (path: vars: prev.substituteAll ({ src = path; } // vars));
          };

          # System-specific nixos modules to avoid circular dependency
          nixosModules.default = { pkgs, lib, config, ... }: {
            imports = [ "${./nix/modules/lnbits-service.nix}" ];
            nixpkgs.overlays = [ self.overlays.${system}.default ];
          };

          checks = { };
        });
}

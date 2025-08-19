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

          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          uvLockedOverlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

          myOverrides =
            let
              plus = a: b: lib.unique (a ++ b);
            in
            (final: prev: {
              embit = prev.embit.overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
              });

              "http-ece" = prev."http-ece".overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
              });

              pyqrcode = prev.pyqrcode.overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
              });

              # <<< UPDATED HERE
              secp256k1 = prev.secp256k1.overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [
                  prev.setuptools
                  pkgs.pkg-config
                  prev.cffi
                  prev.pycparser
                ];
                buildInputs = plus (old.buildInputs or []) [
                  pkgs.secp256k1
                ];
                propagatedBuildInputs = plus (old.propagatedBuildInputs or []) [
                  prev.cffi
                  prev.pycparser
                ];
                env = (old.env or { }) // {
                  PKG_CONFIG = "${pkgs.pkg-config}/bin/pkg-config";
                };
              });
              # >>>

              tlv8 = prev.tlv8.overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools ];
              });

              pynostr = prev.pynostr.overrideAttrs (old: {
                nativeBuildInputs = plus (old.nativeBuildInputs or []) [ prev.setuptools-scm ];
              });
            });

          pythonSet =
            (pkgs.callPackage pyproject-nix.build.packages { inherit python; })
              .overrideScope (lib.composeManyExtensions [
                build-system-pkgs.overlays.default
                uvLockedOverlay
                myOverrides
              ]);

          projectName = "lnbits";
          thisProject = pythonSet.${projectName};

          runtimeVenv = pythonSet.mkVirtualEnv "${projectName}-env" workspace.deps.default;
          appDrv = pythonSet.toPythonApplication thisProject;
        in
        {
          packages.default = runtimeVenv;
          packages.${projectName} = runtimeVenv;

          apps.default = { type = "app"; program = "${appDrv}/bin/lnbits"; };
          apps.${projectName} = self.apps.${system}.default;

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

          nixosModules.default = { pkgs, lib, config, ... }: {
            imports = [ "${./nix/modules/lnbits-service.nix}" ];
            nixpkgs.overlays = [ self.overlays.default ];
          };

          checks = { };
        });
}

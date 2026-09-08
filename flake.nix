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

          # wasmtime's `py3-none-any` wheel contains a Windows binary. Select
          # the wheel matching the Nix host instead of accepting that wheel.
          wasmtimeWheel = {
            x86_64-linux = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/a2/92/e144fcf578fc394678c24b042efe45f3b0614acdb87ea95d8b839b208842/wasmtime-48.0.0-py3-none-manylinux1_x86_64.whl";
              hash = "sha256-WFRNU5BT3/e9TPMMQNelQIYtaDATwN+mukagY/W2gvc=";
            };
            aarch64-linux = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/1c/c3/a957b226979daaeb09ec024562e9aac05e475a954537e6f150eb60bca84d/wasmtime-48.0.0-py3-none-manylinux2014_aarch64.whl";
              hash = "sha256-JvzjYT/vvimijp1lncozJugAWThY5XWMrQhuuAKzt2Y=";
            };
            x86_64-darwin = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/89/93/911434c6c4406e6979b6cb67ba889c85633ff8d92eb0cb569fec6e2a43f7/wasmtime-48.0.0-py3-none-macosx_10_13_x86_64.whl";
              hash = "sha256-UOHqgaO+xTfQDgdnIt/cSJeKVuokYZ2BU6ofdbEXlrk=";
            };
            aarch64-darwin = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/dc/a6/91c9c19ed7f8e164f4db6405d872c9397be9f53e4f325d0adcd5e67598f4/wasmtime-48.0.0-py3-none-macosx_11_0_arm64.whl";
              hash = "sha256-6mmImjxRcC6dpfX0QQJ8qTT3dY+JJqTtFnsNaHfwkug=";
            };
          }.${system};

          # uv2nix does not consider nostr-sdk's macOS 11 wheels compatible
          # with the pinned Darwin platform, despite them being in uv.lock.
          nostrSdkDarwinWheel = {
            x86_64-darwin = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/9a/a8/3defda5f31dc639d5003c6b96389407637a7a0355e9aa14aceb0feac60db/nostr_sdk-0.44.8-cp39-abi3-macosx_11_0_x86_64.whl";
              hash = "sha256-7xppz1T7yGR9Wnt6Hnek0MgXYe766hMjxT2BUjl0xIg=";
            };
            aarch64-darwin = pkgs.fetchurl {
              url = "https://files.pythonhosted.org/packages/6b/59/df089c9ca3f683c3245c6aeb55b76e8933ebb33168b6436c29da24f1040b/nostr_sdk-0.44.8-cp39-abi3-macosx_11_0_arm64.whl";
              hash = "sha256-14FSbaCVUKjKexGr8O4nC9pT+r4ZGiq/yIUd0fP0I1w=";
            };
          };

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

            wasmtime = prev.wasmtime.overrideAttrs (_old: {
              src = wasmtimeWheel;
            });
          } // lib.optionalAttrs pkgs.stdenv.isDarwin {
            "nostr-sdk" = final.stdenv.mkDerivation {
              pname = "nostr-sdk";
              version = "0.44.8";
              src = nostrSdkDarwinWheel.${system};
              dontStrip = true;
              nativeBuildInputs = [ final.pyprojectWheelHook ];
              passthru = {
                dependencies = { };
                optional-dependencies = { };
                dependency-groups = { };
                format = "wheel";
              };
            };
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

          # Linux distributions include every optional wallet backend, matching
          # the AppImage and Docker builds. Darwin retains the core dependency set.
          runtimeDeps =
            if pkgs.stdenv.isLinux then workspace.deps.optionals
            else workspace.deps.default;
          runtimeVenv = pythonSet.mkVirtualEnv "${projectName}-env" runtimeDeps;

          sitePackages = "${runtimeVenv}/lib/python${python.pythonVersion}/site-packages";

          # Preserve source-checkout behavior, but make installed Nix packages
          # self-contained when launched from any other directory.
          lnbitsLauncher = pkgs.writeText "lnbits-nix-launcher.py" ''
            import os
            import sys
            from pathlib import Path

            from dotenv import load_dotenv

            launch_dir = Path.cwd()
            load_dotenv(launch_dir / ".env", override=False)

            source_package = launch_dir / "lnbits"
            if (source_package / "static").is_dir() and (source_package / "templates").is_dir():
                sys.path.insert(0, str(launch_dir))
            else:
                os.environ.setdefault("LNBITS_DATA_FOLDER", str(launch_dir / "data"))
                os.environ.setdefault("LNBITS_EXTENSIONS_PATH", str(launch_dir / "lnbits"))
                for setting in ("LNBITS_DATA_FOLDER", "LNBITS_EXTENSIONS_PATH"):
                    configured_path = os.environ[setting]
                    if configured_path and not Path(configured_path).is_absolute():
                        os.environ[setting] = str(launch_dir / configured_path)
                os.chdir("${sitePackages}")

            from lnbits.server import main

            main()
          '';

          lnbitsPackage = pkgs.symlinkJoin {
            name = projectName;
            paths = [ runtimeVenv ];
            nativeBuildInputs = [ pkgs.makeWrapper ];
            postBuild = ''
              rm "$out/bin/lnbits"
              makeWrapper ${runtimeVenv}/bin/python "$out/bin/lnbits" \
                --set SSL_CERT_FILE ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt \
                --set REQUESTS_CA_BUNDLE ${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt \
                --add-flags ${lnbitsLauncher}
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
          packages.default = lnbitsPackage;
          packages.${projectName} = lnbitsPackage;

          apps.default = { type = "app"; program = "${lnbitsPackage}/bin/lnbits"; };
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

          # Preserve the existing system-specific module output path.
          nixosModules.default = { ... }: {
            imports = [ ./nix/modules/lnbits-service.nix ];
            nixpkgs.overlays = [ self.overlays.${system}.default ];
          };

          checks =
            import ./nix/tests { inherit pkgs; flake = self; };
        });
}

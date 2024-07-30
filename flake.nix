{
  description = "LNbits, free and open-source Lightning wallet and accounts system";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-24.05";
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };
  outputs = { self, nixpkgs, poetry2nix }@inputs:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forSystems = systems: f:
        nixpkgs.lib.genAttrs systems
        (system: f system (import nixpkgs { inherit system; overlays = [ poetry2nix.overlays.default self.overlays.default ]; }));
      forAllSystems = forSystems supportedSystems;
      projectName = "lnbits";
    in
    {
      overlays = {
        default = final: prev: {
          ${projectName} = self.packages.${prev.stdenv.hostPlatform.system}.${projectName};
        };
      };
      packages = forAllSystems (system: pkgs: {
        default = self.packages.${system}.${projectName};
        ${projectName} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          meta.rev = self.dirtyRev or self.rev;
          meta.mainProgram = projectName;
          overrides = pkgs.poetry2nix.overrides.withDefaults (final: prev: {
            protobuf = prev.protobuf.override { preferWheel = true; };
            ruff = prev.ruff.override { preferWheel = true; };
            wallycore = prev.wallycore.override { preferWheel = true; };
          });
        };
      });
      nixosModules = {
        default = { pkgs, lib, config, ... }: {
          imports = [ "${./nix/modules/${projectName}-service.nix}" ];
          nixpkgs.overlays = [ self.overlays.default ];
        };
      };
      checks = forAllSystems (system: pkgs:
        let
          vmTests = import ./nix/tests {
            makeTest = (import (nixpkgs + "/nixos/lib/testing-python.nix") { inherit system; }).makeTest;
            inherit inputs pkgs;
          };
        in
        pkgs.lib.optionalAttrs pkgs.stdenv.isLinux vmTests # vmTests can only be ran on Linux, so append them only if on Linux.
        //
        {
          # Other checks here...
        }
      );
    };
}

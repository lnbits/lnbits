{
  description = "LNbits, free and open-source Lightning wallet and accounts system";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
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
        (system: f system (import nixpkgs { inherit system; overlays = [ poetry2nix.overlay self.overlays.default ]; }));
      forAllSystems = forSystems supportedSystems;
      projectName = "lnbits";
    in
    {
      devShells = forAllSystems (system: pkgs: {
        default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodePackages.prettier
            poetry
          ];
        };
      });
      overlays = {
        default = final: prev: {
          ${projectName} = self.packages.${final.hostPlatform.system}.${projectName};
        };
      };
      packages = forAllSystems (system: pkgs: {
        default = self.packages.${system}.${projectName};
        ${projectName} = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
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

{ pkgs, flake }:
{
  vmTest = import ./nixos-module { inherit pkgs flake; };
}

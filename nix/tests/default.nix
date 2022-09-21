{ pkgs, makeTest, inputs }:
{
  vmTest = import ./nixos-module { inherit pkgs makeTest inputs; };
}

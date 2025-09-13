{ pkgs, flake }:
pkgs.nixosTest {
  name = "lnbits-nixos-module";
  nodes = {
    client = { config, pkgs, ... }: {
      environment.systemPackages = [ pkgs.curl ];
    };
    lnbits = { ... }: {
      imports = [ flake.nixosModules.${pkgs.system}.default ];
      services.lnbits = {
        enable = true;
        openFirewall = true;
        host = "0.0.0.0";
        env = {
          LNBITS_ADMIN_UI = "false";
        };
      };
    };
  };
  testScript = { nodes, ... }: ''
    start_all()
    lnbits.wait_for_open_port(${toString nodes.lnbits.config.services.lnbits.port})
    client.wait_for_unit("multi-user.target")
    with subtest("Check that the lnbits webserver can be reached."):
        output = client.succeed(
            "curl -sSf http://lnbits:8231/ | grep title | head -n1"
        )

        assert "<title>LNbits</title>" in output;
  '';
}

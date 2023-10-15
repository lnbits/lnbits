{ pkgs, makeTest, inputs }:
makeTest {
  name = "lnbits-nixos-module";
  nodes = {
    client = { config, pkgs, ... }: {
      environment.systemPackages = [ pkgs.curl ];
    };
    lnbits = { ... }: {
      imports = [ inputs.self.nixosModules.default ];
      services.lnbits = {
        enable = true;
        openFirewall = true;
        host = "0.0.0.0";
      };
    };
  };
  testScript = { nodes, ... }: ''
    start_all()
    lnbits.wait_for_open_port(${toString nodes.lnbits.config.services.lnbits.port})
    client.wait_for_unit("multi-user.target")
    with subtest("Check that the lnbits webserver can be reached."):
        assert "<title>LNbits</title>" in client.succeed(
            "curl -sSf http:/lnbits:8231/ | grep title"
        )
  '';
}

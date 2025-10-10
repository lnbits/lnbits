{ config, pkgs, lib, ... }:

let
  defaultUser = "lnbits";
  cfg = config.services.lnbits;
  inherit (lib) mkOption mkIf types optionalAttrs literalExpression;
in

{
  options = {
    services.lnbits = {
      enable = mkOption {
        default = false;
        type = types.bool;
        description = ''
          Whether to enable the lnbits service
        '';
      };
      openFirewall = mkOption {
        type = types.bool;
        default = false;
        description = ''
          Whether to open the ports used by lnbits in the firewall for the server
        '';
      };
      package = mkOption {
        type = types.package;
        defaultText = literalExpression "pkgs.lnbits";
        default = pkgs.lnbits;
        description = ''
          The lnbits package to use.
        '';
      };
      stateDir = mkOption {
        type = types.path;
        default = "/var/lib/lnbits";
        description = ''
          The lnbits state directory
        '';
      };
      host = mkOption {
        type = types.str;
        default = "127.0.0.1";
        description = ''
          The host to bind to
        '';
      };
      port = mkOption {
        type = types.port;
        default = 8231;
        description = ''
          The port to run on
        '';
      };
      user = mkOption {
        type = types.str;
        default = "lnbits";
        description = "user to run lnbits as";
      };
      group = mkOption {
        type = types.str;
        default = "lnbits";
        description = "group to run lnbits as";
      };
      env = mkOption {
        type = types.attrsOf types.str;
        default = {};
        description = ''
          Additional environment variables that are passed to lnbits.
          Reference Variables: https://github.com/lnbits/lnbits/blob/dev/.env.example
        '';
        example = {
          LNBITS_ADMIN_UI = "true";
        };
      };
    };
  };

  config = mkIf cfg.enable {
    users.users = optionalAttrs (cfg.user == defaultUser) {
      ${defaultUser} = {
        isSystemUser = true;
        group = defaultUser;
      };
    };

    users.groups = optionalAttrs (cfg.group == defaultUser) {
      ${defaultUser} = { };
    };

    systemd.tmpfiles.rules = [
      "d ${cfg.stateDir}                            0700 ${cfg.user} ${cfg.group} - -"
      "d ${cfg.stateDir}/data                       0700 ${cfg.user} ${cfg.group} - -"
    ];

    systemd.services.lnbits = {
      enable = true;
      description = "lnbits";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      environment = lib.mkMerge [
        {
          LNBITS_DATA_FOLDER = "${cfg.stateDir}/data";
          # LNBits automatically appends '/extensions' to this path
          LNBITS_EXTENSIONS_PATH = "${cfg.stateDir}";
        }
        cfg.env
      ];
      serviceConfig = {
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = "${cfg.package}/lib/python3.12/site-packages";
        StateDirectory = "lnbits";
        ExecStart = "${cfg.package}/bin/lnbits --port ${toString cfg.port} --host ${cfg.host}";
        Restart = "always";
        PrivateTmp = true;
      };
    };
    networking.firewall = mkIf cfg.openFirewall {
      allowedTCPPorts = [ cfg.port ];
    };
  };
}

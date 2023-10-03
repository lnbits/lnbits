{ config, lib, pkgs, ... }:

with lib;
let
  options.services.lightning-loop = {
    enable = mkEnableOption "Lightning Loop, a non-custodial off/on chain bridge";
    rpcAddress = mkOption {
       type = types.str;
       default = "127.0.0.1";
       description = mdDoc "Address to listen for gRPC connections.";
    };
    rpcPort = mkOption {
       type = types.port;
       default = 11010;
       description = mdDoc "Port to listen for gRPC connections.";
    };
    restAddress = mkOption {
       type = types.str;
       default = cfg.rpcAddress;
       description = mdDoc "Address to listen for REST connections.";
    };
    restPort = mkOption {
       type = types.port;
       default = 8081;
       description = mdDoc "Port to listen for REST connections.";
    };
    package = mkOption {
      type = types.package;
      default = config.nix-bitcoin.pkgs.lightning-loop;
      defaultText = "config.nix-bitcoin.pkgs.lightning-loop";
      description = mdDoc "The package providing lightning-loop binaries.";
    };
    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/lightning-loop";
      description = mdDoc "The data directory for lightning-loop.";
    };
    proxy = mkOption {
      type = types.nullOr types.str;
      default = if cfg.tor.proxy then config.nix-bitcoin.torClientAddressWithPort else null;
      description = mdDoc "`host:port` of SOCKS5 proxy for connnecting to the loop server.";
    };
    certificate = {
      extraIPs = mkOption {
        type = with types; listOf str;
        default = [];
        example = [ "60.100.0.1" ];
        description = mdDoc ''
          Extra `subjectAltName` IPs added to the certificate.
          This works the same as loop option {option}`tlsextraip`.
        '';
      };
      extraDomains = mkOption {
        type = with types; listOf str;
        default = [];
        example = [ "example.com" ];
        description = mdDoc ''
          Extra `subjectAltName` domain names added to the certificate.
          This works the same as loop option {option}`tlsextradomain`.
        '';
      };
    };
    extraConfig = mkOption {
      type = types.lines;
      default = "";
      example = ''
        debuglevel=trace
      '';
      description = mdDoc ''
        Extra lines appended to the configuration file.
        See here for all available options:
        https://github.com/lightninglabs/loop/blob/11ab596080e9d36f1df43edbeba0702b25aa7457/loopd/config.go#L119
      '';
    };
    cli = mkOption {
      default = pkgs.writers.writeBashBin "loop" ''
        ${cfg.package}/bin/loop \
        --rpcserver ${nbLib.addressWithPort cfg.rpcAddress cfg.rpcPort} \
        --macaroonpath '${cfg.dataDir}/${network}/loop.macaroon' \
        --tlscertpath '${secretsDir}/loop-cert' "$@"
      '';
      defaultText = "(See source)";
      description = mdDoc "Binary to connect with the lightning-loop instance.";
    };
    tor = nbLib.tor;
  };

  cfg = config.services.lightning-loop;
  nbLib = config.nix-bitcoin.lib;
  secretsDir = config.nix-bitcoin.secretsDir;

  lnd = config.services.lnd;

  network = config.services.bitcoind.network;
  configFile = builtins.toFile "loop.conf" ''
    datadir=${cfg.dataDir}
    network=${network}
    rpclisten=${cfg.rpcAddress}:${toString cfg.rpcPort}
    restlisten=${cfg.restAddress}:${toString cfg.restPort}
    logdir=${cfg.dataDir}/logs
    tlscertpath=${secretsDir}/loop-cert
    tlskeypath=${secretsDir}/loop-key

    lnd.host=${nbLib.addressWithPort lnd.rpcAddress lnd.rpcPort}
    lnd.macaroonpath=${lnd.networkDir}/admin.macaroon
    lnd.tlspath=${lnd.certPath}

    ${optionalString (cfg.proxy != null) "server.proxy=${cfg.proxy}"}

    ${cfg.extraConfig}
  '';
in {
  inherit options;

  config = mkIf cfg.enable {
    services.lnd.enable = true;

    environment.systemPackages = [ cfg.package (hiPrio cfg.cli) ];

    systemd.tmpfiles.rules = [
      "d '${cfg.dataDir}' 0770 ${lnd.user} ${lnd.group} - -"
    ];

    services.lightning-loop.certificate.extraIPs = mkIf (cfg.rpcAddress != "127.0.0.1") [ "${cfg.rpcAddress}" ];

    systemd.services.lightning-loop = {
      wantedBy = [ "multi-user.target" ];
      requires = [ "lnd.service" ];
      after = [ "lnd.service" ];
      serviceConfig = nbLib.defaultHardening // {
        ExecStart = "${cfg.package}/bin/loopd --configfile=${configFile}";
        User = lnd.user;
        Restart = "on-failure";
        RestartSec = "10s";
        ReadWritePaths = [ cfg.dataDir ];
      } // nbLib.allowedIPAddresses cfg.tor.enforce;
    };

     nix-bitcoin.secrets = {
       loop-key.user = lnd.user;
       loop-cert.user = lnd.user;
     };
     nix-bitcoin.generateSecretsCmds.lightning-loop = ''
       makeCert loop '${nbLib.mkCertExtraAltNames cfg.certificate}'
    '';
  };
}

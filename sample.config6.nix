{ config, lib, pkgs, ... }:

with lib;
let
  options.services = {
    btcpayserver = {
      enable = mkEnableOption "btcpayserver, a self-hosted Bitcoin payment processor";
      address = mkOption {
        type = types.str;
        default = "127.0.0.1";
        description = mdDoc "Address to listen on.";
      };
      port = mkOption {
        type = types.port;
        default = 23000;
        description = mdDoc "Port to listen on.";
      };
      package = mkOption {
        type = types.package;
        default = if cfg.btcpayserver.lbtc then
                    config.nix-bitcoin.pkgs.btcpayserver.override { altcoinSupport = true; }
                  else
                    config.nix-bitcoin.pkgs.btcpayserver;
        defaultText = "(See source)";
        description = mdDoc "The package providing btcpayserver binaries.";
      };
      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/btcpayserver";
        description = mdDoc "The data directory for btcpayserver.";
      };
      lightningBackend = mkOption {
        type = types.nullOr (types.enum [ "clightning" "lnd" ]);
        default = null;
        description = mdDoc "The lightning node implementation to use.";
      };
      lbtc = mkOption {
        type = types.bool;
        default = false;
        description = mdDoc "Enable liquid support in btcpayserver.";
      };
      rootpath = mkOption {
        type = types.nullOr types.str;
        default = null;
        example = "btcpayserver";
        description = mdDoc "The prefix for root-relative btcpayserver URLs.";
      };
      user = mkOption {
        type = types.str;
        default = "btcpayserver";
        description = mdDoc "The user as which to run btcpayserver.";
      };
      group = mkOption {
        type = types.str;
        default = cfg.btcpayserver.user;
        description = mdDoc "The group as which to run btcpayserver.";
      };
      tor.enforce = nbLib.tor.enforce;
    };

    nbxplorer = {
      enable = mkOption {
        # This option is only used by netns-isolation
        internal = true;
        default = cfg.btcpayserver.enable;
        description = mdDoc ''
          nbxplorer is always enabled when btcpayserver is enabled.
        '';
      };
      package = mkOption {
        type = types.package;
        default = config.nix-bitcoin.pkgs.nbxplorer;
        defaultText = "config.nix-bitcoin.pkgs.nbxplorer";
        description = mdDoc "The package providing nbxplorer binaries.";
      };
      address = mkOption {
        type = types.str;
        default = "127.0.0.1";
        description = mdDoc "Address to listen on.";
      };
      port = mkOption {
        type = types.port;
        default = 24444;
        description = mdDoc "Port to listen on.";
      };
      dataDir = mkOption {
        type = types.path;
        default = "/var/lib/nbxplorer";
        description = mdDoc "The data directory for nbxplorer.";
      };
      user = mkOption {
        type = types.str;
        default = "nbxplorer";
        description = mdDoc "The user as which to run nbxplorer.";
      };
      group = mkOption {
        type = types.str;
        default = cfg.nbxplorer.user;
        description = mdDoc "The group as which to run nbxplorer.";
      };
      tor.enforce = nbLib.tor.enforce;
    };
  };

  cfg = config.services;
  nbLib = config.nix-bitcoin.lib;

  inherit (config.services) bitcoind liquidd;
in {
  inherit options;

  config = mkIf cfg.btcpayserver.enable {
    services.bitcoind = {
      enable = true;
      rpc.users.btcpayserver = {
        passwordHMACFromFile = true;
        rpcwhitelist = cfg.bitcoind.rpc.users.public.rpcwhitelist ++ [
          "setban"
          "generatetoaddress"
          "getpeerinfo"
        ];
      };
      listenWhitelisted = true;
    };
    services.clightning.enable = mkIf (cfg.btcpayserver.lightningBackend == "clightning") true;
    services.lnd = mkIf (cfg.btcpayserver.lightningBackend == "lnd") {
      enable = true;
      macaroons.btcpayserver = {
        inherit (cfg.btcpayserver) user;
        permissions = ''{"entity":"info","action":"read"},{"entity":"onchain","action":"read"},{"entity":"offchain","action":"read"},{"entity":"address","action":"read"},{"entity":"message","action":"read"},{"entity":"peers","action":"read"},{"entity":"signer","action":"read"},{"entity":"invoices","action":"read"},{"entity":"invoices","action":"write"},{"entity":"address","action":"write"}'';
      };
    };
    services.liquidd = mkIf cfg.btcpayserver.lbtc {
      enable = true;
      listenWhitelisted = true;
    };
    services.postgresql = {
      enable = true;
      ensureDatabases = [ "btcpaydb" "nbxplorer" ];
      ensureUsers = [
        {
          name = cfg.btcpayserver.user;
          ensurePermissions."DATABASE btcpaydb" = "ALL PRIVILEGES";
        }
        {
          name = cfg.nbxplorer.user;
          ensurePermissions."DATABASE nbxplorer" = "ALL PRIVILEGES";
        }
      ];
    };

    systemd.tmpfiles.rules = [
      "d '${cfg.nbxplorer.dataDir}' 0770 ${cfg.nbxplorer.user} ${cfg.nbxplorer.group} - -"
      "d '${cfg.btcpayserver.dataDir}' 0770 ${cfg.btcpayserver.user} ${cfg.btcpayserver.group} - -"
    ];

    systemd.services.nbxplorer = let
      configFile = builtins.toFile "config" ''
        network=${bitcoind.network}
        btcrpcuser=${cfg.bitcoind.rpc.users.btcpayserver.name}
        btcrpcurl=http://${nbLib.addressWithPort bitcoind.rpc.address cfg.bitcoind.rpc.port}
        btcnodeendpoint=${nbLib.addressWithPort bitcoind.address bitcoind.whitelistedPort}
        bind=${cfg.nbxplorer.address}
        port=${toString cfg.nbxplorer.port}
        ${optionalString cfg.btcpayserver.lbtc ''
          chains=btc,lbtc
          lbtcrpcuser=${liquidd.rpcuser}
          lbtcrpcurl=http://${nbLib.addressWithPort liquidd.rpc.address liquidd.rpc.port}
          lbtcnodeendpoint=${nbLib.addressWithPort liquidd.address liquidd.whitelistedPort}
        ''}
        postgres=User ID=${cfg.nbxplorer.user};Host=/run/postgresql;Database=nbxplorer
        automigrate=1
      '';
    in rec {
      wantedBy = [ "multi-user.target" ];
      requires = [ "bitcoind.service" "postgresql.service" ] ++ optional cfg.btcpayserver.lbtc "liquidd.service";
      after = requires;
      preStart = ''
        install -m 600 ${configFile} '${cfg.nbxplorer.dataDir}/settings.config'
        {
          echo "btcrpcpassword=$(cat ${config.nix-bitcoin.secretsDir}/bitcoin-rpcpassword-btcpayserver)"
          ${optionalString cfg.btcpayserver.lbtc ''
            echo "lbtcrpcpassword=$(cat ${config.nix-bitcoin.secretsDir}/liquid-rpcpassword)"
          ''}
        } >> '${cfg.nbxplorer.dataDir}/settings.config'
      '';
      serviceConfig = nbLib.defaultHardening // {
        ExecStart = ''
          ${cfg.nbxplorer.package}/bin/nbxplorer --conf=${cfg.nbxplorer.dataDir}/settings.config \
            --datadir=${cfg.nbxplorer.dataDir}
        '';
        User = cfg.nbxplorer.user;
        Restart = "on-failure";
        RestartSec = "10s";
        ReadWritePaths = [ cfg.nbxplorer.dataDir ];
        MemoryDenyWriteExecute = false;
      } // nbLib.allowedIPAddresses cfg.nbxplorer.tor.enforce;
    };

    systemd.services.btcpayserver = let
      nbExplorerUrl = "http://${nbLib.addressWithPort cfg.nbxplorer.address cfg.nbxplorer.port}/";
      nbExplorerCookie = "${cfg.nbxplorer.dataDir}/${bitcoind.makeNetworkName "Main" "RegTest"}/.cookie";
      configFile = builtins.toFile "btcpayserver-config" (''
        network=${bitcoind.network}
        bind=${cfg.btcpayserver.address}
        port=${toString cfg.btcpayserver.port}
        socksendpoint=${config.nix-bitcoin.torClientAddressWithPort}
        btcexplorerurl=${nbExplorerUrl}
        btcexplorercookiefile=${nbExplorerCookie}
        postgres=User ID=${cfg.btcpayserver.user};Host=/run/postgresql;Database=btcpaydb
      '' + optionalString (cfg.btcpayserver.rootpath != null) ''
        rootpath=${cfg.btcpayserver.rootpath}
      '' + optionalString (cfg.btcpayserver.lightningBackend == "clightning") ''
        btclightning=type=clightning;server=unix:///${cfg.clightning.dataDir}/${bitcoind.makeNetworkName "bitcoin" "regtest"}/lightning-rpc
      '' + optionalString (cfg.btcpayserver.lightningBackend == "lnd")
        (
          "btclightning=type=lnd-rest;" +
          "server=https://${cfg.lnd.restAddress}:${toString cfg.lnd.restPort}/;" +
          "macaroonfilepath=/run/lnd/btcpayserver.macaroon;" +
          "certfilepath=${config.services.lnd.certPath}" +
          "\n"
        )
      + optionalString cfg.btcpayserver.lbtc ''
        chains=btc,lbtc
        lbtcexplorerurl=${nbExplorerUrl}
        lbtcexplorercookiefile=${nbExplorerCookie}
      '');
    in let self = {
      wantedBy = [ "multi-user.target" ];
      requires = [ "nbxplorer.service" "postgresql.service" ]
                 ++ optional (cfg.btcpayserver.lightningBackend != null) "${cfg.btcpayserver.lightningBackend}.service";
      after = self.requires;
      serviceConfig = nbLib.defaultHardening // {
        ExecStart = ''
          ${cfg.btcpayserver.package}/bin/btcpayserver --conf=${configFile} \
            --datadir='${cfg.btcpayserver.dataDir}'
        '';
        User = cfg.btcpayserver.user;
        # Also restart after the program has exited successfully.
        # This is required to support restarting from the web interface after
        # interactive plugin installation.
        # Restart rate limiting is implemented via the `startLimit*` options below.
        Restart = "always";
        ReadWritePaths = [ cfg.btcpayserver.dataDir ];
        MemoryDenyWriteExecute = false;
      } // nbLib.allowedIPAddresses cfg.btcpayserver.tor.enforce;
      startLimitIntervalSec = 30;
      startLimitBurst = 10;
    }; in self;

    users.users.${cfg.nbxplorer.user} = {
      isSystemUser = true;
      group = cfg.nbxplorer.group;
      extraGroups = [ "bitcoinrpc-public" ]
                    ++ optional cfg.btcpayserver.lbtc liquidd.group;
      home = cfg.nbxplorer.dataDir;
    };
    users.groups.${cfg.nbxplorer.group} = {};
    users.users.${cfg.btcpayserver.user} = {
      isSystemUser = true;
      group = cfg.btcpayserver.group;
      extraGroups = [ cfg.nbxplorer.group ]
                    ++ optional (cfg.btcpayserver.lightningBackend == "clightning") cfg.clightning.user;
      home = cfg.btcpayserver.dataDir;
    };
    users.groups.${cfg.btcpayserver.group} = {};

    nix-bitcoin.secrets = {
      bitcoin-rpcpassword-btcpayserver = {
        user = cfg.bitcoind.user;
        group = cfg.nbxplorer.group;
      };
      bitcoin-HMAC-btcpayserver.user = cfg.bitcoind.user;
    };
    nix-bitcoin.generateSecretsCmds.btcpayserver = ''
      makeBitcoinRPCPassword btcpayserver
    '';
  };
}

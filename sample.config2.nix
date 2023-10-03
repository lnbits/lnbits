{ config, lib, pkgs, ... }:

with lib;
let
  options.services.lnd = {
    enable = mkEnableOption "Lightning Network daemon, a Lightning Network implementation in Go";
    address = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = mdDoc "Address to listen for peer connections";
    };
    port = mkOption {
      type = types.port;
      default = 9735;
      description = mdDoc "Port to listen for peer connections";
    };
    rpcAddress = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = mdDoc "Address to listen for RPC connections.";
    };
    rpcPort = mkOption {
      type = types.port;
      default = 10009;
      description = mdDoc "Port to listen for gRPC connections.";
    };
    restAddress = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = mdDoc "Address to listen for REST connections.";
    };
    restPort = mkOption {
      type = types.port;
      default = 8080;
      description = mdDoc "Port to listen for REST connections.";
    };
    dataDir = mkOption {
      type = types.path;
      default = "/var/lib/lnd";
      description = mdDoc "The data directory for LND.";
    };
    networkDir = mkOption {
      readOnly = true;
      default = "${cfg.dataDir}/chain/bitcoin/${bitcoind.network}";
      description = mdDoc "The network data directory.";
    };
    tor-socks = mkOption {
      type = types.nullOr types.str;
      default = if cfg.tor.proxy then config.nix-bitcoin.torClientAddressWithPort else null;
      description = mdDoc "Socks proxy for connecting to Tor nodes";
    };
    macaroons = mkOption {
      default = {};
      type = with types; attrsOf (submodule {
        options = {
          user = mkOption {
            type = types.str;
            description = mdDoc "User who owns the macaroon.";
          };
          permissions = mkOption {
            type = types.str;
            example = ''
              {"entity":"info","action":"read"},{"entity":"onchain","action":"read"}
            '';
            description = mdDoc "List of granted macaroon permissions.";
          };
        };
      });
      description = mdDoc ''
        Extra macaroon definitions.
      '';
    };
    certificate = {
      extraIPs = mkOption {
        type = with types; listOf str;
        default = [];
        example = [ "60.100.0.1" ];
        description = mdDoc ''
          Extra `subjectAltName` IPs added to the certificate.
          This works the same as lnd option {option}`tlsextraip`.
        '';
      };
      extraDomains = mkOption {
        type = with types; listOf str;
        default = [];
        example = [ "example.com" ];
        description = mdDoc ''
          Extra `subjectAltName` domain names added to the certificate.
          This works the same as lnd option {option}`tlsextradomain`.
        '';
      };
    };
    extraConfig = mkOption {
      type = types.lines;
      default = "";
      example = ''
        autopilot.active=1
      '';
      description = mdDoc ''
        Extra lines appended to {file}`lnd.conf`.
        See here for all available options:
        https://github.com/lightningnetwork/lnd/blob/master/sample-lnd.conf
      '';
    };
    package = mkOption {
      type = types.package;
      default = config.nix-bitcoin.pkgs.lnd;
      defaultText = "config.nix-bitcoin.pkgs.lnd";
      description = mdDoc "The package providing lnd binaries.";
    };
    cli = mkOption {
      default = pkgs.writers.writeBashBin "lncli"
        # Switch user because lnd makes datadir contents readable by user only
        ''
          ${runAsUser} ${cfg.user} ${cfg.package}/bin/lncli \
            --rpcserver ${cfg.rpcAddress}:${toString cfg.rpcPort} \
            --tlscertpath '${cfg.certPath}' \
            --macaroonpath '${networkDir}/admin.macaroon' "$@"
        '';
      defaultText = "(See source)";
      description = mdDoc "Binary to connect with the lnd instance.";
    };
    getPublicAddressCmd = mkOption {
      type = types.str;
      default = "";
      description = mdDoc ''
        Bash expression which outputs the public service address to announce to peers.
        If left empty, no address is announced.
      '';
    };
    user = mkOption {
      type = types.str;
      default = "lnd";
      description = mdDoc "The user as which to run LND.";
    };
    group = mkOption {
      type = types.str;
      default = cfg.user;
      description = mdDoc "The group as which to run LND.";
    };
    certPath = mkOption {
      readOnly = true;
      default = "${secretsDir}/lnd-cert";
      description = mdDoc "LND TLS certificate path.";
    };
    tor = nbLib.tor;
  };

  cfg = config.services.lnd;
  nbLib = config.nix-bitcoin.lib;
  secretsDir = config.nix-bitcoin.secretsDir;
  runAsUser = config.nix-bitcoin.runAsUserCmd;
  lndinit = "${config.nix-bitcoin.pkgs.lndinit}/bin/lndinit";

  bitcoind = config.services.bitcoind;

  bitcoindRpcAddress = nbLib.address bitcoind.rpc.address;
  networkDir = cfg.networkDir;
  configFile = pkgs.writeText "lnd.conf" ''
    datadir=${cfg.dataDir}
    logdir=${cfg.dataDir}/logs
    tlscertpath=${cfg.certPath}
    tlskeypath=${secretsDir}/lnd-key

    listen=${toString cfg.address}:${toString cfg.port}
    rpclisten=${cfg.rpcAddress}:${toString cfg.rpcPort}
    restlisten=${cfg.restAddress}:${toString cfg.restPort}

    bitcoin.${bitcoind.network}=1
    bitcoin.active=1
    bitcoin.node=bitcoind

    ${optionalString (cfg.tor.proxy) "tor.active=true"}
    ${optionalString (cfg.tor-socks != null) "tor.socks=${cfg.tor-socks}"}

    bitcoind.rpchost=${bitcoindRpcAddress}:${toString bitcoind.rpc.port}
    bitcoind.rpcuser=${bitcoind.rpc.users.${rpcUser}.name}
    bitcoind.zmqpubrawblock=${zmqHandleSpecialAddress bitcoind.zmqpubrawblock}
    bitcoind.zmqpubrawtx=${zmqHandleSpecialAddress bitcoind.zmqpubrawtx}

    wallet-unlock-password-file=${secretsDir}/lnd-wallet-password

    ${cfg.extraConfig}
  '';

  zmqHandleSpecialAddress = builtins.replaceStrings [ "0.0.0.0" "[::]" ] [ "127.0.0.1" "[::1]" ];

  isPruned = bitcoind.prune > 0;
  # When bitcoind pruning is enabled, lnd requires non-public RPC commands `getpeerinfo`, `getnodeaddresses`
  # to fetch missing blocks from peers (implemented in btcsuite/btcwallet/chain/pruned_block_dispatcher.go)
  rpcUser = if isPruned then "lnd" else "public";
in {

  inherit options;

  config = mkIf cfg.enable (mkMerge [ {
    assertions = [
      { assertion =
          !(config.services ? clightning)
          || !config.services.clightning.enable
          || config.services.clightning.port != cfg.port;
        message = ''
          LND and clightning can't both bind to lightning port 9735. Either
          disable LND/clightning or change services.clightning.port or
          services.lnd.port to a port other than 9735.
        '';
      }
    ];

    services.bitcoind = {
      enable = true;

      # Increase rpc thread count due to reports that lightning implementations fail
      # under high bitcoind rpc load
      rpc.threads = 16;

      zmqpubrawblock = mkDefault "tcp://${bitcoindRpcAddress}:28332";
      zmqpubrawtx = mkDefault "tcp://${bitcoindRpcAddress}:28333";
    };

    environment.systemPackages = [ cfg.package (hiPrio cfg.cli) ];

    systemd.tmpfiles.rules = [
      "d '${cfg.dataDir}' 0770 ${cfg.user} ${cfg.group} - -"
    ];

    services.lnd.certificate.extraIPs = mkIf (cfg.rpcAddress != "127.0.0.1") [ "${cfg.rpcAddress}" ];

    systemd.services.lnd = {
      wantedBy = [ "multi-user.target" ];
      requires = [ "bitcoind.service" ];
      after = [ "bitcoind.service" ];
      preStart = ''
        install -m600 ${configFile} '${cfg.dataDir}/lnd.conf'
        {
          echo "bitcoind.rpcpass=$(cat ${secretsDir}/bitcoin-rpcpassword-${rpcUser})"
          ${optionalString (cfg.getPublicAddressCmd != "") ''
            echo "externalip=$(${cfg.getPublicAddressCmd})"
          ''}
        } >> '${cfg.dataDir}/lnd.conf'

        if [[ ! -f ${networkDir}/wallet.db ]]; then
          seed='${cfg.dataDir}/lnd-seed-mnemonic'

          if [[ ! -f "$seed" ]]; then
            echo "Create lnd seed"
            (umask u=r,go=; ${lndinit} gen-seed > "$seed")
          fi

          echo "Create lnd wallet"
          ${lndinit} -v init-wallet \
            --file.seed="$seed" \
            --file.wallet-password='${secretsDir}/lnd-wallet-password' \
            --init-file.output-wallet-dir='${cfg.networkDir}'
        fi
      '';
      serviceConfig = nbLib.defaultHardening // {
        Type = "notify";
        RuntimeDirectory = "lnd"; # Only used to store custom macaroons
        RuntimeDirectoryMode = "711";
        ExecStart = "${cfg.package}/bin/lnd --configfile='${cfg.dataDir}/lnd.conf'";
        User = cfg.user;
        TimeoutSec = "15min";
        Restart = "on-failure";
        RestartSec = "10s";
        ReadWritePaths = [ cfg.dataDir ];
        ExecStartPost = let
          curl = "${pkgs.curl}/bin/curl -fsS --cacert ${cfg.certPath}";
          restUrl = "https://${nbLib.addressWithPort cfg.restAddress cfg.restPort}/v1";
        in
          # Setting macaroon permissions for other users needs root permissions
          nbLib.rootScript "lnd-create-macaroons" ''
            umask ug=r,o=
            ${lib.concatMapStrings (macaroon: ''
              echo "Create custom macaroon ${macaroon}"
              macaroonPath="$RUNTIME_DIRECTORY/${macaroon}.macaroon"
              ${curl} \
                -H "Grpc-Metadata-macaroon: $(${pkgs.xxd}/bin/xxd -ps -u -c 99999 '${networkDir}/admin.macaroon')" \
                -X POST \
                -d '{"permissions":[${cfg.macaroons.${macaroon}.permissions}]}' \
                ${restUrl}/macaroon |\
                ${pkgs.jq}/bin/jq -c '.macaroon' | ${pkgs.xxd}/bin/xxd -p -r > "$macaroonPath"
              chown ${cfg.macaroons.${macaroon}.user}: "$macaroonPath"
            '') (attrNames cfg.macaroons)}
          '';
      } // nbLib.allowedIPAddresses cfg.tor.enforce;
    };

    users.users.${cfg.user} = {
      isSystemUser = true;
      group = cfg.group;
      extraGroups = [ "bitcoinrpc-public" ];
      home = cfg.dataDir; # lnd creates .lnd dir in HOME
    };
    users.groups.${cfg.group} = {};
    nix-bitcoin.operator = {
      groups = [ cfg.group ];
      allowRunAsUsers = [ cfg.user ];
    };

    nix-bitcoin.secrets = {
      lnd-wallet-password.user = cfg.user;
      lnd-key.user = cfg.user;
      lnd-cert.user = cfg.user;
      lnd-cert.permissions = "444"; # world readable
    };
    # Advantages of manually pre-generating certs:
    # - Reduces dynamic state
    # - Enables deployment of a mesh of server plus client nodes with predefined certs
    nix-bitcoin.generateSecretsCmds.lnd = ''
      makePasswordSecret lnd-wallet-password
      makeCert lnd '${nbLib.mkCertExtraAltNames cfg.certificate}'
    '';
  }

  (mkIf isPruned {
    services.bitcoind.rpc.users.lnd = {
      passwordHMACFromFile = true;
      rpcwhitelist = bitcoind.rpc.users.public.rpcwhitelist ++ [
        "getpeerinfo"
        "getnodeaddresses"
      ];
    };
    nix-bitcoin.secrets = {
      bitcoin-rpcpassword-lnd.user = cfg.user;
      bitcoin-HMAC-lnd.user = bitcoind.user;
    };
    nix-bitcoin.generateSecretsCmds.lndBitcoinRPC = ''
      makeBitcoinRPCPassword lnd
    '';
  }) ]);
}

{ config, lib, pkgs, ... }:

with lib;
let
  options.nix-bitcoin.netns-isolation = {
    enable = mkEnableOption "netns isolation";

    addressblock = mkOption {
      type = types.ints.u8;
      default = 1;
      description = mdDoc ''
        The address block N in 169.254.N.0/24, used as the prefix for netns addresses.
      '';
    };

    services = mkOption {
      default = {};
      type = types.attrsOf (types.submodule {
        options = {
          id = mkOption {
            # TODO: Assert uniqueness
            type = types.ints.between 11 255;
            description = mdDoc ''
              id for the netns, used for the IP address host part and
              for naming the interfaces. Must be unique. Must be greater than 10.
            '';
          };
          connections = mkOption {
            type = with types; listOf str;
            default = [];
          };
        };
      });
    };

    allowedUser = mkOption {
      type = types.str;
      description = mdDoc ''
        User that is allowed to execute commands in the service network namespaces.
        The user's group is also authorized.
      '';
      default = config.nix-bitcoin.operator.name;
    };

    netns = mkOption {
      readOnly = true;
      default = netns;
      description = mdDoc "Exposes netns parameters.";
    };

    bridgeIp = mkOption {
      readOnly = true;
      default = bridgeIp;
      description = mdDoc "IP of the netns bridge interface.";
    };
  };

  cfg = config.nix-bitcoin.netns-isolation;

  netns = builtins.mapAttrs (n: v: {
    inherit (v) id;
    address = "169.254.${toString cfg.addressblock}.${toString v.id}";
    availableNetns = availableNetns.${n};
    netnsName = "nb-${n}";
  }) enabledServices;

  # Symmetric netns connection matrix
  # if clightning.connections = [ "bitcoind" ]; then
  #   availableNetns.bitcoind = [ "clighting" ];
  #   and
  #   availableNetns.clighting = [ "bitcoind" ];
  #
  # TODO-EXTERNAL:
  # Although negligible for our purposes, this calculation's runtime
  # is in the order of (number of connections * number of services),
  # because attrsets and lists are fully copied on each update with '//' or '++'.
  # This can only be improved with an update in the nix language.
  #
  availableNetns = let
    # base = { clightning = [ "bitcoind" ]; ... }
    base = builtins.mapAttrs (n: v:
      builtins.filter isEnabled v.connections
    ) enabledServices;
  in
    foldl (xs: s1:
      foldl (xs: s2:
        xs // { "${s2}" = xs.${s2} ++ [ s1 ]; }
      ) xs cfg.services.${s1}.connections
    ) base (builtins.attrNames base);

  enabledServices = filterAttrs (n: v: isEnabled n) cfg.services;
  isEnabled = x: config.services.${x}.enable;

  ip = "${pkgs.iproute}/bin/ip";
  iptables = "${config.networking.firewall.package}/bin/iptables";

  bridgeIp = "169.254.${toString cfg.addressblock}.10";

  mkCliExec = service: "exec netns-exec ${netns.${service}.netnsName}";
in {
  inherit options;

  config = mkIf cfg.enable (mkMerge [

  # Base infrastructure
  {
    networking.dhcpcd.denyInterfaces = [ "nb-br" "nb-veth*" ];
    services.tor.client.socksListenAddress = {
      addr = bridgeIp;
      # Default NixOS values. These must be repeated when redefining this option.
      port = 9050;
      IsolateDestAddr = true;
    };
    services.i2pd.proto.sam.address = bridgeIp;
    networking.firewall.interfaces.nb-br.allowedTCPPorts = [
      config.services.tor.client.socksListenAddress.port
      config.services.i2pd.proto.sam.port
    ];
    boot.kernel.sysctl."net.ipv4.ip_forward" = true;

    security.wrappers.netns-exec = {
      source = config.nix-bitcoin.pkgs.netns-exec;
      capabilities = "cap_sys_admin=ep";
      owner = cfg.allowedUser;
      group = ""; # Set to the group of `owner`
      permissions = "550";
    };

    systemd.services = {
      # Due to a NixOS bug we can't currently use option `networking.bridges` to
      # setup the bridge while `networking.useDHCP` is enabled.
      nb-netns-bridge = {
        description = "nix-bitcoin netns bridge";
        wantedBy = [ "network-setup.service" ];
        partOf = [ "network-setup.service" ];
        before = [ "network-setup.service" ];
        after = [ "network-pre.target" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          ${ip} link add name nb-br type bridge
          ${ip} link set nb-br up
          ${ip} addr add ${bridgeIp}/24 brd + dev nb-br
          ${iptables} -w -t nat -A POSTROUTING -s 169.254.${toString cfg.addressblock}.0/24 -j MASQUERADE
        '';
        preStop = ''
          ${iptables} -w -t nat -D POSTROUTING -s 169.254.${toString cfg.addressblock}.0/24 -j MASQUERADE
          ${ip} link del nb-br
        '';
      };

    } //
    (let
      makeNetnsServices = n: v: let
        veth = "nb-veth-${toString v.id}";
        peer = "nb-veth-br-${toString v.id}";
        inherit (v) netnsName;
        nsenter = "${pkgs.utillinux}/bin/nsenter";
        allowedNetnsAddresses = map (available: netns.${available}.address) v.availableNetns;
        allowedAddresses = concatStringsSep ","
          ([ "127.0.0.1,${bridgeIp},${v.address}" ] ++ allowedNetnsAddresses);

        setup = ''
          ${ip} netns add ${netnsName}
          ${ip} link add ${veth} type veth peer name ${peer}
          ${ip} link set ${veth} netns ${netnsName}
          # The peer link is never used directly, so don't auto-assign an IPv6 address
          echo 1 > /proc/sys/net/ipv6/conf/${peer}/disable_ipv6
          ${ip} link set ${peer} up
          ${ip} link set ${peer} master nb-br
          exec ${nsenter} --net=/run/netns/${netnsName} ${script "in-netns" setupInNetns}
        '';

        setupInNetns = ''
          ${ip} link set lo up
          ${ip} addr add ${v.address}/24 dev ${veth}
          ${ip} link set ${veth} up
          ${ip} route add default via ${bridgeIp}

          ${iptables} -w -P INPUT DROP
          # allow return traffic to outgoing connections initiated by the service itself
          ${iptables} -w -A INPUT -m conntrack --ctstate ESTABLISHED -j ACCEPT
          ${iptables} -w -A INPUT -s ${allowedAddresses} -j ACCEPT
        '' + optionalString (config.services.${n}.tor.enforce or false) ''
          ${iptables} -w -P OUTPUT DROP
          ${iptables} -w -A OUTPUT -d ${allowedAddresses} -j ACCEPT
        '';
        script = name: src: pkgs.writers.writeDash name ''
          set -e
          ${src}
        '';
      in {
        "${n}".serviceConfig.NetworkNamespacePath = "/var/run/netns/${netnsName}";

        "netns-${n}" = rec {
          requires = [ "nb-netns-bridge.service" ];
          after = [ "nb-netns-bridge.service" ];
          requiredBy = [ "${n}.service" ];
          before = requiredBy;
          serviceConfig = {
            Type = "oneshot";
            RemainAfterExit = true;
            ExecStart = script "setup" setup;
          };
          # Link deletion is implicit in netns deletion, but it sometimes only happens
          # after `netns delete` finishes. Add an extra `link del` to ensure that
          # the link is deleted before the service stops, which is needed for service
          # restart to succeed.
          preStop = ''
            ${ip} netns delete ${netnsName}
            ${ip} link del ${peer} 2> /dev/null || true
          '';

        };
      };
    in
      foldl (services: n:
        services // (makeNetnsServices n netns.${n})
      ) {} (builtins.attrNames netns)
    );
  }

  # Service-specific config
  {
    nix-bitcoin.netns-isolation.services = {
      bitcoind = {
        id = 12;
      };
      clightning = {
        id = 13;
        connections = [ "bitcoind" ];
      };
      lnd = {
        id = 14;
        connections = [ "bitcoind" ];
      };
      liquidd = {
        id = 15;
        connections = [ "bitcoind" ];
      };
      electrs = {
        id = 16;
        connections = [ "bitcoind" ];
      };
      nginx = {
        id = 21;
      };
      lightning-loop = {
        id = 22;
        connections = [ "lnd" ];
      };
      nbxplorer = {
        id = 23;
        connections = [ "bitcoind" ]
                      ++ optional config.services.btcpayserver.lbtc "liquidd";
      };
      btcpayserver = {
        id = 24;
        connections = [ "nbxplorer" ]
                      ++ optional (config.services.btcpayserver.lightningBackend == "lnd") "lnd"
                      ++ optional config.services.btcpayserver.lbtc "liquidd";
        # communicates with clightning over rpc socket
      };
      joinmarket = {
        id = 25;
        connections = [ "bitcoind" ];
      };
      joinmarket-ob-watcher = {
        id = 26;
        connections = [ "bitcoind" ];
      };
      lightning-pool = {
        id = 27;
        connections = [ "lnd" ];
      };
      charge-lnd = {
        id = 28;
        connections = [ "lnd" "electrs" ];
      };
      rtl = {
        id = 29;
        connections = let
          nodes = config.services.rtl.nodes;
        in
          optional nodes.lnd.enable "lnd" ++
          optional (nodes.lnd.enable && nodes.lnd.loop) "lightning-loop" ++
          optional nodes.clightning.enable "clightning-rest";
      };
      clightning-rest = {
        id = 30;
      };
      fulcrum = {
        id = 31;
        connections = [ "bitcoind" ];
      };
      # id = 32 reserved for the upcoming mempool module
    };

    services.bitcoind = {
      address = netns.bitcoind.address;
      rpc.address = netns.bitcoind.address;
      rpc.allowip = [
        bridgeIp # For operator user
        netns.bitcoind.address
      ] ++ map (n: netns.${n}.address) netns.bitcoind.availableNetns;
    };

    services.clightning.address = netns.clightning.address;

    services.lnd = {
      address = netns.lnd.address;
      rpcAddress = netns.lnd.address;
      restAddress = netns.lnd.address;
    };

    services.liquidd = {
      address = netns.liquidd.address;
      rpc.address = netns.liquidd.address;
      rpcallowip = [
        bridgeIp # For operator user
        netns.liquidd.address
      ] ++ map (n: netns.${n}.address) netns.liquidd.availableNetns;
    };

    services.electrs.address = netns.electrs.address;

    services.fulcrum.address = netns.fulcrum.address;

    services.lightning-loop.rpcAddress = netns.lightning-loop.address;

    services.nbxplorer.address = netns.nbxplorer.address;
    services.btcpayserver.address = netns.btcpayserver.address;

    services.joinmarket = {
      payjoinAddress = netns.joinmarket.address;
      messagingAddress = netns.joinmarket.address;
      cliExec = mkCliExec "joinmarket";
    };
    systemd.services.joinmarket-yieldgenerator = mkIf config.services.joinmarket.yieldgenerator.enable {
      serviceConfig.NetworkNamespacePath = "/var/run/netns/nb-joinmarket";
    };

    services.joinmarket-ob-watcher.address = netns.joinmarket-ob-watcher.address;

    services.lightning-pool.rpcAddress = netns.lightning-pool.address;

    services.rtl.address = netns.rtl.address;

    services.clightning-rest.address = netns.clightning-rest.address;
  }
  ]);
}

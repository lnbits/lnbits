{ config, lib, pkgs, ... }:

with lib;
let
  options.services.hardware-wallets = {
    ledger = mkOption {
      type = types.bool;
      default = false;
      description = mdDoc ''
        If enabled, the ledger udev rules will be installed.
      '';
    };
    trezor = mkOption {
      type = types.bool;
      default = false;
      description = mdDoc ''
        If enabled, the trezor udev rules will be installed.
      '';
    };
    group = mkOption {
      type = types.str;
      default = "hardware-wallets";
      description = mdDoc ''
        Group the hardware wallet udev rules apply to.
      '';
    };
  };

  cfg = config.services.hardware-wallets;
in {
  inherit options;

  config = mkMerge [
    (mkIf (cfg.ledger || cfg.trezor) {
      assertions = [
        { assertion = (config.services.bitcoind.disablewallet == null || !config.services.bitcoind.disablewallet);
          message = ''
            Hardware-Wallets are not compatible with bitcoind.disablewallet.
          '';
        }
      ];

      environment.systemPackages = [
        config.nix-bitcoin.pkgs.hwi
        # Provides lsusb for debugging
        pkgs.usbutils
      ];

      users.groups.${cfg.group} = {};
      nix-bitcoin.operator.groups = [ cfg.group ];
    })

    (mkIf cfg.ledger {
      # Ledger Nano S according to https://github.com/LedgerHQ/udev-rules/blob/master/add_udev_rules.sh
      # Don't use rules from nixpkgs because we want to use our own group.
      services.udev.packages = lib.singleton (pkgs.writeTextFile {
        name = "ledger-udev-rules";
        destination = "/etc/udev/rules.d/20-ledger.rules";
        text = ''
          SUBSYSTEMS=="usb", ATTRS{idVendor}=="2c97", ATTRS{idProduct}=="0001", MODE="0660", GROUP="${cfg.group}"
        '';
      });
    })
    (mkIf cfg.trezor {
      environment.systemPackages = [ pkgs.python3.pkgs.trezor ];
      # Don't use rules from nixpkgs because we want to use our own group.
      services.udev.packages = lib.singleton (pkgs.writeTextFile {
        name = "trezord-udev-rules";
        destination = "/etc/udev/rules.d/52-trezor.rules";
        text = ''
          # TREZOR v1 (One)
          SUBSYSTEM=="usb", ATTR{idVendor}=="534c", ATTR{idProduct}=="0001", MODE="0660", GROUP="${cfg.group}", TAG+="uaccess", SYMLINK+="trezor%n"
          KERNEL=="hidraw*", ATTRS{idVendor}=="534c", ATTRS{idProduct}=="0001", MODE="0660", GROUP="${cfg.group}", TAG+="uaccess"

          # TREZOR v2 (T)
          SUBSYSTEM=="usb", ATTR{idVendor}=="1209", ATTR{idProduct}=="53c0", MODE="0660", GROUP="${cfg.group}", TAG+="uaccess", SYMLINK+="trezor%n"
          SUBSYSTEM=="usb", ATTR{idVendor}=="1209", ATTR{idProduct}=="53c1", MODE="0660", GROUP="${cfg.group}", TAG+="uaccess", SYMLINK+="trezor%n"
          KERNEL=="hidraw*", ATTRS{idVendor}=="1209", ATTRS{idProduct}=="53c1", MODE="0660", GROUP="${cfg.group}", TAG+="uaccess"
        '';
      });
      services.trezord.enable = true;
    })
  ];
}

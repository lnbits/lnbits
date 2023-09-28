{
  imports = [
    ./nix-bitcoin.nix
    ./secrets/secrets.nix
    ./operator.nix
    ./bitcoind.nix
    ./clightning.nix
    ./clightning-plugins.nix
    ./clightning-rest.nix
    ./clightning-replication.nix
    ./lndconnect.nix
    ./btcpayserver.nix
    ./joinmarket.nix
    ./joinmarket-ob-watcher.nix
    ./hardware-wallets.nix
    ./versioning.nix
    ./security.nix
    ./onion-addresses.nix
    ./backups.nix
  ];

  disabledModules = [ "services/networking/bitcoind.nix" ];
}
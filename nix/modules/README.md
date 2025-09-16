# LNBits NixOS Installation Guide

This guide shows how to install LNBits on a fresh NixOS system.

## Quick Start (Recommended)

Add this to your NixOS configuration (`/etc/nixos/configuration.nix`):

```nix
{ config, lib, pkgs, ... }:

let
  lnbitsFlake = builtins.getFlake "github:lnbits/lnbits";
in
{
  imports = [
    # Import LNBits service module directly from GitHub
    "${lnbitsFlake}/nix/modules/lnbits-service.nix"
  ];

  # Enable flakes (required)
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Configure LNBits service
  services.lnbits = {
    enable = true;
    host = "0.0.0.0";        # Listen on all interfaces
    port = 5000;             # Default port
    openFirewall = true;     # Open firewall port automatically

    # Use package from the same flake (adjust system architecture as needed)
    package = lnbitsFlake.packages.x86_64-linux.lnbits;

    env = {
      LNBITS_ADMIN_UI = "true";
      # Configure your Lightning backend:
      # LNBITS_BACKEND_WALLET_CLASS = "LndRestWallet";
      # LND_REST_ENDPOINT = "https://localhost:8080";
      # LND_REST_CERT = "/path/to/tls.cert";
      # LND_REST_MACAROON = "/path/to/admin.macaroon";
    };
  };

  # Rebuild and switch
  # sudo nixos-rebuild switch
}
```

> **⚠️ System Architecture Note**: The examples above use `x86_64-linux`. Replace this with your system architecture:
>
> - `x86_64-linux` - Intel/AMD 64-bit Linux
> - `aarch64-linux` - ARM 64-bit Linux (e.g., Raspberry Pi 4, Apple Silicon under Linux)
> - `x86_64-darwin` - Intel Mac
> - `aarch64-darwin` - Apple Silicon Mac
>
> You can check your system with: `nix eval --impure --raw --expr 'builtins.currentSystem'`

## Alternative: Using Your Own Flake

Create a `flake.nix` for your system configuration:

```nix
{
  description = "My NixOS configuration with LNBits";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    lnbits.url = "github:lnbits/lnbits";
  };

  outputs = { self, nixpkgs, lnbits }: {
    nixosConfigurations.myserver = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";  # Adjust architecture as needed
      modules = [
        ./hardware-configuration.nix
        {
          services.lnbits = {
            enable = true;
            host = "0.0.0.0";
            port = 5000;
            openFirewall = true;
            package = lnbits.packages.x86_64-linux.lnbits;  # Adjust architecture as needed
            env = {
              LNBITS_ADMIN_UI = "true";
              # Add your Lightning backend configuration
            };
          };
        }
      ];
    };
  };
}
```

Then deploy with:

```bash
sudo nixos-rebuild switch --flake .#myserver
```

## Configuration Options

### Basic Options

- `enable`: Enable the LNBits service (default: `false`)
- `host`: Host to bind to (default: `"127.0.0.1"`)
- `port`: Port to run on (default: `8231`)
- `openFirewall`: Automatically open firewall port (default: `false`)
- `user`: User to run as (default: `"lnbits"`)
- `group`: Group to run as (default: `"lnbits"`)
- `stateDir`: State directory (default: `"/var/lib/lnbits"`)

### Environment Variables

Configure LNBits through the `env` option. Common variables:

```nix
services.lnbits.env = {
  # Admin UI
  LNBITS_ADMIN_UI = "true";

  # LND Backend Example:

  # LND
  LNBITS_BACKEND_WALLET_CLASS = "LndRestWallet";
  LND_REST_ENDPOINT = "https://localhost:8080";
  LND_REST_CERT = "/path/to/tls.cert";
  LND_REST_MACAROON = "/path/to/admin.macaroon";
};
```

See the [LNBits documentation](https://docs.lnbits.org/guide/wallets.html) for all supported backends.

## State Directory Structure

LNBits data is stored in `/var/lib/lnbits` (default) with this structure:

```
/var/lib/lnbits/
├── data/                       # Application data
│   ├── database.sqlite3        # Main database
│   ├── ext_<extension>.sqlite3 # Extension database
│   ├── images/                 # Uploaded images
│   ├── logs/                   # Log files
│   └── upgrades/               # Migration files
└── extensions/                 # Installed extensions
```

## First Time Setup

1. **Deploy the configuration:**

   ```bash
   sudo nixos-rebuild switch
   ```

2. **Check service status:**

   ```bash
   systemctl status lnbits
   ```

3. **Access the web interface:**

   ```
   http://your-server-ip:5000
   ```

4. **Follow the first-time setup wizard** to configure your Lightning backend and create your first wallet.

5. **Bonus** Add Reverse Proxy with generated SSL Cert

```nix
{
# Enable nginx
  services.nginx = {
    enable = true;

    virtualHosts."lnbits.mydomain.com" = {
      forceSSL = true;
      enableACME = true;
      locations."/" = {
        proxyPass = "http://127.0.0.1:5000";
        proxyWebsockets = true;
      };
    };
  };
}
```

## Troubleshooting

### Service won't start

```bash
# Check service logs
journalctl -u lnbits -f

# Check if port is available
ss -tlnp | grep 5000
```

### Can't access web interface

- Ensure `openFirewall = true` is set
- Check if the port is correct: `services.lnbits.port`
- Verify host binding: `services.lnbits.host = "0.0.0.0"`

## Further Reading

- [LNBits Documentation](https://docs.lnbits.org)
- [Lightning Wallet Configuration](https://docs.lnbits.org/guide/wallets.html)
- [LNBits Extensions](https://docs.lnbits.org/devs/extensions.html)

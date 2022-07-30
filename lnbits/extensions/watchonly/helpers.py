from embit.descriptor import Descriptor, Key  # type: ignore
from embit.descriptor.arguments import AllowedDerivation  # type: ignore
from embit.networks import NETWORKS  # type: ignore


def detect_network(k):
    version = k.key.version
    for network_name in NETWORKS:
        net = NETWORKS[network_name]
        # not found in this network
        if version in [net["xpub"], net["ypub"], net["zpub"], net["Zpub"], net["Ypub"]]:
            return net


def parse_key(masterpub: str) -> Descriptor:
    """Parses masterpub or descriptor and returns a tuple: (Descriptor, network)
    To create addresses use descriptor.derive(num).address(network=network)
    """
    network = None
    # probably a single key
    if "(" not in masterpub:
        k = Key.from_string(masterpub)
        if not k.is_extended:
            raise ValueError("The key is not a master public key")
        if k.is_private:
            raise ValueError("Private keys are not allowed")
        # check depth
        if k.key.depth != 3:
            raise ValueError(
                "Non-standard depth. Only bip44, bip49 and bip84 are supported with bare xpubs. For custom derivation paths use descriptors."
            )
        # if allowed derivation is not provided use default /{0,1}/*
        if k.allowed_derivation is None:
            k.allowed_derivation = AllowedDerivation.default()
        # get version bytes
        version = k.key.version
        for network_name in NETWORKS:
            net = NETWORKS[network_name]
            # not found in this network
            if version in [net["xpub"], net["ypub"], net["zpub"]]:
                network = net
                if version == net["xpub"]:
                    desc = Descriptor.from_string("pkh(%s)" % str(k))
                elif version == net["ypub"]:
                    desc = Descriptor.from_string("sh(wpkh(%s))" % str(k))
                elif version == net["zpub"]:
                    desc = Descriptor.from_string("wpkh(%s)" % str(k))
                break
        # we didn't find correct version
        if network is None:
            raise ValueError("Unknown master public key version")
    else:
        desc = Descriptor.from_string(masterpub)
        if not desc.is_wildcard:
            raise ValueError("Descriptor should have wildcards")
        for k in desc.keys:
            if k.is_extended:
                net = detect_network(k)
                if net is None:
                    raise ValueError(f"Unknown version: {k}")
                if network is not None and network != net:
                    raise ValueError("Keys from different networks")
                network = net
    return desc, network


async def derive_address(masterpub: str, num: int, branch_index=0):
    desc, network = parse_key(masterpub)
    return desc.derive(num, branch_index).address(network=network)

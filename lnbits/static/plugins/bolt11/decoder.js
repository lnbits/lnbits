//TODO - A reader MUST check that the signature is valid (see the n tagged field)
//TODO - Tagged part of type f: the fallback on-chain address should be decoded into an address format
//TODO - A reader MUST check that the SHA-2 256 in the h field exactly matches the hashed description.
//TODO - A reader MUST use the n field to validate the signature instead of performing signature recovery if a valid n field is provided.

function decode(paymentRequest) {
    let input = paymentRequest.toLowerCase();
    let splitPosition = input.lastIndexOf('1');
    let humanReadablePart = input.substring(0, splitPosition);
    let data = input.substring(splitPosition + 1, input.length - 6);
    let checksum = input.substring(input.length - 6, input.length);
    if (!verify_checksum(humanReadablePart, bech32ToFiveBitArray(data + checksum))) {
        throw 'Malformed request: checksum is incorrect'; // A reader MUST fail if the checksum is incorrect.
    }
    return {
        'human_readable_part': decodeHumanReadablePart(humanReadablePart),
        'data': decodeData(data, humanReadablePart),
        'checksum': checksum
    }
}

function decodeHumanReadablePart(humanReadablePart) {
    let prefixes = ['lnbc', 'lntb', 'lnbcrt', 'lnsb'];
    let prefix;
    prefixes.forEach(value => {
        if (humanReadablePart.substring(0, value.length) === value) {
            prefix = value;
        }
    });
    if (prefix == null) throw 'Malformed request: unknown prefix'; // A reader MUST fail if it does not understand the prefix.
    let amount = decodeAmount(humanReadablePart.substring(prefix.length, humanReadablePart.length));
    return {
        'prefix': prefix,
        'amount': amount
    }
}

function decodeData(data, humanReadablePart) {
    let date32 = data.substring(0, 7);
    let dateEpoch = bech32ToInt(date32);
    let signature = data.substring(data.length - 104, data.length);
    let tagData = data.substring(7, data.length - 104);
    let decodedTags = decodeTags(tagData);
    let value = bech32ToFiveBitArray(date32 + tagData);
    value = fiveBitArrayTo8BitArray(value, true);
    value = textToHexString(humanReadablePart).concat(byteArrayToHexString(value));
    return {
        'time_stamp': dateEpoch,
        'tags': decodedTags,
        'signature': decodeSignature(signature),
        'signing_data': value
    }
}

function decodeSignature(signature) {
    let data = fiveBitArrayTo8BitArray(bech32ToFiveBitArray(signature));
    let recoveryFlag = data[data.length - 1];
    let r = byteArrayToHexString(data.slice(0, 32));
    let s = byteArrayToHexString(data.slice(32, data.length - 1));
    return {
        'r': r,
        's': s,
        'recovery_flag': recoveryFlag
    }
}

function decodeAmount(str) {
    let multiplier = str.charAt(str.length - 1);
    let amount = str.substring(0, str.length - 1);
    if (amount.substring(0, 1) === '0') {
        throw 'Malformed request: amount cannot contain leading zeros';
    }
    amount = Number(amount);
    if (amount < 0 || !Number.isInteger(amount)) {
        throw 'Malformed request: amount must be a positive decimal integer'; // A reader SHOULD fail if amount contains a non-digit
    }

    switch (multiplier) {
        case '':
            return 'Any amount'; // A reader SHOULD indicate if amount is unspecified
        case 'p':
            return amount / 10;
        case 'n':
            return amount * 100;
        case 'u':
            return amount * 100000;
        case 'm':
            return amount * 100000000;
        default:
            // A reader SHOULD fail if amount is followed by anything except a defined multiplier.
            throw 'Malformed request: undefined amount multiplier';
    }
}

function decodeTags(tagData) {
    let tags = extractTags(tagData);
    let decodedTags = [];
    tags.forEach(value => decodedTags.push(decodeTag(value.type, value.length, value.data)));
    return decodedTags;
}

function extractTags(str) {
    let tags = [];
    while (str.length > 0) {
        let type = str.charAt(0);
        let dataLength = bech32ToInt(str.substring(1, 3));
        let data = str.substring(3, dataLength + 3);
        tags.push({
            'type': type,
            'length': dataLength,
            'data': data
        });
        str = str.substring(3 + dataLength, str.length);
    }
    return tags;
}

function decodeTag(type, length, data) {
    switch (type) {
        case 'p':
            if (length !== 52) break; // A reader MUST skip over a 'p' field that does not have data_length 52
            return {
                'type': type,
                'length': length,
                'description': 'payment_hash',
                'value': byteArrayToHexString(fiveBitArrayTo8BitArray(bech32ToFiveBitArray(data)))
            };
        case 'd':
            return {
                'type': type,
                'length': length,
                'description': 'description',
                'value': bech32ToUTF8String(data)
            };
        case 'n':
            if (length !== 53) break; // A reader MUST skip over a 'n' field that does not have data_length 53
            return {
                'type': type,
                'length': length,
                'description': 'payee_public_key',
                'value': byteArrayToHexString(fiveBitArrayTo8BitArray(bech32ToFiveBitArray(data)))
            };
        case 'h':
            if (length !== 52) break; // A reader MUST skip over a 'h' field that does not have data_length 52
            return {
                'type': type,
                'length': length,
                'description': 'description_hash',
                'value': data
            };
        case 'x':
            return {
                'type': type,
                'length': length,
                'description': 'expiry',
                'value': bech32ToInt(data)
            };
        case 'c':
            return {
                'type': type,
                'length': length,
                'description': 'min_final_cltv_expiry',
                'value': bech32ToInt(data)
            };
        case 'f':
            let version = bech32ToFiveBitArray(data.charAt(0))[0];
            if (version < 0 || version > 18) break; // a reader MUST skip over an f field with unknown version.
            data = data.substring(1, data.length);
            return {
                'type': type,
                'length': length,
                'description': 'fallback_address',
                'value': {
                    'version': version,
                    'fallback_address': data
                }
            };
        case 'r':
            data = fiveBitArrayTo8BitArray(bech32ToFiveBitArray(data));
            let pubkey = data.slice(0, 33);
            let shortChannelId = data.slice(33, 41);
            let feeBaseMsat = data.slice(41, 45);
            let feeProportionalMillionths = data.slice(45, 49);
            let cltvExpiryDelta = data.slice(49, 51);
            return {
                'type': type,
                'length': length,
                'description': 'routing_information',
                'value': {
                    'public_key': byteArrayToHexString(pubkey),
                    'short_channel_id': byteArrayToHexString(shortChannelId),
                    'fee_base_msat': byteArrayToInt(feeBaseMsat),
                    'fee_proportional_millionths': byteArrayToInt(feeProportionalMillionths),
                    'cltv_expiry_delta': byteArrayToInt(cltvExpiryDelta)
                }
            };
        default:
        // reader MUST skip over unknown fields
    }
}

function polymod(values) {
    let GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];
    let chk = 1;
    values.forEach((value) => {
        let b = (chk >> 25);
        chk = (chk & 0x1ffffff) << 5 ^ value;
        for (let i = 0; i < 5; i++) {
            if (((b >> i) & 1) === 1) {
                chk ^= GEN[i];
            } else {
                chk ^= 0;
            }
        }
    });
    return chk;
}

function expand(str) {
    let array = [];
    for (let i = 0; i < str.length; i++) {
        array.push(str.charCodeAt(i) >> 5);
    }
    array.push(0);
    for (let i = 0; i < str.length; i++) {
        array.push(str.charCodeAt(i) & 31);
    }
    return array;
}

function verify_checksum(hrp, data) {
    hrp = expand(hrp);
    let all = hrp.concat(data);
    let bool = polymod(all);
    return bool === 1;
}
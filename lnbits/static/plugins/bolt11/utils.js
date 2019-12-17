const bech32CharValues = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l';

function byteArrayToInt(byteArray) {
    let value = 0;
    for (let i = 0; i < byteArray.length; ++i) {
        value = (value << 8) + byteArray[i];
    }
    return value;
}

function bech32ToInt(str) {
    let sum = 0;
    for (let i = 0; i < str.length; i++) {
        sum = sum * 32;
        sum = sum + bech32CharValues.indexOf(str.charAt(i));
    }
    return sum;
}

function bech32ToFiveBitArray(str) {
    let array = [];
    for (let i = 0; i < str.length; i++) {
        array.push(bech32CharValues.indexOf(str.charAt(i)));
    }
    return array;
}

function fiveBitArrayTo8BitArray(int5Array, includeOverflow) {
    let count = 0;
    let buffer = 0;
    let byteArray = [];
    int5Array.forEach((value) => {
        buffer = (buffer << 5) + value;
        count += 5;
        if (count >= 8) {
            byteArray.push(buffer >> (count - 8) & 255);
            count -= 8;
        }
    });
    if (includeOverflow && count > 0) {
        byteArray.push(buffer << (8 - count) & 255);
    }
    return byteArray;
}

function bech32ToUTF8String(str) {
    let int5Array = bech32ToFiveBitArray(str);
    let byteArray = fiveBitArrayTo8BitArray(int5Array);

    let utf8String = '';
    for (let i = 0; i < byteArray.length; i++) {
        utf8String += '%' + ('0' + byteArray[i].toString(16)).slice(-2);
    }
    return decodeURIComponent(utf8String);
}

function byteArrayToHexString(byteArray) {
    return Array.prototype.map.call(byteArray, function (byte) {
        return ('0' + (byte & 0xFF).toString(16)).slice(-2);
    }).join('');
}

function textToHexString(text) {
    let hexString = '';
    for (let i = 0; i < text.length; i++) {
        hexString += text.charCodeAt(i).toString(16);
    }
    return hexString;
}

function epochToDate(int) {
    let date = new Date(int * 1000);
    return date.toUTCString();
}

function isEmptyOrSpaces(str){
    return str === null || str.match(/^ *$/) !== null;
}

function toFixed(x) {
    if (Math.abs(x) < 1.0) {
        var e = parseInt(x.toString().split('e-')[1]);
        if (e) {
            x *= Math.pow(10,e-1);
            x = '0.' + (new Array(e)).join('0') + x.toString().substring(2);
        }
    } else {
        var e = parseInt(x.toString().split('+')[1]);
        if (e > 20) {
            e -= 20;
            x /= Math.pow(10,e);
            x += (new Array(e+1)).join('0');
        }
    }
    return x;
}
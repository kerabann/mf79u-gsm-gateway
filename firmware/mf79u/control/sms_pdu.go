package main

// 3GPP TS 23.040 TPDU, TS 23.038 default/extension alphabet. The B03 IMS
// engine constructs RP-DATA and handles SIP/IMS authentication itself.
import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
)

var gsmAlphabet = []rune("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
var gsmExtension = map[byte]rune{10: '\f', 20: '^', 40: '{', 41: '}', 47: '\\', 60: '[', 61: '~', 62: ']', 64: '|', 101: '€'}

func gsmEncode(text string) ([]byte, bool) {
	var out []byte
	for _, r := range text {
		found := false
		for i, x := range gsmAlphabet {
			if x == r && i != 27 {
				out = append(out, byte(i))
				found = true
				break
			}
		}
		if !found {
			for i, x := range gsmExtension {
				if x == r {
					out = append(out, 27, i)
					found = true
					break
				}
			}
		}
		if !found {
			return nil, false
		}
	}
	return out, true
}
func gsmPack(text []byte, header []byte) ([]byte, byte) {
	prefix := (len(header)*8 + 6) / 7
	out := make([]byte, ((prefix+len(text))*7+7)/8)
	copy(out, header)
	for i, x := range text {
		bit := (prefix + i) * 7
		out[bit/8] |= x << uint(bit%8)
		if bit%8 > 1 && bit/8+1 < len(out) {
			out[bit/8+1] |= x >> uint(8-bit%8)
		}
	}
	return out, byte(prefix + len(text))
}
func gsmDecode(data []byte, start, count int) (string, error) {
	if count < 0 || start < 0 || start+count*7 > len(data)*8 {
		return "", errors.New("Truncated GSM-7 SMS")
	}
	var out []rune
	escape := false
	for i := 0; i < count; i++ {
		bit := start + i*7
		v := data[bit/8] >> uint(bit%8)
		if bit%8 > 1 && bit/8+1 < len(data) {
			v |= data[bit/8+1] << uint(8-bit%8)
		}
		v &= 127
		if escape {
			r, ok := gsmExtension[v]
			if !ok {
				return "", errors.New("Unsupported GSM-7 extension")
			}
			out = append(out, r)
			escape = false
		} else if v == 27 {
			escape = true
		} else {
			out = append(out, gsmAlphabet[v])
		}
	}
	if escape {
		return "", errors.New("Incomplete GSM-7 escape")
	}
	return string(out), nil
}
func smsSubmitPDUs(number, text string) ([]string, error) {
	if !numberRE.MatchString(number) || len(strings.TrimPrefix(number, "+")) > 20 || !utf8.ValidString(text) || strings.ContainsRune(text, 0) || len([]rune(text)) < 1 || len([]rune(text)) > 670 {
		return nil, errors.New("Invalid phone number or SMS text (1–670 characters)")
	}
	ref := make([]byte, 1)
	if _, e := rand.Read(ref); e != nil {
		return nil, e
	}
	digits := strings.TrimPrefix(number, "+")
	toa := byte(0x81)
	if number[0] == '+' {
		toa = 0x91
	}
	address := []byte{byte(len(digits)), toa}
	for i := 0; i < len(digits); i += 2 {
		v := digits[i] - '0'
		h := byte(15)
		if i+1 < len(digits) {
			h = digits[i+1] - '0'
		}
		address = append(address, v|(h<<4))
	}
	septets, gsm := gsmEncode(text)
	var chunks [][]byte
	if gsm {
		limit := 160
		if len(septets) > 160 {
			limit = 153
		}
		for len(septets) > 0 {
			n := len(septets)
			if n > limit {
				n = limit
				if septets[n-1] == 27 {
					n--
				}
			}
			chunks = append(chunks, append([]byte(nil), septets[:n]...))
			septets = septets[n:]
		}
	} else {
		units := utf16.Encode([]rune(text))
		limit := 70
		if len(units) > 70 {
			limit = 67
		}
		for len(units) > 0 {
			n := len(units)
			if n > limit {
				n = limit
				if units[n-1] >= 0xd800 && units[n-1] <= 0xdbff {
					n--
				}
			}
			var bytes []byte
			for _, u := range units[:n] {
				bytes = append(bytes, byte(u>>8), byte(u))
			}
			chunks = append(chunks, bytes)
			units = units[n:]
		}
	}
	out := []string{}
	for i, chunk := range chunks {
		fo, dcs := byte(1), byte(8)
		var header []byte
		if len(chunks) > 1 {
			fo |= 0x40
			header = []byte{5, 0, 3, ref[0], byte(len(chunks)), byte(i + 1)}
		}
		var ud []byte
		var udl byte
		if gsm {
			dcs = 0
			ud, udl = gsmPack(chunk, header)
		} else {
			ud = append(header, chunk...)
			udl = byte(len(ud))
		}
		pdu := []byte{0, fo, 0}
		pdu = append(pdu, address...)
		pdu = append(pdu, 0, dcs, udl)
		pdu = append(pdu, ud...)
		out = append(out, strings.ToUpper(hex.EncodeToString(pdu)))
	}
	return out, nil
}

type imsSMSPart struct {
	Number, Text, Date, Hash, Group string
	Total, Sequence                 int
	Report                          bool
}

func smsSemi(data []byte, digits int) (string, error) {
	if digits < 1 || digits > 20 || len(data) != (digits+1)/2 {
		return "", errors.New("Invalid SMS address")
	}
	var out strings.Builder
	for i := 0; i < digits; i++ {
		v := data[i/2] >> uint((i%2)*4) & 15
		if v > 9 {
			return "", errors.New("Invalid SMS address digit")
		}
		out.WriteByte('0' + v)
	}
	return out.String(), nil
}
func smsDecodePDU(encoded string) (imsSMSPart, error) {
	var result imsSMSPart
	bad := errors.New("Invalid IMS SMS PDU")
	p, e := hex.DecodeString(encoded)
	if e != nil || len(p) < 2 || len(p) > 200 {
		return result, bad
	}
	result.Hash = smsSIPHash(strings.ToUpper(encoded))
	sca := int(p[0])
	if sca+2 > len(p) {
		return result, bad
	}
	p = p[sca+1:]
	fo := p[0]
	if fo&3 == 2 {
		result.Report = true
		return result, nil
	} // status report, not an inbox message
	if fo&3 != 0 || len(p) < 3 {
		return result, bad
	}
	n, toa := int(p[1]), p[2]
	addrBytes := (n + 1) / 2
	if addrBytes < 1 || addrBytes > 20 || len(p) < 3+addrBytes+10 {
		return result, bad
	}
	if toa&0x70 == 0x50 {
		result.Number, e = gsmDecode(p[3:3+addrBytes], 0, n*4/7)
	} else {
		result.Number, e = smsSemi(p[3:3+addrBytes], n)
		if toa&0x70 == 0x10 {
			result.Number = "+" + result.Number
		}
	}
	if e != nil {
		return result, e
	}
	p = p[3+addrBytes:]
	dcs := p[1]
	stamp := p[2:9]
	swapped := func(x byte) int { return int(x&15)*10 + int(x>>4) }
	for i, x := range stamp {
		if i == 6 {
			x &= 0xf7
		}
		if x&15 > 9 || x>>4 > 9 {
			return result, bad
		}
	}
	sign := "+"
	if stamp[6]&8 != 0 {
		sign = "-"
	}
	raw := fmt.Sprintf("%02d,%d,%d,%d,%d,%d,%s%d", swapped(stamp[0]), swapped(stamp[1]), swapped(stamp[2]), swapped(stamp[3]), swapped(stamp[4]), swapped(stamp[5]), sign, swapped(stamp[6]&0xf7))
	date := smsDate(raw)
	if date == nil {
		return result, bad
	}
	result.Date = *date
	udl := int(p[9])
	ud := p[10:]
	alphabet := byte(0)
	switch {
	case dcs&0xc0 == 0:
		if dcs&0x20 != 0 {
			return result, errors.New("Compressed SMS is unsupported")
		}
		alphabet = (dcs >> 2) & 3
	case dcs&0xf0 == 0xe0:
		alphabet = 2
	case dcs&0xf0 == 0xc0 || dcs&0xf0 == 0xd0:
		alphabet = 0
	case dcs&0xf0 == 0xf0:
		alphabet = (dcs >> 2) & 1
	default:
		return result, errors.New("Unsupported SMS alphabet")
	}
	bytes := udl
	if alphabet == 0 {
		bytes = (udl*7 + 7) / 8
	}
	if bytes > 140 || bytes != len(ud) {
		return result, bad
	}
	skip := 0
	result.Total, result.Sequence = 1, 1
	if fo&0x40 != 0 {
		if len(ud) < 1 {
			return result, bad
		}
		skip = int(ud[0]) + 1
		if skip > len(ud) {
			return result, bad
		}
		for i := 1; i < skip; {
			if i+2 > skip {
				return result, bad
			}
			kind, size := ud[i], int(ud[i+1])
			i += 2
			if i+size > skip {
				return result, bad
			}
			v := ud[i : i+size]
			switch {
			case kind == 0 && size == 3:
				result.Group = fmt.Sprint(v[0])
				result.Total, result.Sequence = int(v[1]), int(v[2])
			case kind == 8 && size == 4:
				result.Group = fmt.Sprint(int(v[0])<<8 | int(v[1]))
				result.Total, result.Sequence = int(v[2]), int(v[3])
			case kind == 0 || kind == 8:
				return result, bad
			case kind == 0x24 || kind == 0x25:
				return result, errors.New("National language SMS alphabet is unsupported")
			}
			i += size
		}
		if result.Total < 1 || result.Total > 24 || result.Sequence < 1 || result.Sequence > result.Total {
			return result, bad
		}
	}
	switch alphabet {
	case 0:
		prefix := (skip*8 + 6) / 7
		result.Text, e = gsmDecode(ud, prefix*7, udl-prefix)
	case 2:
		body := ud[skip:]
		if len(body)&1 != 0 {
			return result, bad
		}
		var units []uint16
		for i := 0; i < len(body); i += 2 {
			units = append(units, uint16(body[i])<<8|uint16(body[i+1]))
		}
		result.Text = string(utf16.Decode(units))
	default:
		return result, errors.New("Binary SMS is not a text message")
	}
	if e != nil || strings.ContainsRune(result.Text, 0) {
		return result, bad
	}
	if result.Total > 1 {
		result.Group = smsSIPHash(result.Number + "\x00" + result.Date[:10] + "\x00" + result.Group + fmt.Sprint(result.Total, dcs))
	}
	return result, nil
}

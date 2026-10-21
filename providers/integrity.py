"""Streaming provider hashes. QuickXor is an error check, not a signature."""
import base64
import hashlib
import hmac
import zlib


class CRC32:
    def __init__(self): self.value=0
    def update(self,data): self.value=zlib.crc32(data,self.value)
    def digest(self): return (self.value & 0xffffffff).to_bytes(4,'big')


class QuickXor:
    def __init__(self):
        self.fold = 0
        self.tail = b''
        self.length = 0

    def update(self, data):
        self.length += len(data)
        data = self.tail + data
        end = len(data) // 160 * 160
        for start in range(0, end, 160):
            self.fold ^= int.from_bytes(data[start:start + 160], 'little')
        self.tail = data[end:]

    def digest(self):
        folded = self.fold ^ int.from_bytes(self.tail, 'little')
        value = 0
        for index in range(160):
            value ^= ((folded >> (index * 8)) & 255) << ((index * 11) % 160)
        value = (value & ((1 << 160) - 1)) ^ (value >> 160)
        value ^= (self.length & ((1 << 64) - 1)) << 96
        return value.to_bytes(20, 'little')


def verify_source(path, metadata):
    """Return the actual comparison ledger; absence is explicit, never a pass."""
    supplied = metadata.get('file', {}).get('hashes', {})
    expected = {}
    # Graph explicitly marks sha256Hash unsupported; local SHA-256 is separate.
    for key, algorithm in [('crc32Hash','crc32'), ('sha1Hash', 'sha1'), ('quickXorHash', 'quickxor')]:
        if supplied.get(key):
            expected[algorithm] = (supplied[key], 'base64' if algorithm == 'quickxor' else 'hex')
    if metadata.get('md5Checksum'):
        expected['md5'] = (metadata['md5Checksum'], 'hex')
    # Rclone lists hashes as hex, including QuickXorHash.
    for key, value in metadata.get('Hashes', {}).items():
        algorithm = {'md5': 'md5', 'sha1': 'sha1', 'sha256': 'sha256', 'quickxor': 'quickxor','crc32':'crc32'}.get(key.lower())
        if algorithm and value:
            expected.setdefault(algorithm, (value, 'hex'))
    if not expected:
        return {'status': 'unavailable', 'algorithms': [], 'note': 'Keine unterstützte Quellprüfsumme verfügbar.'}
    digests = {name: QuickXor() if name == 'quickxor' else (CRC32() if name=='crc32' else hashlib.new(name, usedforsecurity=False)) for name in expected}
    with path.open('rb') as handle:
        while chunk := handle.read(256 * 1024):
            for digest in digests.values():
                digest.update(chunk)
    for name, (value, encoding) in expected.items():
        try:
            wanted = base64.b64decode(value, validate=True) if encoding == 'base64' else bytes.fromhex(value)
        except (ValueError, TypeError):
            raise ValueError('Ungültige Quellprüfsumme; Datei wurde nicht übernommen.') from None
        if not hmac.compare_digest(digests[name].digest(), wanted):
            raise ValueError('Quellprüfsumme stimmt nicht überein; Datei wurde nicht übernommen.')
    return {'status': 'verified', 'algorithms': sorted(expected)}

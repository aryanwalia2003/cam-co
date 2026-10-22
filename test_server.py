"""make_png ke liye ek chhota sa sanity check. Chalao: python3 test_server.py"""
import struct
import zlib

from server import make_png

def read_chunks(png: bytes) -> dict:
    chunks, pos = {}, 8
    while pos < len(png):
        length = struct.unpack(">I", png[pos:pos + 4])[0]
        tag = png[pos + 4:pos + 8]
        chunks[tag] = png[pos + 8:pos + 8 + length]
        pos += 8 + length + 4  # +4 = crc
    return chunks


png = make_png(4, 3, (10, 20, 30))
assert png.startswith(b"\x89PNG\r\n\x1a\n"), "PNG signature galat"

chunks = read_chunks(png)
w, h, depth, color_type = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
assert (w, h, depth, color_type) == (4, 3, 8, 2), "IHDR fields galat"

raw = zlib.decompress(chunks[b"IDAT"])
assert len(raw) == 3 * (1 + 4 * 3), "decompressed scanline size galat"
assert raw[1:4] == bytes((10, 20, 30)), "pixel color galat"

print("ok")

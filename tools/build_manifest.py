"""Scan data/ for DICOM files and write manifest.json (stdlib only).

Only the header is read. Assumes Explicit VR Little Endian (the disc's transfer syntax).
Usage: python tools/build_manifest.py   (run from kade_ct_online/)
"""
import json, os, struct, sys, collections

WANT = {
    (0x0002, 0x0010): "ts", (0x0010, 0x0010): "patient", (0x0010, 0x0020): "pid",
    (0x0008, 0x0020): "studyDate", (0x0008, 0x1030): "studyDesc", (0x0008, 0x0060): "modality",
    (0x0008, 0x103E): "seriesDesc", (0x0020, 0x000E): "seriesUID", (0x0020, 0x0011): "seriesNumber",
    (0x0020, 0x0013): "instance", (0x0020, 0x0032): "ipp", (0x0020, 0x0037): "iop",
    (0x0020, 0x1041): "sliceLoc", (0x0018, 0x0050): "thickness", (0x0028, 0x0010): "rows",
    (0x0028, 0x0011): "cols", (0x0028, 0x0030): "spacing", (0x0028, 0x0100): "bitsAlloc",
    (0x0028, 0x0103): "pixelRep", (0x0028, 0x0002): "samples", (0x0028, 0x0004): "photometric",
    (0x0028, 0x1050): "wc", (0x0028, 0x1051): "ww", (0x0028, 0x1052): "intercept",
    (0x0028, 0x1053): "slope", (0x0008, 0x0008): "imageType",
    (0x0010, 0x1010): "age", (0x0010, 0x0040): "sex", (0x0008, 0x0050): "acc",
    (0x0008, 0x0080): "institution", (0x0008, 0x0090): "referring", (0x0008, 0x0070): "maker",
    (0x0008, 0x1090): "model", (0x0008, 0x0030): "studyTime", (0x0008, 0x1070): "operator",
    (0x0018, 0x5100): "patPos", (0x0010, 0x0030): "dob",
}
US = {"rows", "cols", "bitsAlloc", "pixelRep", "samples"}
LONG_VR = {b"OB", b"OW", b"OF", b"OD", b"OL", b"OV", b"SQ", b"UC", b"UR", b"UT", b"UN"}


def study_meta(h):
    """Study-level fields for the viewer. Age is worked out here ("44Y 4M") so the birth date itself never ships."""
    m = {k: h.get(k, "") for k in ("patient", "pid", "studyDate", "studyDesc", "sex", "acc", "institution",
                                    "referring", "maker", "model", "studyTime", "operator", "patPos")}
    b, d = h.get("dob", ""), h.get("studyDate", "")
    m["age"] = h.get("age", "")
    if len(b) == 8 and len(d) == 8:
        mo = (int(d[:4]) - int(b[:4])) * 12 + int(d[4:6]) - int(b[4:6]) - (int(d[6:]) < int(b[6:]))
        m["age"] = f"{mo // 12}Y {mo % 12}M"
    return m



def skip_undefined(buf, pos):
    """Skip an undefined-length value (nested items) and return the position after it."""
    while True:
        g, e, ln = struct.unpack_from("<HHI", buf, pos)
        pos += 8
        if (g, e) == (0xFFFE, 0xE0DD):
            return pos
        if (g, e) == (0xFFFE, 0xE000):
            if ln == 0xFFFFFFFF:
                pos = skip_item(buf, pos)
            else:
                pos += ln
        else:
            raise ValueError("bad sequence structure")


def skip_item(buf, pos):
    while True:
        g, e = struct.unpack_from("<HH", buf, pos)
        if (g, e) == (0xFFFE, 0xE00D):
            return pos + 8
        vr = buf[pos + 4:pos + 6]
        if vr in LONG_VR:
            ln = struct.unpack_from("<I", buf, pos + 8)[0]
            hdr = 12
        else:
            ln = struct.unpack_from("<H", buf, pos + 6)[0]
            hdr = 8
        pos += hdr
        if ln == 0xFFFFFFFF:
            pos = skip_undefined(buf, pos)
        else:
            pos += ln


def parse(path):
    with open(path, "rb") as f:
        buf = f.read(65536)  # headers sit well inside the first 64 KB on this disc
    if buf[128:132] != b"DICM":
        return None
    pos, out = 132, {}
    while pos + 8 <= len(buf):
        g, e = struct.unpack_from("<HH", buf, pos)
        if (g, e) >= (0x7FE0, 0x0010):
            break
        vr = buf[pos + 4:pos + 6]
        if vr in LONG_VR:
            ln = struct.unpack_from("<I", buf, pos + 8)[0]
            pos += 12
        else:
            ln = struct.unpack_from("<H", buf, pos + 6)[0]
            pos += 8
        if ln == 0xFFFFFFFF:
            pos = skip_undefined(buf, pos)
            continue
        raw = buf[pos:pos + ln]
        pos += ln
        key = WANT.get((g, e))
        if key:
            if key in US:
                out[key] = struct.unpack_from("<H", raw)[0]
            else:
                out[key] = raw.decode("latin-1").strip("\x00 ")
    return out


def nums(s):
    return [float(x) for x in s.split("\\")] if s else None


def main():
    root = "data"
    series = collections.OrderedDict()
    meta = {}
    n = bad = 0
    for dp, _, fs in os.walk(os.path.join(root, "000")):
        for fn in sorted(fs):
            p = os.path.join(dp, fn)
            h = parse(p)
            if not h or "rows" not in h:
                bad += 1
                print("skip", p, file=sys.stderr)
                continue
            if h.get("ts") != "1.2.840.10008.1.2.1":
                print("WARNING non explicit-LE:", p, h.get("ts"), file=sys.stderr)
            n += 1
            meta = meta or study_meta(h)
            s = series.setdefault(h["seriesUID"], {
                "uid": h["seriesUID"], "number": int(h.get("seriesNumber") or 0),
                "desc": h.get("seriesDesc", ""), "modality": h.get("modality", ""), "images": []})
            ipp = nums(h.get("ipp"))
            iop = nums(h.get("iop"))
            s["images"].append({
                "f": os.path.relpath(p, root).replace(os.sep, "/"),
                "n": int(h.get("instance") or 0),
                "loc": float(h["sliceLoc"]) if h.get("sliceLoc") else None,
                "ipp": ipp, "iop": iop, "rows": h["rows"], "cols": h["cols"],
                "sp": nums(h.get("spacing")), "th": float(h["thickness"]) if h.get("thickness") else None,
                "bits": h.get("bitsAlloc"), "rep": h.get("pixelRep"), "spp": h.get("samples", 1),
                "pi": h.get("photometric"), "wc": nums(h.get("wc")), "ww": nums(h.get("ww")),
                "ic": float(h.get("intercept") or 0), "sl": float(h.get("slope") or 1),
                "type": h.get("imageType", ""),
            })
    out = sorted(series.values(), key=lambda s: s["number"])
    for s in out:
        # Sort along the slice normal when position data exists, else by instance number.
        def key(im):
            if im["ipp"] and im["iop"]:
                r, c = im["iop"][:3], im["iop"][3:]
                nrm = (r[1] * c[2] - r[2] * c[1], r[2] * c[0] - r[0] * c[2], r[0] * c[1] - r[1] * c[0])
                return sum(a * b for a, b in zip(nrm, im["ipp"]))
            return im["n"]
        s["images"].sort(key=lambda im: (key(im), im["n"]))
        s["count"] = len(s["images"])
    with open("manifest.json", "w") as f:
        json.dump({"study": meta, "series": out}, f, separators=(",", ":"))
    print(f"{n} images, {bad} skipped, {len(out)} series")
    for s in out:
        print(s["number"], s["modality"], s["count"], s["desc"])


main()

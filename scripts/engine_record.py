"""engine_record.py ROOT NAME COMMIT: the engine record of the build NAME under the build root ROOT, written beside each arclog binary of that build.

The record is the JSON object that `round_core.content_key.Engine.load` reads:
{"commit": COMMIT, "flags": {"profile": "tool"}, "clean": true, "binaries": {PLATFORM: SHA256}}. `binaries` holds the sha256 of the arclog
binary of each platform built for NAME from COMMIT: the Mac site `builds/NAME`, as `<sys.platform>-<machine>` of the machine that builds it,
and the Linux wheel in `linux/NAME`, as `linux-x86_64`. A site whose COMMIT file names another commit takes no part. Every site of NAME gets the
same record: `builds/NAME/arclog/engine-record.json`, and the file `arclog/engine-record.json` in the Linux arclog wheel, with its line in the
wheel's RECORD and the folder's SHA256SUMS made again. The build checks out COMMIT in a clean tree, so `clean` is true. `profile` is the cargo
profile that every part of the build compiles with."""
import base64, glob, hashlib, io, json, os, platform, re, sys, zipfile

RECORD_NAME = "arclog/engine-record.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def commit_of(folder):
    try:
        with open(os.path.join(folder, "COMMIT")) as handle:
            return handle.read().strip()
    except OSError:
        return None


def linux_wheel(folder):
    wheels = sorted(glob.glob(os.path.join(folder, "arclog-*.whl")))
    return wheels[0] if wheels else None


def binary_in(wheel):
    with zipfile.ZipFile(wheel) as archive:
        names = [n for n in archive.namelist() if re.fullmatch(r"arclog/[^/]+\.so", n)]
        if len(names) != 1:
            sys.exit("%s: %d arclog binaries, not one" % (wheel, len(names)))
        return archive.read(names[0])


def write_into_wheel(wheel, data):
    """Rewrite `wheel` with RECORD_NAME holding `data`, in place of any earlier copy, and with its line in the dist-info RECORD. The entries keep
    their order and their times, so the rewrite of one record into one wheel gives the same bytes."""
    with zipfile.ZipFile(wheel) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist() if info.filename != RECORD_NAME]
    so = next(info for info, _ in entries if re.fullmatch(r"arclog/[^/]+\.so", info.filename))
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    line = "%s,sha256=%s,%d" % (RECORD_NAME, digest, len(data))
    out = []
    for info, body in entries:
        if re.fullmatch(r"arclog-[^/]+\.dist-info/RECORD", info.filename):
            kept = [l for l in body.decode().splitlines() if l and not l.startswith(RECORD_NAME + ",")]
            body = ("\n".join(kept[:-1] + [line, kept[-1]]) + "\n").encode()
        out.append((info, body))
        if info.filename == so.filename:
            record = zipfile.ZipInfo(RECORD_NAME, date_time=so.date_time)
            record.compress_type, record.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            out.append((record, data))
    temp = wheel + ".part"
    with zipfile.ZipFile(temp, "w") as archive:
        for info, body in out:
            archive.writestr(info, body, compress_type=info.compress_type)
    os.replace(temp, wheel)


def main():
    root, name, commit = sys.argv[1:4]
    mac, linux = os.path.join(root, "builds", name), os.path.join(root, "linux", name)
    binaries = {}
    mac_binaries = sorted(glob.glob(os.path.join(mac, "arclog", "*.so")))
    if commit_of(mac) == commit and len(mac_binaries) == 1:
        with open(mac_binaries[0], "rb") as handle:
            binaries["%s-%s" % (sys.platform, platform.machine())] = sha256(handle.read())
    wheel = linux_wheel(linux) if commit_of(linux) == commit else None
    if wheel:
        binaries["linux-x86_64"] = sha256(binary_in(wheel))
    if not binaries:
        print("engine record: no arclog binary of %s for %s" % (commit[:9], name))
        return
    data = (json.dumps({"commit": commit, "flags": {"profile": "tool"}, "clean": True, "binaries": binaries}, indent=1, sort_keys=True) + "\n").encode()
    if len(mac_binaries) == 1 and commit_of(mac) == commit:
        with open(os.path.join(mac, RECORD_NAME), "wb") as handle:
            handle.write(data)
    if wheel:
        write_into_wheel(wheel, data)
        files = sorted(f for f in os.listdir(linux) if f not in ("SHA256SUMS", "COMMIT") and os.path.isfile(os.path.join(linux, f)))
        with open(os.path.join(linux, "SHA256SUMS"), "w") as handle:
            for f in files:
                with open(os.path.join(linux, f), "rb") as body:
                    handle.write("%s  %s\n" % (sha256(body.read()), f))
    print("engine record of %s for %s: %s" % (commit[:9], name, ", ".join(sorted(binaries))))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reconstruct upstream ancestry without changing the original vendor history."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR_TIP = "dee4ef0f"


def git(*args, data=None, env=None):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], input=data, env=env
    )


def oid(ref):
    return git("rev-parse", "--verify", ref + "^{commit}").decode().strip()


def stock():
    roots = git("rev-list", "--max-parents=0", VENDOR_TIP).decode().splitlines()
    if len(roots) != 1 or not roots[0].startswith("1fcf1c94"):
        raise ValueError("Expected the single original OPPO stock root 1fcf1c94")
    return roots[0]


def version(ref):
    makefile = git("show", ref + ":Makefile").decode()
    return tuple(int(re.search(r"^" + key + r"\s*=\s*(\d+)", makefile,
                               re.M).group(1))
                 for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))


def blobs(ref):
    with subprocess.Popen(["git", "-C", str(ROOT), "cat-file", "--batch"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        for entry in git("ls-tree", "-r", "-z", ref).split(b"\0"):
            if not entry:
                continue
            metadata, path = entry.split(b"\t", 1)
            mode, kind, blob_id = metadata.split()
            if kind != b"blob":
                continue
            process.stdin.write(blob_id + b"\n")
            process.stdin.flush()
            header = process.stdout.readline().split()
            size = int(header[2])
            content = process.stdout.read(size)
            if len(content) != size or process.stdout.read(1) != b"\n":
                raise ValueError("Truncated git cat-file output")
            yield os.fsdecode(path), content
        process.stdin.close()
        if process.wait():
            raise ValueError("git cat-file failed")


def audit(args):
    ref = oid(args.ref)
    entries = []
    for name, blob in blobs(ref):
        if b"\0" in blob:
            continue
        markers = []
        for lineno, line in enumerate(blob.splitlines(), 1):
            # Evidence only: VENDOR_EDIT alone does not prove OPPO authorship.
            if re.search(rb"oppo|VENDOR_EDIT", line, re.I):
                markers.append({"line": lineno,
                                "text": line.decode("utf-8", "replace")})
        path_evidence = bool(re.search(r"oppo", name, re.I))
        if markers or path_evidence:
            entries.append({"path": name, "oppo_path": path_evidence,
                            "markers": markers})
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"source": ref, "version": version(ref),
              "notice": "Candidate evidence, not a pure OPPO patch. The stock "
                        "snapshot mixes Linux, Android, MediaTek and OPPO code.",
              "files": entries}
    (output / "vendor-evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    paths = [entry["path"] for entry in entries if entry["oppo_path"]]
    (output / "oppo-paths.txt").write_text("\n".join(paths) + "\n")
    # Only paths explicitly named OPPO go into the standalone archive.
    if paths:
        with (output / "oppo-paths.tar").open("wb") as stream:
            subprocess.run(["git", "-C", str(ROOT), "archive", ref, "--", *paths],
                           stdout=stream, check=True)
    print(f"{len(entries)} candidate files; {len(paths)} OPPO-named paths: {output}")


def restore(args):
    base = oid(args.base)
    if version(base) != (3, 10, 72):
        raise ValueError("The proposed upstream base must be Linux 3.10.72")
    branch = "refs/heads/" + args.branch
    subprocess.run(["git", "check-ref-format", branch], check=True)
    if subprocess.run(["git", "-C", str(ROOT), "show-ref", "--verify", "--quiet",
                       branch]).returncode == 0:
        raise ValueError("Destination branch already exists; refusing to replace it")
    commits = git("rev-list", "--reverse", "--topo-order", VENDOR_TIP).decode().splitlines()
    if commits[0] != stock():
        raise ValueError("Unexpected vendor root")
    mapping = []
    parent = base
    for original in commits:
        parents = git("show", "-s", "--format=%P", original).decode().split()
        if len(parents) > 1:
            raise ValueError("Nonlinear vendor history needs manual reconstruction")
        fields = git("show", "-s", "--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI",
                     original).decode().strip().split("\0")
        env = os.environ.copy()
        for key, value in zip(("AUTHOR_NAME", "AUTHOR_EMAIL", "AUTHOR_DATE",
                               "COMMITTER_NAME", "COMMITTER_EMAIL", "COMMITTER_DATE"), fields):
            env["GIT_" + key] = value
        message = git("show", "-s", "--format=%B", original)
        if original == commits[0]:
            message = (b"vendor: import OPPO/MediaTek stock snapshot on Linux 3.10.72\n\n"
                       b"Reconstructed ancestry; not recovered vendor development history.\n"
                       b"The parent is inferred from the stock Makefile version.\n"
                       + b"Original-commit: " + original.encode() + b"\n")
        else:
            message += b"\nOriginal-commit: " + original.encode() + b"\n"
        tree = git("rev-parse", original + "^{tree}").decode().strip()
        new = git("commit-tree", tree, "-p", parent, data=message, env=env).decode().strip()
        if git("rev-parse", new + "^{tree}").strip() != tree.encode():
            raise ValueError("Tree mismatch")
        mapping.append((original, new))
        parent = new
    git("update-ref", branch, parent, "0" * 40)
    print("Original vendor branch preserved. Reconstructed branch: " + args.branch)
    for original, new in mapping:
        print(original + " " + new)


def export(args):
    base = oid(args.base)
    if version(base) != (3, 10, 72):
        raise ValueError("Export base must be Linux 3.10.72")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with (output / "linux-to-stock.patch").open("wb") as stream:
        subprocess.run(["git", "-C", str(ROOT), "diff", "--binary", "--full-index",
                        base, stock()], stdout=stream, check=True)
    (output / "PROVENANCE.txt").write_text(
        f"Base: {base}\nStock: {stock()}\n"
        "This is the combined MediaTek/Android/OPPO delta, not OPPO-only.\n"
        "A matching pre-OPPO MediaTek source is required to separate OPPO edits.\n")
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("audit", help="Export OPPO paths and vendor marker evidence")
    p.add_argument("--ref", default=VENDOR_TIP)
    p.add_argument("--output", required=True)
    p.set_defaults(run=audit)
    p = commands.add_parser("restore", help="Create a new branch with upstream ancestry")
    p.add_argument("--base", default="refs/tags/v3.10.72")
    p.add_argument("--branch", default="reconstructed/oppo-3.10.72")
    p.set_defaults(run=restore)
    p = commands.add_parser("export", help="Export the complete stock delta from upstream")
    p.add_argument("--base", default="refs/tags/v3.10.72")
    p.add_argument("--output", required=True)
    p.set_defaults(run=export)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)

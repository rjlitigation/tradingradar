# tools/fix_merge_markers.py
import sys, os, re, shutil

USAGE = "python tools/fix_merge_markers.py app/replay.py"

def clean_file(path):
    if not os.path.exists(path):
        print(f"❌ No such file: {path}")
        sys.exit(1)

    bak = path + ".bak"
    shutil.copy2(path, bak)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    out = []
    i = 0
    changed = False
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            changed = True
            # consume "ours" until =======
            i += 1
            ours = []
            while i < len(lines) and not lines[i].startswith("======="):
                ours.append(lines[i]); i += 1
            # skip the ======= line
            if i < len(lines) and lines[i].startswith("======="):
                i += 1
            # consume "theirs" until >>>>>>>
            while i < len(lines) and not lines[i].startswith(">>>>>>>"):
                i += 1
            # skip the >>>>>>> line
            if i < len(lines) and lines[i].startswith(">>>>>>>"):
                i += 1
            # keep ours by default
            out.extend(ours)
        else:
            # also strip any stray >>>>>>> hash lines if present
            if line.startswith(">>>>>>>") or line.startswith("<<<<<<<") or line.startswith("======="):
                changed = True
                i += 1
                continue
            out.append(line)
            i += 1

    # Also remove invisible garbage merge lines like ">>>>>> 5acb3a7 (…)" that
    # sometimes get pasted without the full conflict block:
    new_out = []
    for ln in out:
        if re.match(r"^>{5,}", ln.strip()):
            changed = True
            continue
        new_out.append(ln)

    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.writelines(new_out)

    print(f"✅ Cleaned {path}. Backup saved at {bak}" if changed else f"ℹ️ No markers found in {path} (no changes).")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(USAGE); sys.exit(1)
    clean_file(sys.argv[1])

"""Inspect diagram data inside the .veragrid file."""
import sys, zipfile, json
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

path = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

with zipfile.ZipFile(path, 'r') as zf:
    print("=== Files in archive ===")
    for name in zf.namelist():
        print(f"  {name}")

    # Look for diagram or gui config files
    for name in zf.namelist():
        if 'diagram' in name.lower() or 'gui' in name.lower() or 'config' in name.lower():
            print(f"\n=== {name} ===")
            data = zf.read(name)
            try:
                parsed = json.loads(data)
                print(json.dumps(parsed, indent=2)[:3000])
            except:
                print(f"  (binary, {len(data)} bytes)")

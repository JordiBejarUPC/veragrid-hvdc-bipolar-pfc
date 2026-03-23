"""Fix the diagram directly in the ZIP without using the API (which fails on parse)."""
import zipfile, json

FILEPATH = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

# Read all files from ZIP
file_contents = {}
diagram_name = None
with zipfile.ZipFile(FILEPATH, 'r') as zf:
    for name in zf.namelist():
        file_contents[name] = zf.read(name)
        if name.endswith('.diagram'):
            diagram_name = name

# Parse and fix the diagram
diagram = json.loads(file_contents[diagram_name])

# Fix VSC entries: add missing w, h, r fields
if 'VSC' in diagram['data']:
    for idtag, entry in diagram['data']['VSC'].items():
        if 'w' not in entry:
            entry['w'] = 80.0
        if 'h' not in entry:
            entry['h'] = 40
        if 'r' not in entry:
            entry['r'] = 0.0
        print(f"Fixed VSC entry {idtag}: x={entry['x']:.1f}, y={entry['y']:.1f}")

# Write back
file_contents[diagram_name] = json.dumps(diagram, indent=2).encode('utf-8')
with zipfile.ZipFile(FILEPATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for name, data in file_contents.items():
        zf.writestr(name, data)

print(f"\nFixed diagram in {FILEPATH}")

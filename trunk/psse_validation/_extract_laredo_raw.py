import os

folder = "data"
src_name = os.path.join(folder, "ACTIVSg2000.RAW")
dst_name = os.path.join(folder, "ACTIVS_Laredo.raw")

with open(src_name) as f:
    lines = f.readlines()

# Section separators in this file are the "0 / END OF X DATA, BEGIN Y DATA" comment
# lines PSSe writes between every record block, always in the fixed PSSe section order.
markers = [i for i, l in enumerate(lines) if l.lstrip().startswith('0 /')]
(bus_end, load_end, fixshunt_end, gen_end, branch_end, trafo_end,
 area_end, dc2_end, vsc_end, imp_end, mtdc_end, msline_end,
 zone_end, interarea_end, owner_end, facts_end, swshunt_end, gne_end) = markers


def bus_num(field: str) -> int:
    """Parse a PSSe integer field (arbitrary surrounding whitespace) into a bus number."""
    return int(field.strip())


def filter_by_first_field(block_lines: list[str], keep_buses: set[int]) -> list[str]:
    """Keep single-line records (bus, load, fixed shunt, generator, switched shunt) whose I field is in keep_buses."""
    kept = list()
    for l in block_lines:
        fields = l.split(',')
        if bus_num(fields[0]) in keep_buses:
            kept.append(l)
    return kept


def promote_to_swing(bus_lines: list[str], swing_bus: int) -> list[str]:
    """Set IDE (field index 3 of the Bus Data record) to 3 for the given bus number."""
    out_lines = list()
    for l in bus_lines:
        fields = l.split(',')
        if bus_num(fields[0]) == swing_bus:
            fields[3] = '3'
            l = ','.join(fields)
        out_lines.append(l)
    return out_lines


def filter_branches(block_lines: list[str], keep_buses: set[int]) -> list[str]:
    """Keep line records only when both terminal buses (I, J) are in keep_buses, dropping ties out of the zone."""
    kept = list()
    for l in block_lines:
        fields = l.split(',')
        if bus_num(fields[0]) in keep_buses and bus_num(fields[1]) in keep_buses:
            kept.append(l)
    return kept


def filter_transformers(block_lines: list[str], keep_buses: set[int]) -> list[str]:
    """
    Keep whole 2-winding transformer records (4 physical lines each) only when both
    terminal buses (I, J) on the record's first line are in keep_buses. ACTIVSg2000 has
    no 3-winding transformers, so every record here is a fixed 4-line block (verified
    below by the modulo check instead of assumed silently).
    """
    assert len(block_lines) % 4 == 0, "Unexpected transformer block size - a 3-winding (5-line) record may be present"
    kept = list()
    for i in range(0, len(block_lines), 4):
        block = block_lines[i:i + 4]
        fields = block[0].split(',')
        if bus_num(fields[0]) in keep_buses and bus_num(fields[1]) in keep_buses:
            kept.extend(block)
    return kept


# --- find the Laredo zone number from the Zone Data section, independent of the VeraGrid parser ---
laredo_zone_num = None
for l in lines[msline_end + 1:zone_end]:
    fields = l.split(',')
    if 'laredo' in fields[1].strip().strip("'").lower():
        laredo_zone_num = fields[0].strip()
        break
if laredo_zone_num is None:
    raise Exception("Laredo zone not found in Zone Data section")

# --- collect the PSSe bus numbers belonging to that zone straight from the Bus Data ZONE field ---
laredo_buses: set[int] = set()
for l in lines[3:bus_end]:
    fields = l.split(',')
    if fields[5].strip() == laredo_zone_num:
        laredo_buses.add(bus_num(fields[0]))

print(f"Laredo zone number: {laredo_zone_num}, buses found: {len(laredo_buses)}")

# --- drop buses that only had ties to other zones: build adjacency from the branch/ ---
# --- transformer records that survive the zone filter, then keep the main component ---
zone_branches = filter_branches(lines[gen_end + 1:branch_end], laredo_buses)
zone_transformer_blocks = filter_transformers(lines[branch_end + 1:trafo_end], laredo_buses)
zone_transformer_first_lines = zone_transformer_blocks[0::4]

adj: dict[int, set[int]] = {b: set() for b in laredo_buses}
for l in zone_branches + zone_transformer_first_lines:
    fields = l.split(',')
    i, j = bus_num(fields[0]), bus_num(fields[1])
    adj[i].add(j)
    adj[j].add(i)

seen: set[int] = set()
components: list[set[int]] = list()
for b in laredo_buses:
    if b in seen:
        continue
    stack = [b]
    comp: set[int] = set()
    while stack:
        x = stack.pop()
        if x in comp:
            continue
        comp.add(x)
        stack.extend(adj[x] - comp)
    seen |= comp
    components.append(comp)

keep_buses = max(components, key=len)
islanded_buses = laredo_buses - keep_buses
print(f"Islanded buses removed: {sorted(islanded_buses)}")

# --- reassemble the file, filtering only the bus-referencing sections and leaving ---
# --- area/zone/owner/DC/FACTS/GNE declarations and the header/terminator untouched ---
out: list[str] = list()
out += lines[0:3]
# Zone filtering cuts the grid's only swing bus (7098 WADSWORTH 3, zone "Far West"),
# leaving Laredo with no reference bus. Promote its largest generator (4026 CHRISTINE 2,
# PG=408.9 MW) to swing (IDE=3) so FNSL has a bus to solve the island against.
out += promote_to_swing(filter_by_first_field(lines[3:bus_end], keep_buses), swing_bus=4026)
out.append(lines[bus_end])
out += filter_by_first_field(lines[bus_end + 1:load_end], keep_buses)
out.append(lines[load_end])
out += filter_by_first_field(lines[load_end + 1:fixshunt_end], keep_buses)
out.append(lines[fixshunt_end])
out += filter_by_first_field(lines[fixshunt_end + 1:gen_end], keep_buses)
out.append(lines[gen_end])
out += filter_branches(lines[gen_end + 1:branch_end], keep_buses)
out.append(lines[branch_end])
out += filter_transformers(lines[branch_end + 1:trafo_end], keep_buses)
out += lines[trafo_end:facts_end + 1]
out += filter_by_first_field(lines[facts_end + 1:swshunt_end], keep_buses)
out += lines[swshunt_end:]

with open(dst_name, "w") as f:
    f.writelines(out)

print(f"Saved to {dst_name}")

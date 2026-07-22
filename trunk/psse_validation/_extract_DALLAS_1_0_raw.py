import os

folder = "data"
src_name = os.path.join(folder, "ACTIVSg2000.RAW")
dst_name = os.path.join(folder, "DALLAS_1_0.raw")

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


def filter_branches_touching(block_lines: list[str], root_buses: set[int]) -> list[str]:
    """Keep line records that touch a root bus on either end (I or J) - the vicinity=1 rule."""
    kept = list()
    for l in block_lines:
        fields = l.split(',')
        if bus_num(fields[0]) in root_buses or bus_num(fields[1]) in root_buses:
            kept.append(l)
    return kept


def filter_transformers_touching(block_lines: list[str], root_buses: set[int]) -> list[str]:
    """
    Keep whole 2-winding transformer records (4 physical lines each) that touch a root
    bus on either end (I or J) of the record's first line - the vicinity=1 rule.
    ACTIVSg2000 has no 3-winding transformers, so every record here is a fixed 4-line
    block (verified below by the modulo check instead of assumed silently).
    """
    assert len(block_lines) % 4 == 0, "Unexpected transformer block size - a 3-winding (5-line) record may be present"
    kept = list()
    for i in range(0, len(block_lines), 4):
        block = block_lines[i:i + 4]
        fields = block[0].split(',')
        if bus_num(fields[0]) in root_buses or bus_num(fields[1]) in root_buses:
            kept.extend(block)
    return kept


def collect_endpoints(branch_lines: list[str], transformer_blocks: list[str]) -> set[int]:
    """Collect every I/J bus number referenced by a set of (already-filtered) branch/transformer records."""
    endpoints: set[int] = set()
    for l in branch_lines:
        fields = l.split(',')
        endpoints.add(bus_num(fields[0]))
        endpoints.add(bus_num(fields[1]))
    for i in range(0, len(transformer_blocks), 4):
        fields = transformer_blocks[i].split(',')
        endpoints.add(bus_num(fields[0]))
        endpoints.add(bus_num(fields[1]))
    return endpoints


# --- collect the buses belonging to substation "DALLAS 1" straight from the Bus Data ---
# --- NAME field, matching on whitespace-split tokens so "DALLAS 1 *" is not confused ---
# --- with "DALLAS 10 *", "DALLAS 11 *", etc. ---
dallas1_buses: set[int] = set()
for l in lines[3:bus_end]:
    fields = l.split(',')
    name_tokens = fields[1].strip().strip("'").split()
    if len(name_tokens) >= 3 and name_tokens[0] == "DALLAS" and name_tokens[1] == "1":
        dallas1_buses.add(bus_num(fields[0]))

print(f"DALLAS 1 substation buses found: {sorted(dallas1_buses)}")

# --- expand to the immediate one-hop neighborhood (vicinity=1, matching the GUI's ---
# --- "New diagram from selection"): keep every branch/transformer touching a root bus, ---
# --- then keep_buses is the root set plus whatever buses those records reach out to. ---
# --- Branches purely between two neighbor buses (not touching a root bus) are excluded, ---
# --- same as the GUI's one-hop expansion. ---
kept_branches = filter_branches_touching(lines[gen_end + 1:branch_end], dallas1_buses)
kept_transformer_blocks = filter_transformers_touching(lines[branch_end + 1:trafo_end], dallas1_buses)
keep_buses = dallas1_buses | collect_endpoints(kept_branches, kept_transformer_blocks)

print(f"One-hop neighbor buses added: {sorted(keep_buses - dallas1_buses)}")

# --- pick the swing bus: the substation has no IDE=3 bus of its own, so promote its ---
# --- largest in-service generator (ties broken by file order) to swing (IDE=3) so ---
# --- FNSL has a reference bus to solve the isolated substation against. Scoped to the ---
# --- substation's own buses, not the neighborhood, since the swing should belong to ---
# --- the substation being extracted. ---
substation_generators = filter_by_first_field(lines[fixshunt_end + 1:gen_end], dallas1_buses)
swing_bus = None
best_pg = None
for l in substation_generators:
    fields = l.split(',')
    stat = int(fields[14].strip())
    pg = float(fields[2].strip())
    if stat == 1 and (best_pg is None or pg > best_pg):
        best_pg = pg
        swing_bus = bus_num(fields[0])
if swing_bus is None:
    raise Exception("No active generator found in substation DALLAS 1 to promote to swing")

print(f"Swing bus: {swing_bus} (PG={best_pg} MW)")

# --- reassemble the file, filtering only the bus-referencing sections and leaving ---
# --- area/zone/owner/DC/FACTS/GNE declarations and the header/terminator untouched. ---
# --- Single-line records (load, fixed shunt, generator, switched shunt) are filtered ---
# --- against the expanded keep_buses set, so neighbor buses keep their own devices too. ---
out: list[str] = list()
out += lines[0:3]
out += promote_to_swing(filter_by_first_field(lines[3:bus_end], keep_buses), swing_bus=swing_bus)
out.append(lines[bus_end])
out += filter_by_first_field(lines[bus_end + 1:load_end], keep_buses)
out.append(lines[load_end])
out += filter_by_first_field(lines[load_end + 1:fixshunt_end], keep_buses)
out.append(lines[fixshunt_end])
out += filter_by_first_field(lines[fixshunt_end + 1:gen_end], keep_buses)
out.append(lines[gen_end])
out += kept_branches
out.append(lines[branch_end])
out += kept_transformer_blocks
out += lines[trafo_end:facts_end + 1]
out += filter_by_first_field(lines[facts_end + 1:swshunt_end], keep_buses)
out += lines[swshunt_end:]

with open(dst_name, "w") as f:
    f.writelines(out)

print(f"Saved to {dst_name}")

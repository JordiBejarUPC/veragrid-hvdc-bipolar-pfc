import pandas as pd

def parse_pwf_to_gridcal(pwf_file, output_excel):
    buses, gens, lines, loads, shunts = [], [], [], [], []

    with open(pwf_file, "r", encoding="latin-1", errors="ignore") as f:
        in_data = False
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Start after 99999 marker
            if line.startswith("99999"):
                in_data = True
                continue
            if not in_data:
                continue

            parts = line.replace(",", " ").split()
            card = parts[0].upper()

            # --- Buses ---
            if card == "DBAR":
                bus = int(parts[1])
                name = parts[2]
                kv = float(parts[3])
                bustype = int(parts[4])  # 0=PQ, 1=PV, 2=Slack
                vmin = float(parts[5]) if len(parts) > 5 else 0.9
                vmax = float(parts[6]) if len(parts) > 6 else 1.1
                buses.append([bus, name, kv, bustype, vmin, vmax])

            # --- Generators ---
            elif card == "DGER":
                bus = int(parts[1])
                pmax = float(parts[2])
                pmin = float(parts[3])
                qmax = float(parts[4])
                qmin = float(parts[5])
                vset = float(parts[6]) if len(parts) > 6 else 1.0
                gens.append([bus, pmax, pmin, qmax, qmin, vset])

            # --- Branches ---
            elif card == "DLIN":
                fbus = int(parts[1])
                tbus = int(parts[2])
                r = float(parts[3])
                x = float(parts[4])
                b = float(parts[5]) if len(parts) > 5 else 0.0
                rateA = float(parts[6]) if len(parts) > 6 else 0.0
                lines.append([fbus, tbus, r, x, b, rateA])

            # --- Loads ---
            elif card == "DCAR":
                bus = int(parts[1])
                pl = float(parts[2])
                ql = float(parts[3])
                loads.append([bus, pl, ql])

            # --- Shunts ---
            elif card == "DSHR":
                bus = int(parts[1])
                b = float(parts[2])
                shunts.append([bus, b])

    # Convert to DataFrames
    df_buses = pd.DataFrame(buses, columns=["Bus", "Name", "Vnom(kV)", "Type", "Vmin", "Vmax"])
    df_gens  = pd.DataFrame(gens, columns=["Bus", "Pmax", "Pmin", "Qmax", "Qmin", "Vset"])
    df_lines = pd.DataFrame(lines, columns=["From", "To", "R", "X", "B", "RateA"])
    df_loads = pd.DataFrame(loads, columns=["Bus", "P (MW)", "Q (Mvar)"])
    df_shunt = pd.DataFrame(shunts, columns=["Bus", "B"])

    # Save to Excel
    with pd.ExcelWriter(output_excel) as writer:
        df_buses.to_excel(writer, sheet_name="Buses", index=False)
        df_gens.to_excel(writer, sheet_name="Generators", index=False)
        df_lines.to_excel(writer, sheet_name="Branches", index=False)
        df_loads.to_excel(writer, sheet_name="Loads", index=False)
        df_shunt.to_excel(writer, sheet_name="Shunts", index=False)

    print(f"Converted {pwf_file} → {output_excel}")
"""
pfgrid.py
---------
A helper library for extracting and creating grid models in DIgSILENT PowerFactory
via the Python COM API.

NOTE: This is pure chat gpt...needs to be checked

Usage:
    import powerfactory as pf
    from pfgrid import PFGrid

    app = pf.GetApplication()
    app.ActivateProject("MyProject")

    grid = PFGrid(app)
    data = grid.extract_all()     # Extract entire network
    grid.to_json("grid.json")     # Save to JSON

    grid2 = PFGrid(app)
    grid2.from_json("grid.json")
    grid2.rebuild()               # Create devices back in PF
"""

import json
import powerfactory as pf


class PFGrid:
    def __init__(self, app):
        self.app = app
        self.data = {
            "buses": [],
            "lines": [],
            "transformers_2w": [],
            "transformers_3w": [],
            "shunts": [],
            "loads": [],
            "gens_sync": [],
            "gens_async": [],
            "gens_pv": [],
            "ext_grids": [],
            "switches": [],
        }
        # Map for quick lookup of created buses by name
        self._bus_map = {}

    # ----------------------------------------------------------------------
    # Extract Methods
    # ----------------------------------------------------------------------
    # (same as before – buses, lines, trafos, loads, gens, etc.)
    # ----------------------------------------------------------------------

    def extract_all(self):
        self.extract_buses()
        self.extract_lines()
        self.extract_transformers_2w()
        self.extract_transformers_3w()
        self.extract_shunts()
        self.extract_loads()
        self.extract_gens_sync()
        self.extract_gens_async()
        self.extract_gens_pv()
        self.extract_ext_grids()
        self.extract_switches()
        return self.data

    # ----------------------------------------------------------------------
    # JSON helpers
    # ----------------------------------------------------------------------
    def to_json(self, path):
        with open(path, "w") as f:
            json.dump(self.data, f, indent=2)

    def from_json(self, path):
        with open(path, "r") as f:
            self.data = json.load(f)

    # ----------------------------------------------------------------------
    # Creation Methods
    # ----------------------------------------------------------------------
    def create_bus(self, name, u_nom=110.0):
        bus = self.app.GetActiveProject().CreateObject("ElmTerm", name)
        bus.uknom = u_nom
        self._bus_map[name] = bus
        return bus

    def create_line(self, name, bus1_name, bus2_name, r=0.01, x=0.1, b=0.0, g=0.0):
        line = self.app.GetActiveProject().CreateObject("ElmLne", name)
        line.bus1 = self._bus_map.get(bus1_name)
        line.bus2 = self._bus_map.get(bus2_name)
        line.rline, line.xline, line.bline, line.gline = r, x, b, g
        return line

    def create_transformer_2w(self, name, bus1_name, bus2_name, sn=100.0, uk=10.0,
                              pCu=0.0, pFe=0.0, tap_side=0, tap_pos=0, tap_step=1.0):
        tr = self.app.GetActiveProject().CreateObject("ElmTr2", name)
        tr.bus1 = self._bus_map.get(bus1_name)
        tr.bus2 = self._bus_map.get(bus2_name)
        tr.strn, tr.uktr, tr.pCu, tr.pFe = sn, uk, pCu, pFe
        tr.tap_side, tr.nntap, tr.dutap = tap_side, tap_pos, tap_step
        return tr

    def create_transformer_3w(self, name, bus1_name, bus2_name, bus3_name,
                              sn1=100, sn2=100, sn3=50, uk12=10, uk23=10, uk13=10):
        tr = self.app.GetActiveProject().CreateObject("ElmTr3", name)
        tr.bus1 = self._bus_map.get(bus1_name)
        tr.bus2 = self._bus_map.get(bus2_name)
        tr.bus3 = self._bus_map.get(bus3_name)
        tr.strn1, tr.strn2, tr.strn3 = sn1, sn2, sn3
        tr.uk12, tr.uk23, tr.uk13 = uk12, uk23, uk13
        return tr

    def create_shunt(self, name, bus_name, q=10.0, u_nom=110.0):
        sh = self.app.GetActiveProject().CreateObject("ElmShnt", name)
        sh.bus1 = self._bus_map.get(bus_name)
        sh.qcapn = q
        sh.uknom = u_nom
        return sh

    def create_load(self, name, bus_name, p=10.0, q=2.0, cosphi=1.0, scale=1.0):
        ld = self.app.GetActiveProject().CreateObject("ElmLod", name)
        ld.bus1 = self._bus_map.get(bus_name)
        ld.plini, ld.qlini = p, q
        ld.pf_recap, ld.scale0 = cosphi, scale
        return ld

    def create_gen_sync(self, name, bus_name, p=0.0, q=0.0, sn=100.0,
                        p_max=100.0, p_min=0.0, q_max=50.0, q_min=-50.0,
                        cosphi=1.0, ra=0.0, xd=0.2, xq=0.2, ngnum=1):
        g = self.app.GetActiveProject().CreateObject("ElmSym", name)
        g.bus1 = self._bus_map.get(bus_name)
        g.pgini, g.qgini = p, q
        g.strn, g.pgini_max, g.pgini_min = sn, p_max, p_min
        g.qgini_max, g.qgini_min = q_max, q_min
        g.cosn, g.ra, g.xd, g.xq = cosphi, ra, xd, xq
        g.ngnum = ngnum
        return g

    def create_gen_async(self, name, bus_name, p=0.0, sn=100.0, slip=0.01):
        g = self.app.GetActiveProject().CreateObject("ElmAsm", name)
        g.bus1 = self._bus_map.get(bus_name)
        g.pgini, g.strn, g.slip = p, sn, slip
        return g

    def create_gen_pv(self, name, bus_name, p=0.0, q=0.0,
                      p_max=100.0, p_min=0.0, q_max=50.0, q_min=-50.0,
                      cosphi=1.0, qctrl=0):
        g = self.app.GetActiveProject().CreateObject("ElmGenstat", name)
        g.bus1 = self._bus_map.get(bus_name)
        g.pgini, g.qgini = p, q
        g.pmax, g.pmin, g.qmax, g.qmin = p_max, p_min, q_max, q_min
        g.cosn, g.qctrl = cosphi, qctrl
        return g

    def create_ext_grid(self, name, bus_name, u_nom=110.0, p=0.0, q=0.0):
        x = self.app.GetActiveProject().CreateObject("ElmXnet", name)
        x.bus1 = self._bus_map.get(bus_name)
        x.uknom, x.pgini, x.qgini = u_nom, p, q
        return x

    def create_switch(self, name, bus1_name, bus2_name, on_off=1, i_nom=1000.0):
        sw = self.app.GetActiveProject().CreateObject("StaSwitch", name)
        sw.bus1 = self._bus_map.get(bus1_name)
        sw.bus2 = self._bus_map.get(bus2_name)
        sw.on_off = on_off
        sw.Inom = i_nom
        return sw

    # ----------------------------------------------------------------------
    # Rebuild from JSON data
    # ----------------------------------------------------------------------
    def rebuild(self):
        """
        Recreate all objects in PowerFactory from self.data.
        Buses must be created first, then everything else.
        """
        # Buses
        for b in self.data["buses"]:
            self.create_bus(b["name"], u_nom=b.get("uknom", 110.0))

        # Lines
        for l in self.data["lines"]:
            self.create_line(l["name"], l["bus1"], l["bus2"],
                             r=l.get("r", 0.0), x=l.get("x", 0.0),
                             b=l.get("b", 0.0), g=l.get("g", 0.0))

        # Transformers 2w
        for t in self.data["transformers_2w"]:
            self.create_transformer_2w(t["name"], t["bus1"], t["bus2"],
                                       sn=t.get("sn", 100.0), uk=t.get("uk", 10.0),
                                       pCu=t.get("pCu", 0.0), pFe=t.get("pFe", 0.0),
                                       tap_side=t.get("tap_side", 0),
                                       tap_pos=t.get("tap_pos", 0),
                                       tap_step=t.get("tap_step", 1.0))

        # Transformers 3w
        for t in self.data["transformers_3w"]:
            self.create_transformer_3w(t["name"], t["bus1"], t["bus2"], t["bus3"],
                                       sn1=t.get("sn1", 100.0), sn2=t.get("sn2", 100.0), sn3=t.get("sn3", 50.0),
                                       uk12=t.get("uk12", 10.0), uk23=t.get("uk23", 10.0), uk13=t.get("uk13", 10.0))

        # Shunts
        for s in self.data["shunts"]:
            self.create_shunt(s["name"], s["bus"], q=s.get("qcapn", 10.0), u_nom=s.get("uknom", 110.0))

        # Loads
        for l in self.data["loads"]:
            self.create_load(l["name"], l["bus"], p=l.get("p", 0.0), q=l.get("q", 0.0),
                             cosphi=l.get("cosphi", 1.0), scale=l.get("scale", 1.0))

        # Synchronous Generators
        for g in self.data["gens_sync"]:
            self.create_gen_sync(g["name"], g["bus"], p=g.get("p_init", 0.0), q=g.get("q_init", 0.0),
                                 sn=g.get("sn", 100.0), p_max=g.get("p_max", 100.0), p_min=g.get("p_min", 0.0),
                                 q_max=g.get("q_max", 50.0), q_min=g.get("q_min", -50.0),
                                 cosphi=g.get("cosphi", 1.0), ra=g.get("ra", 0.0),
                                 xd=g.get("xd", 0.2), xq=g.get("xq", 0.2),
                                 ngnum=g.get("ngnum", 1))

        # Asynchronous Generators
        for g in self.data["gens_async"]:
            self.create_gen_async(g["name"], g["bus"], p=g.get("p_init", 0.0),
                                  sn=g.get("sn", 100.0), slip=g.get("slip", 0.01))

        # PV Generators
        for g in self.data["gens_pv"]:
            self.create_gen_pv(g["name"], g["bus"], p=g.get("p_init", 0.0), q=g.get("q_init", 0.0),
                               p_max=g.get("p_max", 100.0), p_min=g.get("p_min", 0.0),
                               q_max=g.get("q_max", 50.0), q_min=g.get("q_min", -50.0),
                               cosphi=g.get("cosphi", 1.0), qctrl=g.get("qctrl", 0))

        # External Grids
        for x in self.data["ext_grids"]:
            self.create_ext_grid(x["name"], x["bus"], u_nom=x.get("uknom", 110.0),
                                 p=x.get("pgini", 0.0), q=x.get("qgini", 0.0))

        # Switches
        for s in self.data["switches"]:
            self.create_switch(s["name"], s["bus1"], s["bus2"],
                               on_off=s.get("on_off", 1), i_nom=s.get("i_nom", 1000.0))

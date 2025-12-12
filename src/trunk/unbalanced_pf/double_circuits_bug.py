import VeraGridEngine.api as vge

tower = vge.OverheadLineType(name="Tower", Vnom=10)

wire = vge.Wire(name="-_ACSR_0.902",
                r=0.857492,
                diameter=9.02,
                diameter_internal=0.0,
                is_tube=False,
                max_current=0.177,
                stranding='-',
                material='ACSR')

tower.add_wire_relationship(wire=wire, xpos=0, ypos=20, phase=0)

tower.add_wire_relationship(wire=wire, xpos=-3, ypos=18, phase=1)
# tower.add_wire_relationship(wire=wire, xpos=-3, ypos=16, phase=2)
tower.add_wire_relationship(wire=wire, xpos=-3, ypos=14, phase=3)

tower.add_wire_relationship(wire=wire, xpos=0, ypos=18, phase=4)
# tower.add_wire_relationship(wire=wire, xpos=0, ypos=16, phase=5)
tower.add_wire_relationship(wire=wire, xpos=0, ypos=14, phase=6)

tower.add_wire_relationship(wire=wire, xpos=3, ypos=18, phase=7)
# tower.add_wire_relationship(wire=wire, xpos=3, ypos=16, phase=8)
tower.add_wire_relationship(wire=wire, xpos=3, ypos=14, phase=9)

tower.compute()

# z = tower.z_nabc
# print("Z [ohm/km] =\n", z)
#
# ys = tower.get_ys(circuit_idx=1,
#                   Sbase=100,
#                   length=1,
#                   Vnom=10)
#
# ysh = tower.get_ysh(circuit_idx=1,
#                     Sbase=100,
#                     length=1,
#                     Vnom=10)

# Line

bus1 = vge.Bus(name="Bus 1", Vnom=10)
bus2 = vge.Bus(name="Bus 2", Vnom=10)
line = vge.Line(name="Line", bus_from=bus1, bus_to=bus2, length=1)

line.apply_template(tower, 100, 50)
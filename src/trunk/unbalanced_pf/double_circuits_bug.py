import VeraGridEngine.api as vge

tower = vge.OverheadLineType(name="Tower")

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
tower.add_wire_relationship(wire=wire, xpos=-3, ypos=16, phase=2)
tower.add_wire_relationship(wire=wire, xpos=-3, ypos=14, phase=3)

tower.add_wire_relationship(wire=wire, xpos=0, ypos=18, phase=4)
tower.add_wire_relationship(wire=wire, xpos=0, ypos=16, phase=5)
tower.add_wire_relationship(wire=wire, xpos=0, ypos=14, phase=6)

tower.add_wire_relationship(wire=wire, xpos=3, ypos=18, phase=7)
tower.add_wire_relationship(wire=wire, xpos=3, ypos=16, phase=8)
tower.add_wire_relationship(wire=wire, xpos=3, ypos=14, phase=9)

tower.compute()

Z = tower.z_nabc
print("Z [ohm/km] =\n", Z)

Ys = tower.get_ys(circuit_idx=3,
                  Sbase=100,
                  length=1,
                  Vnom=10)
print(Ys.values)
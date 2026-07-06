import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes

# Base Params
Ub = 525
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb / Ub

#Converter Losses Params
# a = 0.5515/Sb
# b = 0.887*(Ib/Sb)
# c = 3.77*((Ib**2)/Sb)

a = 0
b = 0
c = 0


# Land Cable Params
r_ohm_m_land = 1.7241e-8  # [Ωm]
a_mm2_land = 3000  # [mm2]
d_m_land = 1000  # [m]
a_m2_land = a_mm2_land * 1e-6
# R = rho * (L / A)
r_ohm_km_land = r_ohm_m_land * (d_m_land / a_m2_land)  # ohm/km
r_pu_km_land = r_ohm_km_land / Rb

# Sea Cable Params
r_ohm_m_sea = 1.7241e-8  # [Ωm]
a_mm2_sea = 2500  # [mm2]
d_m_sea = 1000  # [m]
a_m2_sea = a_mm2_sea * 1e-6
# R = rho * (L / A)
r_ohm_km_sea = r_ohm_m_sea * (d_m_sea / a_m2_sea)  # ohm/km
r_pu_km_sea = r_ohm_km_sea / Rb

# Distances in Km
d0a = 12
d0c = 12
d1 = 300
d2 = 200
d3 = 400
d4a = 150
d4b = 150
d5 = 200

grid = gce.MultiCircuit(
    name="4TerminalsBipolarSystem",
    Sbase=Sb
)

# Buses (name, Vnom, is_dc, Grounded, Slack) #
d_buses = {
    1: ("Bus1_ac", Ub, False, False, True),
    2: ("Bus2_ac", Ub, False, False, True),
    3: ("Bus3_ac", Ub, False, False, False),
    4: ("Bus4_ac", Ub, False, False, False),
    # Positive pole DC buses
    5: ("Bus0a_dc_+", Ub, True, False, False),
    6: ("Bus0c_dc_+", Ub, True, False, False),
    7: ("Bus1_dc_+", Ub, True, False, False),
    8: ("Bus2_dc_+", Ub, True, False, False),
    9: ("Bus3_dc_+", Ub, True, False, False),
    10: ("Bus4_dc_+", Ub, True, False, False),
    11: ("Bus5_dc_+", Ub, True, False, False),
    # DMR pole DC buses
    12: ("Bus0a_dc_0+", Ub, True, False, False),
    13: ("Bus0c_dc_0+", Ub, True, False, False),
    14: ("Bus0a_dc_0-", Ub, True, False, False),
    15: ("Bus0c_dc_0-", Ub, True, False, False),
    16: ("Bus1_dc_0", Ub, True, False, False),
    17: ("Bus2_dc_0", Ub, True, False, False),
    18: ("Bus3_dc_0", Ub, True, True, False),  # grounded bus
    19: ("Bus4_dc_0", Ub, True, False, False),
    20: ("Bus5_dc_0", Ub, True, False, False),
    # Negative pole DC buses
    21: ("Bus0a_dc_-", Ub, True, False, False),
    22: ("Bus0c_dc_-", Ub, True, False, False),
    23: ("Bus1_dc_-", Ub, True, False, False),
    24: ("Bus2_dc_-", Ub, True, False, False),
    25: ("Bus3_dc_-", Ub, True, False, False),
    26: ("Bus4_dc_-", Ub, True, False, False),
    27: ("Bus5_dc_-", Ub, True, False, False)
}

for key, data in d_buses.items():
    bus_name = data[0]
    v_nom = data[1]
    is_dc = data[2]
    is_grounded = data[3]
    is_slack = data[4]
    if "_0" in bus_name:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded, Vm0=0.0001, Va0=0.001)

    elif "_-" in bus_name:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded, Vm0=1.00, Va0=np.pi)

    else:
        busi = gce.Bus(name=bus_name, Vnom=v_nom, is_slack=is_slack, is_dc=is_dc, is_grounded=is_grounded)

    grid.add_bus(busi)
    globals()[f"bus{key}"] = busi


#HVDC lines#
d_lines = {1:(bus5,bus7,12, "dc_cable0a_+","land"), 2:(bus6, bus10, 12, "dc_cable0c_+","land"), 3:(bus7, bus8, 300, "dc_cable1_+","sea"), 4:(bus7, bus9, 150, "dc_cable4a_+","sea"), 5:(bus9, bus10, 150, "dc_cable4b_+","sea"), 6:(bus7, bus11, 400, "dc_cable3_+","sea"), 7:(bus8, bus11, 200, "dc_cable2_+","sea"), 8:(bus10, bus11, 200, "dc_cable5_+","sea"),
           9:(bus12,bus16,12, "dc_cable0a_0+","land"), 10:(bus13,bus19,12, "dc_cable0c_0+","land"), 11:(bus14,bus16,12, "dc_cable0a_0-","land"), 12:(bus15,bus19,12, "dc_cable0c_0-","land"), 13:(bus16, bus17, 300, "dc_cable1_0","sea"), 14:(bus16, bus18, 150, "dc_cable4a_0","sea"), 15:(bus18, bus19, 150, "dc_cable4b_0","sea"), 16:(bus16, bus20, 400, "dc_cable3_0","sea"), 17:(bus17, bus20, 200, "dc_cable2_0","sea"), 18:(bus19, bus20, 200, "dc_cable5_0","sea"),
           19:(bus21,bus23,12, "dc_cable0a_-","land"), 20:(bus22, bus26, 12, "dc_cable0c_-","land"), 21:(bus23, bus24, 300, "dc_cable1_-","sea"), 22:(bus23, bus25, 150, "dc_cable4a_-","sea"), 23:(bus25, bus26, 150, "dc_cable4b_-","sea"), 24:(bus23, bus27, 400, "dc_cable3_-","sea"), 25:(bus24, bus27, 200, "dc_cable2_-","sea"), 26:(bus26, bus27, 200, "dc_cable5_-","sea")
           }

for key, data in d_lines.items():
    # data[0]=bus_from, data[1]=bus_to, data[2]=dist, data[3]=name, data[4]=type
    if data[4] == "land":
        grid.add_dc_line(gce.DcLine(name=data[3],
                                    bus_from=data[0],
                                    bus_to=data[1],
                                    r=r_pu_km_land,
                                    length=data[2]))
    else:
        grid.add_dc_line(gce.DcLine(name=data[3],
                                    bus_from=data[0],
                                    bus_to=data[1],
                                    r=r_pu_km_sea,
                                    length=data[2]))

# Generators
# AC grids
grid.add_generator(bus1, gce.Generator(name="AC grid 1",
                                       vset=1.0))

grid.add_generator(bus2, gce.Generator(name="AC grid 2",
                                       vset=1.0))

# OWFs
grid.add_generator(bus3, gce.Generator(name="OWF 1",
                                       vset=1.0,
                                       P=3000))

grid.add_generator(bus4, gce.Generator(name="OWF 2",
                                       vset=1.0,
                                       P=3000))

# VSC#
# positive pole vsc
grid.add_vsc(gce.VSC(name="VSC_1+",
                     bus_to=bus1,
                     bus_from=bus5,
                     bus_dc_n=bus12,
                     rate = 3000,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc_droop,
                     control1_val=1,
                     control1_val_min=-3000,
                     control1_val_max=3000,
                     control1_droop=1,
                     control1_droop_val=1.0,
                     control1_droop_val_min=0.9,
                     control1_droop_val_max=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2+",
                     bus_to=bus2,
                     bus_from=bus6,
                     bus_dc_n=bus13,
                     rate = 3000,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc_droop,
                     control1_val=1,
                     control1_val_min=-3000,
                     control1_val_max=3000,
                     control1_droop=1,
                     control1_droop_val=1.0,
                     control1_droop_val_min=0.9,
                     control1_droop_val_max=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_3+",
                     bus_to=bus3,
                     bus_from=bus8,
                     bus_dc_n=bus17,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_4+",
                     bus_to=bus4,
                     bus_from=bus11,
                     bus_dc_n=bus20,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))

# Negative pole vsc
grid.add_vsc(gce.VSC(name="VSC_1-",
                     bus_to=bus1,
                     bus_from=bus21,
                     bus_dc_n=bus14,
                     rate = 3000,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc_droop,
                     control1_val=1,
                     control1_val_min=-3000,
                     control1_val_max=3000,
                     control1_droop=1,
                     control1_droop_val=1.0,
                     control1_droop_val_min=0.9,
                     control1_droop_val_max=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2-",
                     bus_to=bus2,
                     bus_from=bus22,
                     bus_dc_n=bus15,
                     rate = 3000,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc_droop,
                     control1_val=1,
                     control1_val_min=-3000,
                     control1_val_max=3000,
                     control1_droop=1,
                     control1_droop_val=1.0,
                     control1_droop_val_min=0.9,
                     control1_droop_val_max=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_3-",
                     bus_to=bus3,
                     bus_from=bus24,
                     bus_dc_n=bus17,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=1500,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_4-",
                     bus_to=bus4,
                     bus_from=bus27,
                     bus_dc_n=bus20,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pac,
                     control2=ConverterControlType.Qac,
                     control1_val=1500,
                     control2_val=0.0))

gce.save_file(grid=grid, filename="grids/4TerminalsBipolarSystem_drop.veragrid")

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  use_stored_guess=True,
                                  tolerance=1e-9,
                                  )
results = gce.power_flow(grid, options=options_pf)

print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())




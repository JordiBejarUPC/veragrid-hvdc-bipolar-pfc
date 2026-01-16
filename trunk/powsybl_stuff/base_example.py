import pypowsybl as pp

network = pp.network.load('/Users/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE 14 bus.raw',
                          {'psse.import.ignore-base-voltage': 'true'})
# network = pp.network.create_ieee14()
results = pp.loadflow.run_ac(network)
print(results)

buses = network.get_buses()
print(buses)

print(pp.network.get_import_formats())

# network.save('network.ucte', format='UCTE')

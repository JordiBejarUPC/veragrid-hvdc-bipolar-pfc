from VeraGridEngine.IO.ucte.devices.ucte_line import UcteLine, Logger
from VeraGridEngine.IO.ucte.devices.ucte_node import UcteNode


lne = UcteLine()
logger = Logger()
lne.parse("0BERAN51 0ANDRI51 1 0 3.4360 7.4640 48.67800    480              ", logger)

print(logger.to_df())


node = UcteNode()
node.parse("OYPBEU21 YbbsPersenbe 0 0              0 12.3484 -59.428       0       0 -238.80 12.3484       0                                 ", logger)

print(logger.to_df())

print()

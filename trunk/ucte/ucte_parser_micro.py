from VeraGridEngine.IO.ucte.devices.ucte_line import UcteLine, Logger
from VeraGridEngine.IO.ucte.devices.ucte_node import UcteNode


lne = UcteLine()
logger = Logger()
# lne.parse("D7BUER2C D7MAXA2C 1 0 2.1230 19.580 361.1010   1300 WEINGT       ", logger)

print(logger.to_df())


node = UcteNode()
node.parse("OYPBEU21 YbbsPersenbe 0 0              0 12.3484 -59.428       0       0 -238.80 12.3484       0                                 ", logger)



print(logger.to_df())

print()

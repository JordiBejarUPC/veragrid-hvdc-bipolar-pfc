from VeraGridEngine.IO.ucte.devices.ucte_line import UcteLine, Logger


lne = UcteLine()
logger = Logger()
lne.parse("D7BUER2C D7MAXA2C 1 0 2.1230 19.580 361.1010   1300 WEINGT       ", logger)

print(logger.to_df())

print()

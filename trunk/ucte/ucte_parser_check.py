import logging
import VeraGridEngine as vg

if __name__ == "__main__":
    # fname = "/Users/santi/Git/eRoots/VeraGrid/src/tests/data/grids/ucte/12_node_network.uct"
    fname = "/home/santi/Git/eRoots/VeraGrid/src/tests/data/grids/ucte/tapPositionsRange.uct"
    parser = vg.FileOpen(file_name=fname)
    parser.open()
    print(parser.logger.to_df())

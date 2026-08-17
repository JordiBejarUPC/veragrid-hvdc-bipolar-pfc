import numba as nb
import VeraGridEngine as vg
from VeraGridEngine.Utils.Symbolic.Compiler.native_handler import NativeBlockCompiler, NativeBlockInterpreter

bl = vg.Block()

# Will save the block "dll" into "~/.VeraGrid/compiled/rms
compiler = NativeBlockCompiler(bl, folder="compiled/rms")


# This class will handle a previously compiled binary of a block
dll_handler = NativeBlockInterpreter(hash_code=compiler.hash_code, folder="compiled/rms")


# @nb.njit()
# def s(a, b):
#     return a + b

gens = [vg.Generator() for i in range(100)]

for g in gens:
    g.rms_model = bl


for g in gens:
    dll_handler = NativeBlockInterpreter(hash_code=g.rms_model.__hash__(), folder="compiled/rms")
    fn = dll_handler.fn()
    dfn = dll_handler.dfn()

# fn = dll_handler.fn_vec(params_mat)
# dfn = dll_handler.dfn_vec(params_mat)

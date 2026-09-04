import os
import subprocess
from llvmlite import binding as llvm

# Initialize specific native targets for machine code emission
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()


def compile_cpp_string_to_dll(cpp_code_string, output_dll_path):
    cpp_filename = "temp_code.cpp"
    obj_filename = "temp_code.obj" if os.name == 'nt' else "temp_code.o"

    try:
        with open(cpp_filename, "w") as f:
            f.write(cpp_code_string)

        # 1. Compile C++ into a machine object file (.o)
        clang_cmd = ["clang", "-c", "-O3", "-fPIC", cpp_filename, "-o", obj_filename]
        subprocess.run(clang_cmd, check=True, capture_output=True, text=True)

        # 2. Get the target machine details using llvmlite
        target_triple = llvm.get_process_triple()
        target = llvm.Target.from_triple(target_triple)

        # FIX: Changed 'codegen' to 'codemodel'
        target_machine = target.create_target_machine(reloc='pic', codemodel='default')

        # 3. Link the object file into a shared library (.so)
        link_cmd = ["clang", "-shared", obj_filename, "-o", output_dll_path]
        subprocess.run(link_cmd, check=True, capture_output=True, text=True)

        print(f"Success! Compiled to {output_dll_path}")

    finally:
        for temp_file in [cpp_filename, obj_filename]:
            if os.path.exists(temp_file):
                os.remove(temp_file)


# --- Test the Implementation ---
cpp_source = """
extern "C" {
    __attribute__((visibility("default"))) int add_numbers(int a, int b) {
        return a + b;
    }
}
"""

dll_path = "my_functions.so"
compile_cpp_string_to_dll(cpp_source, dll_path)

# ----------------------------------------------------------------------------------------------------------------------
# Load the function
# ----------------------------------------------------------------------------------------------------------------------

import ctypes
import os

# 1. Define the path to your compiled shared library
dll_path = "./my_functions.so"

# Quick check to ensure the file exists before loading
if not os.path.exists(dll_path):
    raise FileNotFoundError(f"Could not find the library at {dll_path}. Did you run the compilation script first?")

# 2. Load the shared library
# On Linux, use CDLL. (For Windows, it would also be CDLL or WinDLL)
my_lib = ctypes.CDLL(dll_path)

# 3. Define the function's argument and return types
# This ensures ctypes translates Python ints to C ints correctly
my_lib.add_numbers.argtypes = [ctypes.c_int, ctypes.c_int]
my_lib.add_numbers.restype = ctypes.c_int

# 4. Call the function
result = my_lib.add_numbers(35, 7)

print(f"Result from C++ function: {result}")

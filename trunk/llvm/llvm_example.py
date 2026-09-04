import os
import subprocess
import ctypes
from llvmlite import binding as llvm

# You need to install clang-tool-chain (pip install clang-tool-chain)

# 1. Initialize native target architectures for llvmlite's machine configuration
llvm.initialize_native_target()
llvm.initialize_native_asmprinter()


def compile_cpp_string_to_dll(cpp_code_string, output_dll_path):
    cpp_filename = "temp_code.cpp"
    obj_filename = "temp_code.obj" if os.name == 'nt' else "temp_code.o"

    # We use the python-provided clang wrapper from the 'clang-tool-chain' package
    compiler_cmd = "clang-tool-chain-cpp"

    try:
        # Write the source string out to disk
        with open(cpp_filename, "w") as f:
            f.write(cpp_code_string)

        # 2. Compile C++ to machine object file using the Python-packaged Clang binary
        print(f"Compiling via Python package compiler ({compiler_cmd})...")
        compile_args = [compiler_cmd, "-c", "-O3", "-fPIC", cpp_filename, "-o", obj_filename]
        subprocess.run(compile_args, check=True, capture_output=True, text=True)

        # 3. Pull Target Machine metadata using llvmlite
        target_triple = llvm.get_process_triple()
        target = llvm.Target.from_triple(target_triple)
        target_machine = target.create_target_machine(reloc='pic', codemodel='default')

        # 4. Link the object binary into a shared library via the Python-packaged Linker
        print("Linking object file into shared library binary...")
        link_args = [compiler_cmd, "-shared", obj_filename, "-o", output_dll_path]
        subprocess.run(link_args, check=True, capture_output=True, text=True)

        print(f"Success! Shared library generated at: {output_dll_path}\n")

    except FileNotFoundError:
        raise RuntimeError(
            "The packaged compiler could not be located. "
            "Please ensure you ran: pip install clang-tool-chain"
        )
    finally:
        # Clean up disk files safely
        for temp_file in [cpp_filename, obj_filename]:
            if os.path.exists(temp_file):
                os.remove(temp_file)


def load_and_verify_dll(dll_path):
    print(f"--- Loading {dll_path} via ctypes ---")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(f"Could not locate the generated binary at {dll_path}")

    # Explicitly pull absolute path to bypass relative directory loading issues
    abs_path = os.path.abspath(dll_path)
    my_lib = ctypes.CDLL(abs_path)

    # Strictly define ABI contract boundaries
    my_lib.add_numbers.argtypes = [ctypes.c_int, ctypes.c_int]
    my_lib.add_numbers.restype = ctypes.c_int

    # Execute the underlying compiled machine code
    param_a, param_b = 85, 15
    result = my_lib.add_numbers(param_a, param_b)
    print(f"Execution successful! Result of add_numbers({param_a}, {param_b}) = {result}")


# =====================================================================
# PIPELINE EXECUTION ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    # Multi-platform compatible C++ expression structure
    cpp_source = """
    extern "C" {
        #if defined(_WIN32) || defined(_WIN64)
            __declspec(dllexport) int add_numbers(int a, int b) { return a + b; }
        #else
            __attribute__((visibility("default"))) int add_numbers(int a, int b) { return a + b; }
        #endif
    }
    """

    # Automatically switch extension type relative to runtime platform context
    shared_lib_filename = "my_functions.dll" if os.name == 'nt' else "my_functions.so"

    # Step A: Compile using purely Python-installed components
    compile_cpp_string_to_dll(cpp_source, shared_lib_filename)

    # Step B: Load the file back into memory and verify operations
    load_and_verify_dll(shared_lib_filename)

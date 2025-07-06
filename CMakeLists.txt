# ==============================================================================
# CMakeLists.txt for GPMC
#
# This CMake configuration builds the GPMC Python extension module.
# It uses modern CMake practices and is designed for use with scikit-build-core.
#
# Key Features:
#   - Finds required dependencies (GMP, MPFR, ZLIB)
#   - Adds the flow-cutter-pace17 subdirectory
#   - Builds the gpmc Python module using scikit_build_add_python_module
#   - Sets compile options and definitions
#   - Links required libraries
#   - Installs the resulting module to the correct location for packaging
# ==============================================================================

cmake_minimum_required(VERSION 3.18)
project(gpmc CXX)

# ------------------------------------------------------------------------------
# 1. Find required dependencies
#    These libraries must be installed before building.
# ------------------------------------------------------------------------------
find_package(GMP REQUIRED)
find_package(MPFR REQUIRED)
find_package(ZLIB REQUIRED)

# ------------------------------------------------------------------------------
# 2. Add subdirectories
#    Add the flow-cutter-pace17 project as a subdirectory.
# ------------------------------------------------------------------------------
add_subdirectory(flow-cutter-pace17)

# ------------------------------------------------------------------------------
# 3. Build the Python extension module
#    - Uses scikit_build_add_python_module to create a Python-importable module.
#    - The module name (gpmc) will be used in Python as `import gpmc`.
#    - All relevant source files are listed here.
#    - Ensure core/Main.cc is a valid Python module entry point (e.g., uses PYBIND11_MODULE).
# ------------------------------------------------------------------------------
scikit_build_add_python_module(gpmc
    SOURCES
        core/ComponentCache.cc
        core/ComponentManager.cc
        core/Counter.cc
        core/Config.cc
        core/Instance.cc
        ddnnf/DecisionTree.cc
        core/Solver.cc
        c-mpfr/ComplexMPFR.cc
        utils/Options.cc
        utils/System.cc
        preprocessor/Preprocessor.cc
        preprocessor/TestSolver.cc
        preprocessor/lib_sharpsat_td/subsumer.cpp
        preprocessor/TreeDecomposition.cc
        preprocessor/IFlowCutter.cc
        core/Main.cc  # Python module entry point
)

# ------------------------------------------------------------------------------
# 4. Set compile options and definitions
#    - Applies warning and optimization flags.
#    - Sets preprocessor definitions for debug and standards compliance.
# ------------------------------------------------------------------------------
target_compile_options(gpmc PRIVATE
    -Wall
    -Wno-parentheses
    -Wno-format
    -Wno-sign-compare
    -Wno-unused-variable
    -Wno-unused-result
    "$<$<CONFIG:Debug>:-O0>"
    "$<$<CXX_COMPILER_ID:GNU>:-Wno-literal-suffix;-Wno-class-memaccess>"
    "$<$<CXX_COMPILER_ID:Clang>:-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>"
    "$<$<CXX_COMPILER_ID:AppleClang>:-Wno-redundant-move;-Wno-undefined-var-template;-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init;-std=c++11>"
)

target_compile_definitions(gpmc PRIVATE
    "$<$<CONFIG:Debug>:DEBUG>"
    __STDC_FORMAT_MACROS
    __STDC_LIMIT_MACROS
)

# ------------------------------------------------------------------------------
# 5. Link libraries
#    - Links the gpmc module to flowcutter and system libraries.
#    - Uses modern target-based linking for safety and clarity.
# ------------------------------------------------------------------------------
target_link_libraries(gpmc PRIVATE
    flowcutter
    ZLIB::ZLIB
    MPFR::MPFR
    GMP::GMP
    # gmpxx is usually not needed if GMP::GMP includes C++ bindings
)

# ------------------------------------------------------------------------------
# 6. Install the built module
#    - Installs the compiled gpmc module to the wheel's src/QuPRS/utils directory.
#    - This path should match the wheel.install-dir in pyproject.toml.
# ------------------------------------------------------------------------------
install(
    TARGETS gpmc
    DESTINATION src/QuPRS/utils
)
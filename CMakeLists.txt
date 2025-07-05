# GPMC/CMakeLists.txt
cmake_minimum_required(VERSION 3.15)

project(gpmc LANGUAGES CXX)

# --- 1. Use find_package to automatically locate dependencies ---
# This is the core of modern CMake, replacing all hardcoded paths.
# It will automatically search for libraries in system, Homebrew, Conda, etc.
find_package(GMP REQUIRED)
find_package(MPFR REQUIRED)
find_package(ZLIB REQUIRED)

# --- 2. Compile options ---
# Create an option to decide whether to build the final executable statically
option(GPMC_STATIC_BUILD "Build gpmc as a static executable" OFF)

# Organize compile flags to be applied to targets later
set(GPMC_COMPILE_FLAGS "-Wall;-Wno-parentheses;-Wno-format;-Wno-sign-compare;-Wno-unused-variable;-Wno-unused-result")
set(GPMC_GNU_FLAGS "-Wno-literal-suffix;-Wno-class-memaccess")
set(GPMC_CLANG_FLAGS "-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init")
set(GPMC_APPLECLANG_FLAGS "-Wno-redundant-move;-Wno-undefined-var-template;-std=c++11")

# --- 3. Include subproject ---
add_subdirectory(flow-cutter-pace17)

# --- 4. Create gpmc core library (STATIC) ---
add_library(gpmc STATIC
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
)

# --- 5. Set target properties ---
# Set properties (include directories, compile options, link libraries) for specific targets.
# This is safer and clearer than global settings.

# Set include directories required by gpmc library
target_include_directories(gpmc PUBLIC
	${CMAKE_CURRENT_SOURCE_DIR}
	${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src
)

# Set compile definitions required by gpmc library
target_compile_definitions(gpmc PRIVATE
	$<$<CONFIG:Debug>:DEBUG>
	__STDC_FORMAT_MACROS
	__STDC_LIMIT_MACROS
)

# Set compile options required by gpmc library
target_compile_options(gpmc PRIVATE
	$<$<CONFIG:Debug>:-O0>
	${GPMC_COMPILE_FLAGS}
	$<$<CXX_COMPILER_ID:GNU>:${GPMC_GNU_FLAGS}>
	$<$<CXX_COMPILER_ID:Clang>:${GPMC_CLANG_FLAGS}>
	$<$<CXX_COMPILER_ID:AppleClang>:${GPMC_APPLECLANG_FLAGS};${GPMC_CLANG_FLAGS}>
)

# Link gpmc library with required external libraries
# Using `GMP::gmp` style will automatically handle include directories and library paths
target_link_libraries(gpmc PRIVATE
	GMP::gmp
	GMP::gmpxx
	MPFR::mpfr
)

# --- 6. Create the final executable ---
add_executable(gpmc-bin core/Main.cc)
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)

# Link the executable with our gpmc library, subproject library, and external libraries
target_link_libraries(gpmc-bin PRIVATE
	gpmc              # Link our defined gpmc library
	flowcutter        # Link subproject library
	ZLIB::zlib        # Link zlib
)

# Handle static linking option
if(GPMC_STATIC_BUILD)
	set_property(TARGET gpmc-bin APPEND PROPERTY LINK_FLAGS "-static")
endif()
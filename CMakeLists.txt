# ==============================================================================
# Minimum CMake Version
# ==============================================================================
cmake_minimum_required(VERSION 3.15)

# ==============================================================================
# Project Definition
# ==============================================================================
project(gpmc LANGUAGES CXX)

# ==============================================================================
# [WORKAROUND] Manually Set Include and Link Directories
# ==============================================================================
# Due to missing configuration files in Conda packages, we bypass auto-discovery
# and directly specify the paths. $ENV{CONDA_PREFIX} reads the current Conda
# environment path.
message(STATUS "WORKAROUND: Forcing include and link directories to $ENV{CONDA_PREFIX}")
include_directories($ENV{CONDA_PREFIX}/include)
link_directories($ENV{CONDA_PREFIX}/lib)
# ==============================================================================

# ==============================================================================
# Build Options
# ==============================================================================
# Option to build gpmc as a static executable
option(GPMC_STATIC_BUILD "Build gpmc as a static executable" OFF)

# ==============================================================================
# Compiler Flags
# ==============================================================================
set(GPMC_COMPILE_FLAGS "-Wall;-Wno-parentheses;-Wno-format;-Wno-sign-compare;-Wno-unused-variable;-Wno-unused-result")
set(GPMC_GNU_FLAGS "-Wno-literal-suffix;-Wno-class-memaccess")
set(GPMC_CLANG_FLAGS "-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init")
set(GPMC_APPLECLANG_FLAGS "-Wno-redundant-move;-Wno-undefined-var-template;-std=c++11")

# ==============================================================================
# Subdirectories
# ==============================================================================
# Add the flow-cutter-pace17 subproject
add_subdirectory(flow-cutter-pace17)

# ==============================================================================
# Core Library
# ==============================================================================
# Build the main gpmc static library
add_library(gpmc STATIC
	core/ComponentCache.cc core/ComponentManager.cc core/Counter.cc
	core/Config.cc core/Instance.cc ddnnf/DecisionTree.cc
	core/Solver.cc c-mpfr/ComplexMPFR.cc utils/Options.cc
	utils/System.cc preprocessor/Preprocessor.cc preprocessor/TestSolver.cc
	preprocessor/lib_sharpsat_td/subsumer.cpp
	preprocessor/TreeDecomposition.cc preprocessor/IFlowCutter.cc
)

# Set include directories and compile definitions for the gpmc library
target_include_directories(gpmc PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src)
target_compile_definitions(gpmc PRIVATE $<$<CONFIG:Debug>:DEBUG> __STDC_FORMAT_MACROS __STDC_LIMIT_MACROS)
target_compile_options(gpmc PRIVATE $<$<CONFIG:Debug>:-O0> ${GPMC_COMPILE_FLAGS} $<$<CXX_COMPILER_ID:GNU>:${GPMC_GNU_FLAGS}> $<$<CXX_COMPILER_ID:Clang>:${GPMC_CLANG_FLAGS}> $<$<CXX_COMPILER_ID:AppleClang>:${GPMC_APPLECLANG_FLAGS};${GPMC_CLANG_FLAGS}>)

# ==============================================================================
# Executable
# ==============================================================================
# Build the final executable
add_executable(gpmc-bin core/Main.cc)
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)

# Link all required libraries
target_link_libraries(gpmc-bin PRIVATE
	gpmc
	flowcutter
	gmp
	gmpxx
	mpfr
	z
)

# ==============================================================================
# Static Linking Option
# ==============================================================================
if(GPMC_STATIC_BUILD)
	set_property(TARGET gpmc-bin APPEND PROPERTY LINK_FLAGS "-static")
endif()
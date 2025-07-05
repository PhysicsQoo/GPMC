# ==============================================================================
# Minimum required CMake version
# ==============================================================================
cmake_minimum_required(VERSION 3.15)

# ==============================================================================
# Project definition
# ==============================================================================
project(gpmc LANGUAGES CXX)


if(DEFINED ENV{CONDA_PREFIX})
    list(APPEND CMAKE_PREFIX_PATH "$ENV{CONDA_PREFIX}")
endif()


find_package(GMP REQUIRED)
find_package(MPFR REQUIRED)
find_package(ZLIB REQUIRED)


set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_definitions(__STDC_FORMAT_MACROS __STDC_LIMIT_MACROS)

# ==============================================================================
# Option to build gpmc as a static executable
# ==============================================================================
set(GPMC_COMPILE_FLAGS "-Wall;-Wno-parentheses;-Wno-format;-Wno-sign-compare;-Wno-unused-variable;-Wno-unused-result")
set(GPMC_GNU_FLAGS "-Wno-literal-suffix;-Wno-class-memaccess")
set(GPMC_CLANG_FLAGS "-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init")
set(GPMC_APPLECLANG_FLAGS "-Wno-redundant-move;-Wno-undefined-var-template")

# ==============================================================================
# Add subdirectories (dependencies)
# ==============================================================================
add_subdirectory(flow-cutter-pace17)

add_library(gpmc_shared SHARED
    core/ComponentCache.cc core/ComponentManager.cc core/Counter.cc
    core/Config.cc core/Instance.cc ddnnf/DecisionTree.cc
    core/Solver.cc c-mpfr/ComplexMPFR.cc utils/Options.cc
    utils/System.cc preprocessor/Preprocessor.cc preprocessor/TestSolver.cc
    preprocessor/lib_sharpsat_td/subsumer.cpp
    preprocessor/TreeDecomposition.cc preprocessor/IFlowCutter.cc
)

set_target_properties(gpmc_shared PROPERTIES OUTPUT_NAME "gpmc")

target_include_directories(gpmc_shared PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src
)
target_compile_options(gpmc_shared PRIVATE
    $<$<CONFIG:Debug>:-O0>
    ${GPMC_COMPILE_FLAGS}
    $<$<CXX_COMPILER_ID:GNU>:${GPMC_GNU_FLAGS}>
    $<$<CXX_COMPILER_ID:Clang>:${GPMC_CLANG_FLAGS}>
    $<$<CXX_COMPILER_ID:AppleClang>:${GPMC_APPLECLANG_FLAGS};${GPMC_CLANG_FLAGS}>
)

# # ==============================================================================
# Link all required libraries
# ==============================================================================

target_link_libraries(gpmc_shared PRIVATE
	flowcutter
	GMP::gmp       
	GMP::gmpxx     
	MPFR::mpfr    
	ZLIB::zlib     
)
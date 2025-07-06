cmake_minimum_required(VERSION 3.0)
project(gpmc CXX)
option(GPMC_STATIC_BUILD "build gpmc as a static execution file" off)

link_directories(../.venv/lib ../downloads/gmp-6.3.0/lib)
include_directories(${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src ../.venv/include ../downloads/gmp-6.3.0/ ../downloads/gmp-6.3.0/include)
add_compile_options("$<$<CONFIG:Debug>:-O0>")
if (CMAKE_CXX_COMPILER_ID STREQUAL "GNU" OR CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
    # These flags are only for GCC and Clang, not MSVC
    add_compile_options(-Wall -Wno-parentheses -Wno-format -Wno-sign-compare -Wno-unused-variable -Wno-unused-result)
else()
    # For other compilers like MSVC, just add -Wall if you want, or nothing
    # MSVC uses /W3 or /W4 instead of -Wall
    add_compile_options(/W3)
endif()
add_compile_options("$<$<CXX_COMPILER_ID:GNU>:-Wno-literal-suffix;-Wno-class-memaccess>")
add_compile_options("$<$<CXX_COMPILER_ID:Clang>:-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>")
add_compile_options("$<$<CXX_COMPILER_ID:AppleClang>:-Wno-redundant-move;-Wno-undefined-var-template;-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init;-std=c++11>")

add_subdirectory(flow-cutter-pace17)

add_library(gpmc STATIC 
	core/ComponentCache.cc core/ComponentManager.cc core/Counter.cc
	core/Config.cc core/Instance.cc ddnnf/DecisionTree.cc
	core/Solver.cc 
	c-mpfr/ComplexMPFR.cc 
	utils/Options.cc utils/System.cc
	preprocessor/Preprocessor.cc preprocessor/TestSolver.cc 
	preprocessor/lib_sharpsat_td/subsumer.cpp
	preprocessor/TreeDecomposition.cc preprocessor/IFlowCutter.cc
	)
target_compile_definitions(gpmc 
  PRIVATE $<$<CONFIG:Debug>:DEBUG>
           __STDC_FORMAT_MACROS __STDC_LIMIT_MACROS
)

add_executable(gpmc-bin core/Main.cc)
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)
target_link_libraries(gpmc-bin gpmc flowcutter z mpfr gmp gmpxx $<$<BOOL:${GPMC_STATIC_BUILD}>:-static>)

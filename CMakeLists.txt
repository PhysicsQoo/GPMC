cmake_minimum_required(VERSION 3.20)
project(gpmc LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
option(GPMC_STATIC_BUILD "build gpmc as a static execution file" off)

add_compile_options("$<$<CONFIG:Debug>:-O0>")
add_compile_options(
    "$<$<OR:$<CXX_COMPILER_ID:GNU>,$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>>:-Wall;-Wno-parentheses;-Wno-format;-Wno-sign-compare;-Wno-unused-variable;-Wno-unused-result>"
    
    "$<$<CXX_COMPILER_ID:MSVC>:/W3>"
)
add_compile_options("$<$<CXX_COMPILER_ID:GNU>:-Wno-literal-suffix;-Wno-class-memaccess>")
add_compile_options("$<$<CXX_COMPILER_ID:Clang>:-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>")
add_compile_options("$<$<CXX_COMPILER_ID:AppleClang>:-Wno-redundant-move;-Wno-undefined-var-template;-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init >")

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
target_include_directories(gpmc PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src)
target_compile_definitions(gpmc 
  PRIVATE $<$<CONFIG:Debug>:DEBUG>
           __STDC_FORMAT_MACROS __STDC_LIMIT_MACROS
)

add_executable(gpmc-bin core/Main.cc)
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)
target_link_libraries(gpmc-bin gpmc flowcutter z mpfr gmp gmpxx 
    "$<$<AND:$<BOOL:${GPMC_STATIC_BUILD}>,$<OR:$<CXX_COMPILER_ID:GNU>,$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>>>:-static>"
)
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
add_compile_options("$<$<CXX_COMPILER_ID:AppleClang>:-Wno-redundant-move;-Wno-undefined-var-template;-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>")

# Resolve native development packages explicitly, rather than silently searching
# relative directories outside the source tree. CMAKE_PREFIX_PATH is supported.
find_package(ZLIB REQUIRED)
# Keep the original GPMC_STATIC_BUILD contract: use static GMP/GMPXX/MPFR
# archives when requested, without forcing a fully static system executable
# (unsupported by Apple's system toolchain).
if(GPMC_STATIC_BUILD)
  set(GPMC_ORIGINAL_FIND_LIBRARY_SUFFIXES "${CMAKE_FIND_LIBRARY_SUFFIXES}")
  set(CMAKE_FIND_LIBRARY_SUFFIXES ".a" ".lib")
endif()
find_path(GPMC_GMP_INCLUDE_DIR NAMES gmp.h REQUIRED)
find_path(GPMC_GMPXX_INCLUDE_DIR NAMES gmpxx.h REQUIRED)
find_path(GPMC_MPFR_INCLUDE_DIR NAMES mpfr.h REQUIRED)
find_library(GPMC_GMP_LIBRARY NAMES gmp REQUIRED)
find_library(GPMC_GMPXX_LIBRARY NAMES gmpxx REQUIRED)
find_library(GPMC_MPFR_LIBRARY NAMES mpfr REQUIRED)
if(GPMC_STATIC_BUILD)
  set(CMAKE_FIND_LIBRARY_SUFFIXES "${GPMC_ORIGINAL_FIND_LIBRARY_SUFFIXES}")
endif()

add_library(gpmc_native_deps INTERFACE)
target_include_directories(gpmc_native_deps INTERFACE
  "${GPMC_GMP_INCLUDE_DIR}" "${GPMC_GMPXX_INCLUDE_DIR}" "${GPMC_MPFR_INCLUDE_DIR}")
target_link_libraries(gpmc_native_deps INTERFACE
  "${GPMC_MPFR_LIBRARY}" "${GPMC_GMPXX_LIBRARY}" "${GPMC_GMP_LIBRARY}" ZLIB::ZLIB)

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
target_link_libraries(gpmc PRIVATE gpmc_native_deps)
target_compile_definitions(gpmc 
  PRIVATE $<$<CONFIG:Debug>:DEBUG>
           __STDC_FORMAT_MACROS __STDC_LIMIT_MACROS
)

add_executable(gpmc-bin core/Main.cc)
target_include_directories(gpmc-bin PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)
target_link_libraries(gpmc-bin PRIVATE gpmc flowcutter gpmc_native_deps)
# Experimental source-locked C++ benchmarking only. OFF for all normal/release
# builds; GPMC's solver engine, CLI, default MPFR precision and search are
# unchanged. The CodSpeed fork of Google Benchmark exposes simulation hooks.
option(GPMC_BUILD_QU_PRS_BENCHMARKS "Build opt-in QuPRS weighted-CNF CodSpeed C++ benchmarks" OFF)
if(GPMC_BUILD_QU_PRS_BENCHMARKS)
  include(FetchContent)
  set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
  set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
  FetchContent_Declare(
    google_benchmark
    GIT_REPOSITORY https://github.com/CodSpeedHQ/codspeed-cpp.git
    GIT_TAG 76985b6f02c49fe70393c50fcca6e9748f300caa
    SOURCE_SUBDIR google_benchmark
  )
  FetchContent_MakeAvailable(google_benchmark)
  add_executable(gpmc_quprs_cnf_bench benchmarks/quprs/gpmc_quprs_bench.cc)
  set_target_properties(gpmc_quprs_cnf_bench PROPERTIES\n    CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)\n  target_include_directories(gpmc_quprs_cnf_bench PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_link_libraries(gpmc_quprs_cnf_bench PRIVATE
    gpmc flowcutter gpmc_native_deps benchmark::benchmark)
endif()

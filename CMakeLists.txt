cmake_minimum_required(VERSION 3.8)
project(gpmc CXX)
option(GPMC_STATIC_BUILD "Build gpmc as a static executable" OFF)

if(MSVC)
    add_compile_options(/EHsc /W4)
    # C4267: 'size_t' to 'int', possible loss of data
    # C4244: conversion from '...' to '...', possible loss of data
    # C4146: unary minus operator applied to unsigned type
    # C4305: truncation from 'double' to 'float'
    # C4200: zero-sized array in struct/union (nonstandard extension)
    # C4834: discarding return value of function with [[nodiscard]]
    # C4127: conditional expression is constant
    add_compile_options(/wd4267 /wd4244 /wd4146 /wd4305 /wd4200 /wd4834 /wd4127)
    
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()

    add_compile_options(
        -Wall 
        -Wno-parentheses 
        -Wno-format 
        -Wno-sign-compare 
        -Wno-unused-variable 
        -Wno-unused-result
        "$<$<CXX_COMPILER_ID:GNU>:-Wno-literal-suffix;-Wno-class-memaccess>"
        "$<$<CXX_COMPILER_ID:Clang>:-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>"
        "$<$<CXX_COMPILER_ID:AppleClang>:-Wno-redundant-move;-Wno-undefined-var-template;-Wno-reserved-user-defined-literal;-Wno-gnu-array-member-paren-init>"
    )
endif()

find_package(ZLIB REQUIRED)


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

target_include_directories(gpmc PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/flow-cutter-pace17/src
    ../.venv/include
    ../downloads/gmp-6.3.0
    ../downloads/gmp-6.3.0/include
    ${ZLIB_INCLUDE_DIRS}
)

target_compile_definitions(gpmc PRIVATE
    $<$<CONFIG:Debug>:DEBUG>
    __STDC_FORMAT_MACROS
    __STDC_LIMIT_MACROS
)

target_link_libraries(gpmc PUBLIC ZLIB::zlib gmp gmpxx mpfr)

add_executable(gpmc-bin core/Main.cc)
set_target_properties(gpmc-bin PROPERTIES OUTPUT_NAME gpmc)

target_link_libraries(gpmc-bin gpmc flowcutter)

if(GPMC_STATIC_BUILD)
    target_link_options(gpmc-bin PRIVATE -static)
endif()
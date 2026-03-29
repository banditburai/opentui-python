cmake_minimum_required(VERSION 3.15)
project(opentui_bindings)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_OSX_DEPLOYMENT_TARGET "13.0")

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind REQUIRED)

set(OPENTUI_LIB_PATHS
    ${CMAKE_CURRENT_SOURCE_DIR}/../opentui/opentui-libs
    ${CMAKE_SOURCE_DIR}/../opentui/opentui-libs
    /usr/local/lib
    /opt/homebrew/lib
)

find_library(OPENTUI_LIB
    NAMES opentui
    PATHS ${OPENTUI_LIB_PATHS}
    NO_DEFAULT_PATH
)

set(YOGA_SOURCE_DIR "" CACHE PATH "Path to yoga source root (contains yoga/CMakeLists.txt)")
if(NOT YOGA_SOURCE_DIR OR NOT EXISTS "${YOGA_SOURCE_DIR}/yoga/CMakeLists.txt")
    # Try sibling directory (development layout: opentui-python and yoga-python side by side)
    foreach(_try_path
        "${CMAKE_SOURCE_DIR}/../yoga-python/reference/yoga"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../../yoga-python/reference/yoga")
        if(EXISTS "${_try_path}/yoga/CMakeLists.txt")
            get_filename_component(YOGA_SOURCE_DIR "${_try_path}" ABSOLUTE)
            break()
        endif()
    endforeach()
endif()

nanobind_add_module(
    opentui_bindings
    bindings.cpp
    renderer.cpp
    buffer.cpp
    text_buffer.cpp
    edit_buffer.cpp
    editor_view.cpp
    hit_grid.cpp
    graphics.cpp
    types.cpp
    native_signals.cpp
    yoga_configure.cpp
    common_render.cpp
    reconciler_patch.cpp
)

# Windows: find_library won't locate a .dll without a .lib import library.
# Find the DLL, then generate a .lib using dumpbin/lib (MSVC toolchain).
if(NOT OPENTUI_LIB AND WIN32)
    foreach(_dir ${OPENTUI_LIB_PATHS})
        foreach(_name opentui.dll libopentui.dll)
            if(EXISTS "${_dir}/${_name}")
                set(OPENTUI_DLL "${_dir}/${_name}")
                break()
            endif()
        endforeach()
        if(OPENTUI_DLL)
            break()
        endif()
    endforeach()
    if(OPENTUI_DLL)
        set(_genlib "${CMAKE_BINARY_DIR}/opentui.lib")
        set(_deffile "${CMAKE_BINARY_DIR}/opentui.def")
        # Generate .def from DLL exports, then create .lib import library
        execute_process(
            COMMAND dumpbin /EXPORTS "${OPENTUI_DLL}"
            OUTPUT_VARIABLE _exports
            RESULT_VARIABLE _dump_rc
        )
        if(_dump_rc EQUAL 0)
            # Parse dumpbin output: extract function names from the exports table
            string(REPLACE "\n" ";" _lines "${_exports}")
            set(_def_content "EXPORTS\n")
            set(_in_exports FALSE)
            foreach(_line ${_lines})
                if(_line MATCHES "ordinal.*name")
                    set(_in_exports TRUE)
                elseif(_in_exports AND _line MATCHES "^[ \t]+[0-9]+[ \t]+[0-9A-Fa-f]+[ \t]+[0-9A-Fa-f]+[ \t]+(.+)$")
                    string(STRIP "${CMAKE_MATCH_1}" _sym)
                    string(APPEND _def_content "    ${_sym}\n")
                elseif(_in_exports AND _line MATCHES "^[ \t]*$")
                    set(_in_exports FALSE)
                endif()
            endforeach()
            file(WRITE "${_deffile}" "${_def_content}")
            execute_process(
                COMMAND lib "/DEF:${_deffile}" "/OUT:${_genlib}" /MACHINE:X64
                RESULT_VARIABLE _lib_rc
            )
            if(_lib_rc EQUAL 0 AND EXISTS "${_genlib}")
                set(OPENTUI_LIB "${_genlib}")
                message(STATUS "Generated import library: ${_genlib}")
            endif()
        endif()
        # Fallback: if .lib generation failed, try linking the DLL directly
        if(NOT OPENTUI_LIB)
            set(OPENTUI_LIB "${OPENTUI_DLL}")
            message(WARNING "Could not generate .lib - trying direct DLL link")
        endif()
    endif()
endif()

if(OPENTUI_LIB)
    target_link_libraries(opentui_bindings PRIVATE ${OPENTUI_LIB})
    message(STATUS "Found OpenTUI library: ${OPENTUI_LIB}")
else()
    message(FATAL_ERROR "OpenTUI library not found in: ${OPENTUI_LIB_PATHS}\n"
        "Run 'python scripts/download_opentui.py' first.")
endif()

if(YOGA_SOURCE_DIR AND EXISTS "${YOGA_SOURCE_DIR}/yoga/CMakeLists.txt")
    message(STATUS "Found yoga source: ${YOGA_SOURCE_DIR}")
    add_subdirectory(${YOGA_SOURCE_DIR}/yoga ${CMAKE_BINARY_DIR}/yogacore-build EXCLUDE_FROM_ALL)
    target_link_libraries(opentui_bindings PRIVATE yogacore)
    target_compile_definitions(opentui_bindings PRIVATE HAS_YOGACORE=1)
else()
    message(STATUS "Yoga source not found - configure_node_direct disabled (Python fallback)")
endif()

target_include_directories(opentui_bindings PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# macOS: use classic linker to avoid fixup errors on arm64, and set rpath
# so delocate can find libopentui.dylib relative to the extension module.
if(APPLE)
    target_link_options(opentui_bindings PRIVATE "LINKER:-ld_classic")
    set_target_properties(opentui_bindings PROPERTIES
        INSTALL_RPATH "@loader_path/opentui-libs"
    )
endif()

install(TARGETS opentui_bindings DESTINATION "opentui")

# Bundle the native library so auditwheel/delocate can find and repair it.
# On Windows, the DLL is bundled in opentui-libs/ within the wheel.
if(OPENTUI_LIB)
    install(FILES ${OPENTUI_LIB} DESTINATION "opentui/opentui-libs")
endif()

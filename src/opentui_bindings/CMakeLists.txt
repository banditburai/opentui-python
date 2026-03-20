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

# macOS: use classic linker to avoid fixup errors on arm64
if(APPLE)
    target_link_options(opentui_bindings PRIVATE "LINKER:-ld_classic")
endif()

install(TARGETS opentui_bindings DESTINATION "opentui")

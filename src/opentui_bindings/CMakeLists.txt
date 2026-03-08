cmake_minimum_required(VERSION 3.15)
project(opentui_bindings)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_OSX_DEPLOYMENT_TARGET "13.0")

# scikit-build-core provides nanobind and Python
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(nanobind REQUIRED)

# Find OpenTUI library (optional - may not exist during initial build)
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

# Add the nanobind Python module
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
)

# Link with opentui library if found
if(OPENTUI_LIB)
    target_link_libraries(opentui_bindings PRIVATE ${OPENTUI_LIB})
    message(STATUS "Found OpenTUI library: ${OPENTUI_LIB}")
else()
    message(FATAL_ERROR "OpenTUI library not found in: ${OPENTUI_LIB_PATHS}\n"
        "Run 'python scripts/download_opentui.py' first.")
endif()

# Include directories
target_include_directories(opentui_bindings PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# macOS: use classic linker to avoid fixup errors on arm64
if(APPLE)
    target_link_options(opentui_bindings PRIVATE "LINKER:-ld_classic")
endif()

# Install into opentui package directory
install(TARGETS opentui_bindings DESTINATION "opentui")

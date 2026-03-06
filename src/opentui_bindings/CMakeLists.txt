cmake_minimum_required(VERSION 3.15)
project(opentui_bindings)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_OSX_DEPLOYMENT_TARGET "13.0")

# Fetch nanobind
include(FetchContent)
FetchContent_Declare(
    nanobind
    GIT_REPOSITORY https://github.com/wjakob/nanobind.git
    GIT_TAG v2.9.2
)
FetchContent_MakeAvailable(nanobind)

# Find Python - must find before nanobind to set correct suffix
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development)
set(Python_EXECUTABLE ${Python_INTERPRETER})

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
    message(WARNING "OpenTUI library not found - some functions may not work")
endif()

# Include directories
target_include_directories(opentui_bindings PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# Add linker flags to fix arm64 issues on macOS
set_target_properties(opentui_bindings PROPERTIES
    LINK_FLAGS "-Wl,-ld_classic"
)

# Set output directory
set_target_properties(opentui_bindings PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
)

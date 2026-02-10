cmake_minimum_required(VERSION 3.8)

project(imgui_glfw_nfd_lib
    VERSION 0.1 LANGUAGES CXX C)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

# ---------------------------------------------------------------------------
# Source files
# ---------------------------------------------------------------------------
set(IMGUI_SOURCES
    imgui.cpp
    imgui_demo.cpp
    imgui_draw.cpp
    imgui_impl_glfw.cpp
    imgui_impl_opengl3.cpp
    imgui_tables.cpp
    imgui_widgets.cpp
    ImGuiFileDialog.cpp
    extLibs/gl3w/GL/gl3w.c
)

add_library(imgui_glfw_ndf STATIC ${IMGUI_SOURCES})

# ---------------------------------------------------------------------------
# OpenGL
# ---------------------------------------------------------------------------
find_package(OpenGL REQUIRED)

# ---------------------------------------------------------------------------
# GLFW -- on Linux use system-installed glfw3, on Windows use bundled finder
# ---------------------------------------------------------------------------
if(WIN32)
    set(GLFW3_USE_STATIC_LIBS ON)
    find_package(GLFW3 REQUIRED)
    unset(GLFW3_USE_STATIC_LIBS)
    target_link_libraries(imgui_glfw_ndf PUBLIC ${GLFW_LIBRARIES} OpenGL::GL GLFW3::GLFW)
else()
    find_package(glfw3 REQUIRED)
    target_link_libraries(imgui_glfw_ndf PUBLIC OpenGL::GL glfw dl)
endif()

# ---------------------------------------------------------------------------
# Include directories
# ---------------------------------------------------------------------------
target_include_directories(imgui_glfw_ndf PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/extLibs/gl3w>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/>
    $<INSTALL_INTERFACE:include>
)

# ---------------------------------------------------------------------------
# Compile definitions
# ---------------------------------------------------------------------------
target_compile_definitions(imgui_glfw_ndf PUBLIC IMGUI_IMPL_OPENGL_LOADER_GL3W)

if(WIN32)
    target_compile_definitions(imgui_glfw_ndf PUBLIC NOMINMAX _ENABLE_EXTENDED_ALIGNED_STORAGE)
endif()

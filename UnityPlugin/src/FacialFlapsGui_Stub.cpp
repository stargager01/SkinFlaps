/**
 * FacialFlapsGui_Stub.cpp
 * Stub definitions for FacialFlapsGui static members when building Unity plugin
 *
 * The Unity plugin doesn't use the GUI, but some source files reference
 * FacialFlapsGui static members. This provides minimal definitions to link.
 */

#ifdef SKINFLAPS_UNITY_PLUGIN

#include <string>

// Forward declare GLFWwindow to avoid including GLFW headers
struct GLFWwindow;

// Stub definitions for FacialFlapsGui static members
// These are normally defined in FacialFlapsGui.cpp

namespace {
    // We need to match the class name exactly
}

// Define the static members that are referenced by other source files
// These are declared in FacialFlapsGui.h

class FacialFlapsGui;

// Static member definitions
GLFWwindow* FacialFlapsGui::FFwindow = nullptr;
bool FacialFlapsGui::user_message_flag = false;
bool FacialFlapsGui::physicsDrag = false;
bool FacialFlapsGui::getTextInput = false;
int FacialFlapsGui::csgToolstate = 0;
std::string FacialFlapsGui::historyDirectory;
std::string FacialFlapsGui::modelDirectory;
std::string FacialFlapsGui::objDirectory;
std::string FacialFlapsGui::modelFile;
std::string FacialFlapsGui::historyFile;
std::string FacialFlapsGui::user_message;
std::string FacialFlapsGui::user_message_title;
bool FacialFlapsGui::surgicalDrag = false;
bool FacialFlapsGui::ctrlShiftKeyDown = false;

// Additional static members that might be needed
int FacialFlapsGui::buttonsDown = 0;
float FacialFlapsGui::lastSurgX = 0.0f;
float FacialFlapsGui::lastSurgY = 0.0f;
int FacialFlapsGui::FileDlgMode = 0;

#endif // SKINFLAPS_UNITY_PLUGIN

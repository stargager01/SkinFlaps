/**
 * FacialFlapsGui_Unity.cpp
 * Stub implementation of FacialFlapsGui static members for Unity plugin
 *
 * This file provides the required static member definitions without the
 * full GUI implementation, since Unity handles its own windowing and rendering.
 */

#ifdef SKINFLAPS_UNITY_PLUGIN

#include <string>

// Forward declarations to avoid including the full headers
struct GLFWwindow;
struct ImVec2 { float x, y; ImVec2() : x(0), y(0) {} ImVec2(float _x, float _y) : x(_x), y(_y) {} };
typedef unsigned int GLuint;

// Include the actual classes we need
#include "surgicalActions.h"
#include "gl3wGraphics.h"

// Minimal FacialFlapsGui class definition matching the header
class FacialFlapsGui {
public:
    static GLFWwindow* FFwindow;
    static int nextCounter;
    static bool user_message_flag, physicsDrag, getTextInput;

    static void sendUserMessage(const char* message, const char* windowTitle) {
        user_message = message;
        user_message_title = windowTitle;
        user_message_flag = true;
    }

    static void handleThrow(const char* message) {
        user_message = message;
        user_message_title = "Program exception thrown";
        user_message_flag = true;
    }

    static void showHourglass() {
        physicsDrag = true;
    }

    static inline surgicalActions* getSurgicalActions() { return &igSurgAct; }
    static inline gl3wGraphics* getgl3wGraphics() { return &igGl3w; }

    static void setModelFile(const std::string& modelFileName) {
        modelFile = modelFileName;
    }

private:
    static bool powerHooks, showToolbox, viewPhysics, viewSurface, wheelZoom, except_thrown_flag;
    static int csgToolstate;
    static std::string historyDirectory, modelDirectory, objDirectory, modelFile, historyFile, user_message, user_message_title;
    static unsigned char buttonsDown;
    static bool surgicalDrag, ctrlShiftKeyDown;
    static int windowWidth, windowHeight;
    static ImVec2 minFileDlgSize;
    static int FileDlgMode;
    static GLuint hourglassTexture;
    static int hourglassWidth, hourglassHeight;
    static float lastSurgX, lastSurgY;
    static surgicalActions igSurgAct;
    static gl3wGraphics igGl3w;
};

// Static member definitions
GLFWwindow* FacialFlapsGui::FFwindow = nullptr;
int FacialFlapsGui::nextCounter = 0;
bool FacialFlapsGui::user_message_flag = false;
bool FacialFlapsGui::physicsDrag = false;
bool FacialFlapsGui::getTextInput = false;

bool FacialFlapsGui::powerHooks = false;
bool FacialFlapsGui::showToolbox = true;
bool FacialFlapsGui::viewPhysics = false;
bool FacialFlapsGui::viewSurface = true;
bool FacialFlapsGui::wheelZoom = true;
bool FacialFlapsGui::except_thrown_flag = false;

int FacialFlapsGui::csgToolstate = 0;

std::string FacialFlapsGui::historyDirectory;
std::string FacialFlapsGui::modelDirectory;
std::string FacialFlapsGui::objDirectory;
std::string FacialFlapsGui::modelFile;
std::string FacialFlapsGui::historyFile;
std::string FacialFlapsGui::user_message;
std::string FacialFlapsGui::user_message_title;

unsigned char FacialFlapsGui::buttonsDown = 0;
bool FacialFlapsGui::surgicalDrag = false;
bool FacialFlapsGui::ctrlShiftKeyDown = false;

int FacialFlapsGui::windowWidth = 1280;
int FacialFlapsGui::windowHeight = 720;
ImVec2 FacialFlapsGui::minFileDlgSize(640, 360);
int FacialFlapsGui::FileDlgMode = 0;

GLuint FacialFlapsGui::hourglassTexture = 0xffffffff;
int FacialFlapsGui::hourglassWidth = 0;
int FacialFlapsGui::hourglassHeight = 0;

float FacialFlapsGui::lastSurgX = 0.0f;
float FacialFlapsGui::lastSurgY = 0.0f;

surgicalActions FacialFlapsGui::igSurgAct;
gl3wGraphics FacialFlapsGui::igGl3w;

#endif // SKINFLAPS_UNITY_PLUGIN

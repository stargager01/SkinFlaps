// Author: Court Cutting
// Date: November 4, 2020
// Purpose: New gui for cleftSim app using GLFW3, dear imgui and nativeFileDialog
// Copyright 2020 - All rights reserved at this time.

#ifndef _SURGICAL_SIM_GUI_
#define _SURGICAL_SIM_GUI_

#define SKINFLAPS_VERSION_MAJOR 3
#define SKINFLAPS_VERSION_MINOR 1
#define SKINFLAPS_VERSION_PATCH 0
#define SKINFLAPS_VERSION_STRING "3.1.0"

#ifdef WIN32
#include <direct.h>
#define GetCurrentDir _getcwd
#define PATH_SEP "\\"
#define PATH_SEP_CHAR '\\'
#else
#include <unistd.h>
#define GetCurrentDir getcwd
#define PATH_SEP "/"
#define PATH_SEP_CHAR '/'
#endif

//#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include "ImGuiFileDialog.h"
#include "ImGuiFileDialogConfig.h"
#include <string>
#include <fstream>
#include <tbb/task_arena.h>
#include <gl3wGraphics.h>
#include "surgicalActions.h"

class SurgicalSimGui {
public:
	static void mouse_button_callback(GLFWwindow* window, int button, int action, int mods);

	static void cursor_position_callback(GLFWwindow* window, double xpos, double ypos);

	static void key_callback(GLFWwindow* window, int key, int scancode, int action, int mods);

	//		The callback function receives two - dimensional scroll offsets.
	static void mouse_wheel_callback(GLFWwindow* window, double xoffset, double yoffset)
	{ // The callback function receives two - dimensional scroll offsets.
		if (wheelZoom)
			igGl3w.mouseWheelEvent((float)yoffset);
	}

	static void window_size_callback(GLFWwindow* window, int width, int height)
	{
		windowWidth = width;
		windowHeight = height;
		glfwSetWindowSize(window, width, height);
		igGl3w.setViewport(0, 0, width, height);
	}

	static void glfw_error_callback(int error, const char* description)
	{
		fprintf(stderr, "Glfw Error %d: %s\n", error, description);
	}

	static void destroyImguiGlfw();

	static bool initSimulator();

	static bool initImguiGlfw();

	static inline surgicalActions* getSurgicalActions() { return &igSurgAct; }
	static inline gl3wGraphics* getgl3wGraphics() { return &igGl3w; }

	static inline bool CtrlOrShiftKeyIsDown() { return ctrlShiftKeyDown;  }

	static void setToolState(int toolState) { csgToolstate = toolState; }

	static void getFileName(const char *startPath, const char *fileFilterSuffix, std::string &startDirectory, bool mustExist, bool chooseDirectory=false);

	static void sendUserMessage(const char *message, const char *windowTitle) {
		user_message = message;
		user_message_title = windowTitle;
		user_message_flag = true;
	}

	static void handleThrow(const char* message);

	static void showHourglass();

	static void setModelFile(const std::string &modelFileName ) {
		modelFile = modelFileName;
	}

	static std::wstring RegGetString(HKEY hKey, const std::wstring& subKey, const std::wstring& value);

	static void setDefaultDirectories();

	static void InstanceCleftGui();

	SurgicalSimGui(){
		igSurgAct.setSurgicalSimGui(this);
		user_message_flag = false;
		getTextInput = false;
	}

	~SurgicalSimGui(){}

	static GLFWwindow* FFwindow;
	static int nextCounter;
	static bool user_message_flag, physicsDrag, getTextInput;

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

};  // class SurgicalSimGui

#endif  // #ifndef _SURGICAL_SIM_GUI_

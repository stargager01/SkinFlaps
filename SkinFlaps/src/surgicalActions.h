#ifndef __SURGICALACTIONS_H__
#define __SURGICALACTIONS_H__

#include <string>
#include <vector>
#include <list>
#include <mutex>
#include "hooks.h"
#include "sutures.h"
#include "surgGraphics.h"
#include "fence.h"

#include "deepCut.h"
#include "skinCutUndermineTets.h"  // replace with above later

#include "json.h"
#include <Vec3f.h>
#include "bccTetScene.h"

// forward declarations
class SurgicalSimGui;
class gl3wGraphics;

/// Shoulder surgery tool state extensions (beyond existing 0-7 facial tools).
static const int TOOL_SUTURE_ANCHOR = 8;   ///< Place suture anchor into bone
static const int TOOL_ARTHROSCOPE = 9;     ///< Arthroscopic camera view
static const int TOOL_GRASPER = 10;        ///< Two-point tissue grasper

/** @brief Central controller for all surgical tool interactions in the simulator.
 *
 * Handles mouse and keyboard input for surgical tools (hooks, sutures, incisions,
 * undermining), manages scene loading, and coordinates between the GUI, graphics,
 * physics engine, and surgical history recording/playback.
 */
class surgicalActions
{
public:
	/// @brief Display a message dialog to the user, optionally closing the program.
	void sendUserMessage(const char *message, const char *title, bool closeProgram = false);
	/// @brief Handle right mouse button press for tool interaction on a surface object.
	bool rightMouseDown(std::string objectHit, float(&position)[3], int triangle);
	/// @brief Handle right mouse button release; completes the current tool action.
	bool rightMouseUp(std::string objectHit, float(&position)[3], int triangle);
	/// @brief Handle mouse drag motion for hook dragging and tool movement.
	bool mouseMotion(float dScreenX, float dScreenY);
	/// @brief Handle keyboard key press events for tool shortcuts and navigation.
	void onKeyDown(int key);
	/// @brief Handle keyboard key release events.
	void onKeyUp(int key);
	/// @brief Set the active surgical tool (0=none/physics running, >0=specific tool).
	inline void setToolState(int toolState){
		// Restore normal FOV when leaving arthroscope mode
		if (_toolState == TOOL_ARTHROSCOPE && toolState != TOOL_ARTHROSCOPE && _gl3w) {
			float zCenter, height, verticalAngle, screenAspect;
			_gl3w->getGLmatrices()->getCameraData(zCenter, height, verticalAngle, screenAspect);
			_gl3w->getGLmatrices()->setView(0.7f, screenAspect);
			_arthroscopePortalIdx = -1;
		}
		_bts.setPhysicsPause(toolState < 1 ? false : true); _toolState = toolState;
	}
	/// @brief Return the currently active tool state identifier.
	inline int getToolState() { return _toolState; }
	/// @brief Assign the OpenGL graphics context to this controller and the scene.
	inline void setGl3wGraphics(gl3wGraphics *gl3w) { _gl3w = gl3w; _bts.setGl3wGraphics(gl3w); }
	/// @brief Assign the GUI interface for user dialogs and status updates.
	void setSurgicalSimGui(SurgicalSimGui *ffg) { _ffg = ffg; }
	/// @brief Return a pointer to the hooks manager.
	inline hooks* getHooks() { return &_hooks; }
	/// @brief Return a pointer to the sutures manager.
	inline sutures* getSutures() { return &_sutures; }
	/// @brief Load a surgical scene (.smd) from the given directory and filename.
	bool loadScene(const char *modelDirectory, const char *sceneFilename);
	/// @brief Return a pointer to the BCC tet scene manager.
	inline bccTetScene* getBccTetScene() { return &_bts; }
	/// @brief Return a pointer to the surgical graphics (triangulated surface) manager.
	inline surgGraphics* getSurgGraphics() { return &_sg; }

	//	inline deepCut* getDeepCutPtr() { return &_incisions; }
	/// @brief Return a pointer to the deep incision/undermine tool.
	inline skinCutUndermineTets* getDeepCutPtr() { return &_incisions; }  // COURT fix when deepCut added back

	/// @brief Load a surgical history file for action replay.
	bool loadHistory(const char *historyDir, const char *historyFile);
	/// @brief Execute the next recorded action from the loaded surgical history.
	void nextHistoryAction();
	/// @brief Return true if there are no history actions loaded.
	bool historyEmpty()	{return _historyArray.size()<1;}
	/** @brief Convert a current-environment attach point to history-file coordinates.
	 *  @param[in]  triangle  Triangle index in the current mesh.
	 *  @param[in]  uv        Parametric coordinates on the triangle.
	 *  @param[out] material  Material ID for history storage.
	 *  @param[out] historyTexture  Texture coordinates for history storage.
	 *  @param[out] historyVec  Displacement vector for history storage.
	 */
	bool setHistoryAttachPoint(const int triangle, const float(&uv)[2], int &material, float(&historyTexture)[2], Vec3f &historyVec);
	/** @brief Convert a history-file attach point back to current-environment coordinates.
	 *  @param[in]  material  Material ID from the history file.
	 *  @param[in]  historyTexture  Texture coordinates from the history file.
	 *  @param[in]  displacement  Displacement vector from the history file.
	 *  @param[out] triangle  Closest triangle in the current mesh.
	 *  @param[out] uv  Parametric coordinates on the found triangle.
	 *  @param[in]  findEdge  If true, search for an edge rather than a face point.
	 */
	bool getHistoryAttachPoint(const int material, const float(&historyTexture)[2], const Vec3f &displacement, int &triangle, float(&uv)[2], bool findEdge);
	/// @brief Save the current surgical history to a JSON file.
	bool saveSurgicalHistory(const char *fullFilePath);
	/// @brief Return the model/scene data directory path.
	const char* getModelDirectory() { return _sceneDir.c_str(); }
	/// @brief Return the history file directory path.
	const char* getHistoryDirectory() { return _historyDir.c_str(); }
	/// @brief Set the model/scene data directory path.
	void setModelDirectory(const char* sceneDir) { _sceneDir.assign(sceneDir); }
	/// @brief Set the history file directory path.
	void setHistoryDirectory(const char* histDir) { _historyDir.assign(histDir); }
	/// @brief Export the current mesh state as an OBJ file.
	bool saveCurrentObj(const char* fullFilePath, const char* fileNamePrefix);
	/// @brief Promote all temporary (fake) sutures to permanent physics constraints.
	void promoteFakeSutures();
	/// @brief Pause the physics simulation (e.g. during topology changes).
	void pausePhysics();
	bool _strongHooks;  // COURT - hack for collision cheating purposes
	std::atomic<bool> physicsDone, newTopology, taskThreadError;
	std::mutex _errorMutex;
	std::string taskThreadErrorStr;
	bccTetScene _bts;

	surgicalActions();
	~surgicalActions();

private:
    struct float3{	float v[3]; };
	int _toolState;
	bool _sutureAnchorMode = false;  ///< True when placing suture anchors
	int _arthroscopePortalIdx = -1;  ///< Index of active arthroscope portal
	gl3wGraphics *_gl3w;
	SurgicalSimGui *_ffg;
	std::vector<int> _pXToPbTetVertices;
	int _originalTriangleNumber;
	int _dragVertex;
	float _dragXyz[3];
	std::string _selectedSurgObject,_dragTissue;
	surgGraphics _sg;	// dynamic triangulated skin object
	hooks _hooks;
	sutures _sutures;
	deepCut _incisions;  // derived from skinCutUndermineTets class
//	skinCutUndermineTets _incisions;  // now derived from deepCut class

	struct undermineTriangle {
		unsigned int incisionConnect : 1;
		unsigned int triangle : 31;
	};
	std::vector<undermineTriangle> _undermineTriangles;  // user entered undermine texture points
	struct perioTri {
		unsigned int incisionConnect : 1;
		unsigned int periostealTriangle : 31;
	};
	std::list<perioTri> _periostealUndermineTriangles;
	fence _fence;
	json::Array _historyArray;
	json::Array::ValueVector::iterator _historyIt;	// current history command
	std::string _sceneDir, _historyDir;
	void historyAttachFailure(std::string& errorDescription);  // report failure and truncate history at just before this action.

	// next are temporary move variables set by ascii keys
	float _x,_y,_z,_u,_f,_r;
};

#endif // __SURGICALACTIONS_H__

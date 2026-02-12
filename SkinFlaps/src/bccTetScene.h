//////////////////////////////////////////////////////////////////
// File: bccTetScene.h
// Author: Court Cutting
// Date: 3/4/2019
// Purpose: Bcc tet based projective dynamics physics library interface to surgical simulator code.
//    This version uses the ShapeOp subroutine library of Sofien Bouaziz ( http://ShapeOp.org )
//    to do the physics.  So far have experimented with mass-springs, physX(NVIDIA),
//    physBAM(Fedkiw, Teran, Sifakis, et al.), corotated linear elasticity(Teran, Sifakis, Mitchell) and
//    the shape matching code of Rivers and James.
//    Copyright 2019 - All rights reserved at the present time.
///////////////////////////////////////////////////////////////////

#ifndef __BCC_TET_SCENE__
#define __BCC_TET_SCENE__

#include <string>
#include <vector>
#include <unordered_map>
#include "surgGraphics.h"
#include "vnBccTetrahedra.h"
#include "vnBccTetCutter_tbb.h"
#include "tetCollisions.h"
#include "tetSubset.h"
#include "remapTetPhysics.h"
#include "pdTetPhysics.h"

// forward declarations
class gl3wGraphics;
class surgicalActions;

/** @brief Region-specific physical properties for facial skin flap simulation.
 *
 * Different facial regions have clinically distinct stretch characteristics.
 * These properties allow the simulator to assign region-appropriate strain limits
 * and stiffness values, improving surgical accuracy.
 *
 * Each region can optionally reference a closed manifold OBJ file (subsetObjFile)
 * that encloses the tet cluster belonging to that region for spatial mapping.
 */
struct tissueRegionProperties {
	std::string name;           ///< Region identifier, e.g. "cheek", "forehead", "eyelid", "scalp", "nose"
	float stretchMin;           ///< Minimum strain limit (compression). Lower = more compression allowed.
	float stretchMax;           ///< Maximum strain limit (extension). Higher = more stretch allowed.
	float lowTetWeight;         ///< Region-specific low tet stiffness weight. 0 means use global default.
	float highTetWeight;        ///< Region-specific high tet stiffness weight. 0 means use global default.
	std::string subsetObjFile;  ///< Optional path to closed manifold OBJ defining the spatial extent of this region.

	tissueRegionProperties()
		: name(""), stretchMin(0.0f), stretchMax(0.0f),
		  lowTetWeight(0.0f), highTetWeight(0.0f), subsetObjFile("") {}

	tissueRegionProperties(const std::string& regionName, float sMin, float sMax,
	                       float lowW = 0.0f, float highW = 0.0f, const std::string& objFile = "")
		: name(regionName), stretchMin(sMin), stretchMax(sMax),
		  lowTetWeight(lowW), highTetWeight(highW), subsetObjFile(objFile) {}
};

#include "materialLayerConfig.h"

/// @brief Identifies the anatomy type of the loaded scene.
/// Used to select appropriate shaders, default material layers, and region properties.
enum class AnatomyType { FACIAL, SHOULDER, GENERIC };

/** @brief BCC tetrahedral scene manager for projective dynamics-based surgical simulation.
 *
 * Provides the main interface between the surgical simulator and the physics engine.
 * Manages the virtual-noded BCC tetrahedral lattice, physics updates, surface drawing,
 * and region-specific stretch properties for facial skin flaps.
 */
class bccTetScene
{
public:
	/// @brief Load a scene from an .smd file in the given data directory.
	bool loadScene(const char *dataDirectory, const char *sceneFileName);
	/// @brief Create a new multi-resolution BCC tet lattice for physics simulation.
	void createNewPhysicsLattice(int maxDimMegatetSubdivs, int nTetSizeLevels);
	/// @brief Rebuild the existing physics lattice after a topology change (e.g. incision).
	void updateOldPhysicsLattice();
	/// @brief Re-initialize physics without changing tet topology.
	inline void nonTetPhysicsUpdate() {_ptp.initializePhysics();}
	/// @brief Initialize the projective dynamics physics solver.
	void initPdPhysics();
	/// @brief Run one step of the physics simulation and process collisions.
	void updatePhysics();
	/// @brief Fix periosteal peripheral vertices as Dirichlet boundary conditions.
	void fixPeriostealPeriferalVertices();
	/// @brief Update surface triangle positions from the physics nodal positions.
	void updateSurfaceDraw();
	/// @brief Return a pointer to the internal projective dynamics physics solver.
	pdTetPhysics* getPdTetPhysics_2(){ return &_ptp; }
	/// @brief Signal that external forces have been applied this frame.
	inline void setForcesAppliedFlag(){ _forcesApplied = true; }
	/// @brief Promote all temporary sutures to permanent and re-initialize physics.
	inline void promoteSutures() { _ptp.promoteAllSutures(); _ptp.initializePhysics(); }
	/// @brief Return a pointer to the virtual-noded BCC tetrahedra structure.
	vnBccTetrahedra* getVirtualNodedBccTetrahedra() { return &_vnTets; }
	/// @brief Set visibility of surface and physics debug drawing (0=off, 1=on, 2=unchanged).
	void setVisability(char surface, char physics);	// 0=off, 1=on, 2=don't change
	/// @brief Assign the OpenGL graphics context for rendering.
	void setGl3wGraphics(gl3wGraphics *gl3w) { _gl3w = gl3w; }
	/// @brief Create a debug visualization of the tet lattice wireframe.
	void createTetLatticeDrawing();
	/// @brief Render the tet lattice debug visualization.
	void drawTetLattice();
	/// @brief Remove the tet lattice debug visualization.
	void eraseTetLattice();
	/// @brief Set the surgical actions controller that manages user interaction.
	void setSurgicalActions(surgicalActions *sa) { _surgAct = sa; }
	/// @brief Pause or resume the physics simulation.
	void setPhysicsPause(bool pause) { _physicsPaused = pause; }
	/// @brief Return true if physics simulation is currently paused.
	inline bool isPhysicsPaused(){ return  _physicsPaused; }
	/// @brief Return true if external forces were applied this frame.
	inline bool forcesApplied() { return  _forcesApplied; }

	// --- Region-specific stretch limit API ---

	/** @brief Return clinically-informed default stretch properties for common facial regions.
	 *
	 * Provides baseline values for cheek, eyelid, forehead, scalp, and nose regions
	 * based on known surgical tissue extensibility characteristics.
	 */
	static std::vector<tissueRegionProperties> getDefaultRegionProperties();

	/** @brief Set stretch limits for a specific named facial region.
	 *  @param regionName  Identifier such as "cheek", "scalp", etc.
	 *  @param stretchMin  Minimum strain limit (compression).
	 *  @param stretchMax  Maximum strain limit (extension).
	 *
	 *  Updates an existing region or creates a new entry if the name is not found.
	 */
	void setRegionStretchLimit(const std::string& regionName, float stretchMin, float stretchMax);

	/** @brief Set full properties (stretch limits and stiffness) for a named region.
	 *  @param props  A fully populated tissueRegionProperties struct.
	 */
	void setRegionProperties(const tissueRegionProperties& props);

	/** @brief Retrieve properties for a named region.
	 *  @return Pointer to the region's properties, or nullptr if the region is not found.
	 */
	const tissueRegionProperties* getRegionProperties(const std::string& regionName) const;

	/** @brief Override all regions with a single uniform stretch limit.
	 *  @param stretchMin  Global minimum strain limit.
	 *  @param stretchMax  Global maximum strain limit.
	 */
	void setGlobalStretchLimit(float stretchMin, float stretchMax);

	/// @brief Return a const reference to all currently configured region properties.
	const std::vector<tissueRegionProperties>& getAllRegionProperties() const { return _regionProperties; }

	/// @brief Return the material layer ID configuration for this scene.
	/// Defaults match the hardcoded facial tissue IDs; can be overridden via
	/// the "materialLayers" section in the .smd scene file.
	const materialLayerConfig& getMaterialLayers() const { return _materialLayers; }

	/// @brief Return the detected anatomy type for this scene.
	AnatomyType getAnatomyType() const { return _anatomyType; }

	/// @brief Validates that all referenced model files exist and the scene is consistent.
	/// @return true if the scene is valid, false if files are missing or configuration is invalid.
	bool validateScene() const;

	bccTetScene();
	~bccTetScene();

private:
	gl3wGraphics *_gl3w;
	surgicalActions *_surgAct;
	materialTriangles* _mt;  // pointer from surgGraphics.
	vnBccTetrahedra _vnTets;
	remapTetPhysics _rtp;
	tetCollisions _tetCol;
	tetSubset _tetSubsets;
	vnBccTetCutter_tbb _tc;  // multithreaded version using Intel threaded building blocks.  Much faster.  Bug #2 fix: post-parallel canonicalization sorts nodes/tets by spatial coordinates for deterministic indices across runs.
	pdTetPhysics _ptp;
	bool _forcesApplied, _tetsModified, _physicsPaused;
	AnatomyType _anatomyType = AnatomyType::FACIAL;
	std::string _dataDirectory;  ///< Stored for post-load validation.
	std::vector<std::string> _referencedObjFiles;     ///< OBJ files referenced by the scene.
	std::vector<std::string> _referencedTextureFiles;  ///< Texture files referenced by the scene.
	float _lowTetWeight;

	// --- Region-specific stretch properties ---
	std::vector<tissueRegionProperties> _regionProperties;
	// --- Material layer ID configuration ---
	materialLayerConfig _materialLayers;
	// Global fallback stretch limits (used when no region-specific override applies).
	// These are loaded from the "tetrahedralProperties" section of the .smd file.
	float _globalStretchMin;
	float _globalStretchMax;
	float _globalLowTetWeight;
	float _globalHighTetWeight;

	// Apply region-specific tet subsets to the physics solver.
	// Called during loadScene after tet lattice creation. For each region that has a
	// subsetObjFile, creates a tetSubset with the region's strain limits and stiffness.
	void applyRegionSubsets(const std::string& dataDirectory);

	struct boundingBox3{
		float corners[6];
	};
	std::vector<GLfloat> _nodeGraphicsPositions;  // homogeneous coords[4]

	std::vector<Vec3f> _firstSpatialCoords;

};

#endif // __BCC_TET_SCENE__
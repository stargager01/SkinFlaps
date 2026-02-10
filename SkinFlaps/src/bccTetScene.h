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

///////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// facialRegionProperties: Region-specific physical properties for facial skin flap simulation.
// Addresses README Issue #1: "All flap stretch limits are currently set to the same parameter."
// Different facial regions have clinically distinct stretch characteristics:
//   - Cheek/eyelid skin stretches much more than scalp/forehead skin.
//   - Nose skin (especially over cartilage) has very limited stretch.
// These properties allow the simulator to assign region-appropriate strain limits and stiffness
// values, improving surgical accuracy.
//
// Integration with spatial mapping:
//   Each region can optionally reference a closed manifold OBJ file (subsetObjFile) that encloses
//   the tet cluster belonging to that region. When provided, the existing tetSubset::createSubset()
//   mechanism is used to identify which tets belong to the region and override their strain limits.
//   When no OBJ file is provided, the region definition serves as a documented configuration that
//   can be applied via setGlobalStretchLimit() as a uniform fallback, or future spatial mapping
//   (e.g., vertex-to-region lookup by surface material ID or bounding box containment) can be
//   added to automatically assign tets to regions.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////

struct facialRegionProperties {
	std::string name;           // Region identifier, e.g. "cheek", "forehead", "eyelid", "scalp", "nose"
	float stretchMin;           // Minimum strain limit (compression limit). Lower = more compression allowed.
	float stretchMax;           // Maximum strain limit (extension limit). Higher = more stretch allowed.
	float lowTetWeight;         // Region-specific low tet stiffness weight. 0 means use global default.
	float highTetWeight;        // Region-specific high tet stiffness weight. 0 means use global default.
	std::string subsetObjFile;  // Optional: path to closed manifold OBJ defining the spatial extent of this region.
	                            // If empty, region properties are stored but not spatially mapped until an OBJ is provided.

	facialRegionProperties()
		: name(""), stretchMin(0.0f), stretchMax(0.0f),
		  lowTetWeight(0.0f), highTetWeight(0.0f), subsetObjFile("") {}

	facialRegionProperties(const std::string& regionName, float sMin, float sMax,
	                       float lowW = 0.0f, float highW = 0.0f, const std::string& objFile = "")
		: name(regionName), stretchMin(sMin), stretchMax(sMax),
		  lowTetWeight(lowW), highTetWeight(highW), subsetObjFile(objFile) {}
};

class bccTetScene
{
public:
	bool loadScene(const char *dataDirectory, const char *sceneFileName);
	void createNewPhysicsLattice(int maxDimMegatetSubdivs, int nTetSizeLevels);
	void updateOldPhysicsLattice();
	inline void nonTetPhysicsUpdate() {_ptp.initializePhysics();}
	void initPdPhysics();
	void updatePhysics();
	void fixPeriostealPeriferalVertices();
	void updateSurfaceDraw();
	pdTetPhysics* getPdTetPhysics_2(){ return &_ptp; }
	inline void setForcesAppliedFlag(){ _forcesApplied = true; }
	inline void promoteSutures() { _ptp.promoteAllSutures(); _ptp.initializePhysics(); }
	vnBccTetrahedra* getVirtualNodedBccTetrahedra() { return &_vnTets; }
	void setVisability(char surface, char physics);	// 0=off, 1=on, 2=don't change
	void setGl3wGraphics(gl3wGraphics *gl3w) { _gl3w = gl3w; }
	void createTetLatticeDrawing();
	void drawTetLattice();
	void eraseTetLattice();
	void setSurgicalActions(surgicalActions *sa) { _surgAct = sa; }
	void setPhysicsPause(bool pause) { _physicsPaused = pause; }
	inline bool isPhysicsPaused(){ return  _physicsPaused; }
	inline bool forcesApplied() { return  _forcesApplied; }

	// --- Region-specific stretch limit API (README Issue #1) ---

	// Returns clinically-informed default stretch properties for common facial regions.
	// Values are based on known surgical tissue extensibility:
	//   - Cheek:    high stretch, moderate stiffness (loose, mobile skin)
	//   - Eyelid:   high stretch, low stiffness (very thin, elastic skin)
	//   - Forehead: moderate stretch, moderate stiffness (adherent to frontalis)
	//   - Scalp:    low stretch, high stiffness (galea aponeurotica limits extension)
	//   - Nose:     low stretch, high stiffness (skin tightly bound to cartilage framework)
	static std::vector<facialRegionProperties> getDefaultRegionProperties();

	// Set stretch limits for a specific named region. If the region already exists, its
	// properties are updated. If it does not exist, a new region entry is created.
	// The region will be applied to tets via its subsetObjFile if one is set.
	void setRegionStretchLimit(const std::string& regionName, float stretchMin, float stretchMax);

	// Set stretch limits for a named region with full property control including stiffness.
	void setRegionProperties(const facialRegionProperties& props);

	// Retrieve the properties for a named region, or nullptr if not found.
	const facialRegionProperties* getRegionProperties(const std::string& regionName) const;

	// Override all regions and the global default to use a single uniform stretch limit.
	// This is a convenience fallback that applies the same strain range to every tet.
	void setGlobalStretchLimit(float stretchMin, float stretchMax);

	// Get all currently configured region properties.
	const std::vector<facialRegionProperties>& getAllRegionProperties() const { return _regionProperties; }

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
	float _lowTetWeight;

	// --- Region-specific stretch properties ---
	std::vector<facialRegionProperties> _regionProperties;
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
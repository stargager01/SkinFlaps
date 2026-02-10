#ifndef __TET_COLLISIONS__
#define __TET_COLLISIONS__

#include <vector>
#include <array>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include "Vec2f.h"
#include "Vec3f.h"
#include "Mat3x3f.h"

// forward declarations
class materialTriangles;
class vnBccTetrahedra;
class pdTetPhysics;

/** @brief Collision detection and response between the deformable skin flap and fixed anatomy.
 *
 * Manages both soft (self) collisions between flap surfaces and fixed collisions
 * against rigid structures (e.g. bone). Uses ray-casting from bed surface vertices
 * to detect interpenetration with the flap bottom surface each physics iteration.
 */
class tetCollisions
{
public:
	/// @brief Initialize soft collision ray data. Must be called after every topology change.
	void initSoftCollisions(materialTriangles *mt, vnBccTetrahedra *vnt);
	/// @brief Detect soft collision pairs for the current physics frame.
	void findSoftCollisionPairs();
	/// @brief Register a fixed (rigid) collision level-set surface loaded at startup.
	void addFixedCollisionSet(const std::string& levelSetFile, std::vector<int>& vertexIndices);
	/// @brief Rebuild fixed collision data after a topology change.
	void updateFixedCollisions(materialTriangles *mt, vnBccTetrahedra *vnt);
	/// @brief Return true if no collision sets or rays are configured.
	bool empty() { return _fixedCollisionSets.empty() && _bedRays.empty(); }
	/// @brief Assign the physics solver used to apply collision constraint forces.
	inline void setPdTetPhysics(pdTetPhysics *ptp) { _ptp = ptp; }
	/** @brief Set the collision sampling density multiplier.
	 *  @param multiplier  1.0 = vertex-only rays (default). Values > 1.0 add edge midpoint
	 *                     rays for denser sampling on convex surfaces.
	 */
	void setCollisionDensity(float multiplier);
	/// @brief Return the current collision density multiplier.
	inline float getCollisionDensity() const { return _collisionDensityMultiplier; }
	tetCollisions() : _itCount(0), _initialized(false), _collisionDensityMultiplier(1.0f), _minTime((double)FLT_MAX), _maxTime(0.0){
		_fixedCollisionSets.clear(); _flapBotTris.clear();
	}
	~tetCollisions() {}

private:
	int _itCount;
	static materialTriangles *_mt;
	static vnBccTetrahedra *_vnt;
	static pdTetPhysics *_ptp;
	bool _initialized;
	Mat3x3f _rest[6];  // material inverses used to compute deformation gradients
	struct vertexRay {
		int vertex;
		Vec3f P;
		Vec3f N;
		Vec3f materialNormal;
		int restIdx;  // only 6 of these in bcc tets
	};
	std::vector<vertexRay> _bedRays;
	std::vector<int> _flapBotTris;

	// Edge midpoint collision rays for increased density on convex surfaces.
	// These rays are placed at the midpoint of bed surface (material 5) triangle edges,
	// providing collision samples between the per-vertex rays. This catches interpenetration
	// that would otherwise slip between widely-spaced vertex rays on convex geometry.
	struct midpointRay {
		int vertex0;        // first endpoint vertex of the bed edge
		int vertex1;        // second endpoint vertex of the bed edge
		int tet;            // containing tetrahedron for this midpoint
		Vec3f baryWeight;   // barycentric weight within the containing tet
		Vec3f P;            // current spatial position (interpolated each frame)
		Vec3f N;            // current deformed normal direction
		Vec3f materialNormal; // material-space normal (averaged from endpoints, scaled by ray depth)
		int restIdx;        // deformation gradient index (from containing tet)
	};
	std::vector<midpointRay> _midpointRays;
	float _collisionDensityMultiplier;
	void initMidpointRays(std::unordered_map<int, int>& bedVerts, std::unordered_set<int>& tets);

	struct fixedCollisionSet {
		std::string levelSetFilename;
		std::vector<int> vertices;
	};
	std::list< fixedCollisionSet> _fixedCollisionSets;

	float rayDepth(const Vec3f& Vtx, const Vec3f& nrm);

	double _minTime, _maxTime;
};
#endif  // __TET_COLLISIONS__


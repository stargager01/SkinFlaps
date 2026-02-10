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

class tetCollisions
{
public:
	void initSoftCollisions(materialTriangles *mt, vnBccTetrahedra *vnt);  // call after every topo change
	void findSoftCollisionPairs();  // call every physics iteration
	void addFixedCollisionSet(const std::string& levelSetFile, std::vector<int>& vertexIndices);  // call once at load
	void updateFixedCollisions(materialTriangles *mt, vnBccTetrahedra *vnt);  // must be done after every topo change
	bool empty() { return _fixedCollisionSets.empty() && _bedRays.empty(); }
	inline void setPdTetPhysics(pdTetPhysics *ptp) { _ptp = ptp; }
	// Collision density multiplier for convex surface areas. Default 1.0 uses only per-vertex rays (original behavior).
	// Values > 1.0 add edge midpoint rays on bed surface triangles to increase collision sample density,
	// improving collision response where tight flap closures are done over very convex surfaces.
	// See README Known Issues #2.
	void setCollisionDensity(float multiplier);
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

	float inverse_rsqrt(float number);
};
#endif  // __TET_COLLISIONS__


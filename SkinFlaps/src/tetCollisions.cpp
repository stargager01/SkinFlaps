#include <cmath>
#include <unordered_set>
#include <array>
#include <map>
#include "boundingBox.h"
#include "Mat2x2f.h"
#include "insidePolygon.h"
#include "materialTriangles.h"
#include "vnBccTetrahedra.h"
#include "pdTetPhysics.h"
#include "tbb/tbb.h"
#include "tetCollisions.h"


materialTriangles *tetCollisions::_mt;
vnBccTetrahedra *tetCollisions::_vnt;
pdTetPhysics* tetCollisions::_ptp;

void tetCollisions::initSoftCollisions(materialTriangles* mt, vnBccTetrahedra* vnt) {
	_mt = mt;
	_vnt = vnt;
	if (!_initialized) {
		// generate 6 cardinal material coordinate inverses for bcc tet deformation gradients
		for (int i = 0; i < 3; ++i) {
			Mat3x3f M(0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f);
			M((i + 1) % 3, 0) = 2.0f;
			M((i + 2) % 3, 2) *= -1.0f;
			M *= (float)_vnt->getTetUnitSize();  // OK in multires as soft collisions will only occur on level 1 tets
			_rest[i << 1] = M.Inverse();
			M((i + 2) % 3, 1) *= -1.0f;
			M((i + 2) % 3, 2) *= -1.0f;
			M(i, 1) *= -1.0f;
			M(i, 2) *= -1.0f;
			_rest[(i << 1) + 1] = M.Inverse();
		}
		_initialized = true;
	}
	std::unordered_map<int, int> bedVerts;
	bedVerts.reserve(1024);
	_bedRays.clear();
	_bedRays.reserve(1024);
	_flapBotTris.clear();
	_flapBotTris.reserve(1024);
	std::unordered_set<int> tets;
	tets.reserve(2048);
	for (int j, n = _mt->numberOfTriangles(), i = 0; i < n; ++i) {
		if (_mt->triangleMaterial(i) < 0)
			continue;
		if (_mt->triangleMaterial(i) == _matLayers.subcutaneous) {
			for (j = 0; j < 3; ++j) {
				if (_mt->triangleMaterial(_mt->triAdjs(i)[j] >> 2) == _matLayers.deepBed)  // triangle at hinge with flap bed. Skip it.
					break;
			}
			if (j < 3)
				continue;
			int* tr = _mt->triangleVertices(i);
			for (j = 0; j < 3; ++j)
				tets.insert(_vnt->getVertexTetrahedron(tr[j]));
			_flapBotTris.push_back(i);
		}
		else if (_mt->triangleMaterial(i) == _matLayers.deepBed) {
			int* tr = _mt->triangleVertices(i);
			std::array<int, 3> br;
			Vec3f matPos[3];
			for (int j = 0; j < 3; ++j) {
				int tet = _vnt->getVertexTetrahedron(tr[j]);
				auto tc = _vnt->tetCentroid(tet);
				vnt->barycentricWeightToGridLocus(tc, *vnt->getVertexWeight(tr[j]), matPos[j]);
				auto bv = bedVerts.emplace(tr[j], _bedRays.size());
				if (bv.second) {
					tets.insert(tet);
					_bedRays.push_back(vertexRay());
					vertexRay* vr = &_bedRays.back();
					vr->vertex = tr[j];
					vr->materialNormal.set(0.0f, 0.0f, 0.0f);
					int ha, level;
					bool up;
					vnt->centroidType(tc, level, ha, up);
					assert(level < 2);  // should only have soft collisions where virtual noding, so must be level 1.
					vr->restIdx = ha << 1;
					if (!up)
						++(vr->restIdx);
				}
				br[j] = bv.first->second;
			}
			Vec3f N = (matPos[1] - matPos[0]) ^ (matPos[2] - matPos[0]);
			for (int j = 0; j < 3; ++j)
				_bedRays[br[j]].materialNormal += N;
		}
		else
			;
	}
	for (auto& bedR : _bedRays) {
		bedR.materialNormal.q_normalize();
		_mt->getVertexCoordinate(bedR.vertex, bedR.P.xyz);
		const int* nodes = _vnt->tetNodes(vnt->getVertexTetrahedron(bedR.vertex));
		Vec3f cols[3];
		for (int i = 1; i < 4; ++i)
			cols[i - 1] = _vnt->nodeSpatialCoordinate(nodes[i]) - _vnt->nodeSpatialCoordinate(nodes[0]);
		Mat3x3f N(cols[0], cols[1], cols[2]);
		bedR.N = N * _rest[bedR.restIdx] * bedR.materialNormal;
		bedR.materialNormal *= rayDepth(bedR.P, bedR.N) * 0.75f;  // scale
	}
	// _bedRay crossover ignored since will only use shortest one
	// Generate edge midpoint rays for increased collision density on convex surfaces (README Issue #2).
	// Only active when _collisionDensityMultiplier > 1.0.
	_midpointRays.clear();
	if (_collisionDensityMultiplier.load(std::memory_order_acquire) > 1.0f)
		initMidpointRays(bedVerts, tets);
	tets.erase(-1);
 	if (!tets.empty()) {
		std::vector<int> tetras;
		tetras.assign(tets.begin(), tets.end());
		_ptp->addSoftCollisionTets(tetras);
	}
}

void tetCollisions::setCollisionDensity(float multiplier) {
	if (multiplier < 1.0f)
		multiplier = 1.0f;
	_collisionDensityMultiplier.store(multiplier, std::memory_order_release);
}

void tetCollisions::initMidpointRays(std::unordered_map<int, int>& bedVerts, std::unordered_set<int>& tets) {
	// Generate collision rays at edge midpoints of bed surface (material 5) triangles.
	// This increases collision sample density to prevent interpenetration on convex surfaces
	// where per-vertex rays are too widely spaced (README Known Issues #2).
	//
	// Each unique edge of the bed surface gets one midpoint ray. The ray's material normal
	// is averaged from its two endpoint vertex normals (already computed in _bedRays).
	// The containing tet and barycentric weight are found via parametricEdgeTet.
	struct edgeKey {
		int v0, v1;
		bool operator==(const edgeKey& o) const { return v0 == o.v0 && v1 == o.v1; }
	};
	struct edgeKeyHash {
		std::size_t operator()(const edgeKey& k) const {
			// Cantor pairing function
			std::size_t h = (std::size_t)(k.v0 + k.v1) * (k.v0 + k.v1 + 1) / 2 + k.v1;
			return h;
		}
	};
	std::unordered_set<edgeKey, edgeKeyHash> processedEdges;
	processedEdges.reserve(1024);
	_midpointRays.reserve(512);

	for (int n = _mt->numberOfTriangles(), i = 0; i < n; ++i) {
		if (_mt->triangleMaterial(i) != _matLayers.deepBed)
			continue;
		int* tr = _mt->triangleVertices(i);
		// Process each edge of this bed triangle
		for (int e = 0; e < 3; ++e) {
			int va = tr[e];
			int vb = tr[(e + 1) % 3];
			// Order vertices so each edge is represented once
			edgeKey ek;
			ek.v0 = (va < vb) ? va : vb;
			ek.v1 = (va < vb) ? vb : va;
			if (!processedEdges.insert(ek).second)
				continue;  // edge already processed
			// Both endpoints must be bed vertices with existing rays
			auto itA = bedVerts.find(va);
			auto itB = bedVerts.find(vb);
			if (itA == bedVerts.end() || itB == bedVerts.end())
				continue;
			int rayIdxA = itA->second;
			int rayIdxB = itB->second;
			// Find the tet containing the edge midpoint using existing infrastructure
			Vec3f gridLocus;
			int midTet = _vnt->parametricEdgeTet(va, vb, 0.5f, gridLocus);
			if (midTet < 0)
				continue;  // couldn't locate containing tet, skip this midpoint
			midpointRay mr;
			mr.vertex0 = va;
			mr.vertex1 = vb;
			mr.tet = midTet;
			// Compute barycentric weight within the containing tet
			auto tc = _vnt->tetCentroid(midTet);
			_vnt->gridLocusToBarycentricWeight(gridLocus, tc, mr.baryWeight);
			// Determine deformation gradient index from the containing tet's centroid type
			int ha, level;
			bool up;
			_vnt->centroidType(tc, level, ha, up);
			mr.restIdx = ha << 1;
			if (!up)
				++(mr.restIdx);
			// Average material normals from the two endpoint bed rays (pre-normalization normals).
			// Note: _bedRays[].materialNormal has already been normalized and scaled by rayDepth*0.75
			// at this point, so we average the scaled normals. This gives the midpoint a ray depth
			// that is the mean of its two endpoints, which is reasonable for smooth surfaces.
			mr.materialNormal = (_bedRays[rayIdxA].materialNormal + _bedRays[rayIdxB].materialNormal) * 0.5f;
			// Compute initial spatial position and normal
			_vnt->getBarycentricTetPosition(mr.tet, mr.baryWeight, mr.P);
			const int* nodes = _vnt->tetNodes(mr.tet);
			Vec3f cols[3];
			for (int k = 1; k < 4; ++k)
				cols[k - 1] = _vnt->nodeSpatialCoordinate(nodes[k]) - _vnt->nodeSpatialCoordinate(nodes[0]);
			Mat3x3f Nmat(cols[0], cols[1], cols[2]);
			mr.N = Nmat * _rest[mr.restIdx] * mr.materialNormal;
			// Register this midpoint's tet for soft collision processing
			tets.insert(midTet);
			_midpointRays.push_back(mr);
		}
	}
}

void tetCollisions::findSoftCollisionPairs() {
	if (_flapBotTris.empty())
		return;

//	tbb::tick_count t0 = tbb::tick_count::now();

	for (auto& bv : _bedRays) {
		_mt->getVertexCoordinate(bv.vertex, bv.P.xyz);
		const int* nodes = _vnt->tetNodes(_vnt->getVertexTetrahedron(bv.vertex));
		Vec3f cols[3];
		for (int i = 1; i < 4; ++i)
			cols[i - 1] = _vnt->nodeSpatialCoordinate(nodes[i]) - _vnt->nodeSpatialCoordinate(nodes[0]);
		Mat3x3f N(cols[0], cols[1], cols[2]);
		bv.N = N * _rest[bv.restIdx] * bv.materialNormal;
	}
	// Update midpoint ray positions and normals from their containing tets' deformation
	for (auto& mr : _midpointRays) {
		_vnt->getBarycentricTetPosition(mr.tet, mr.baryWeight, mr.P);
		const int* nodes = _vnt->tetNodes(mr.tet);
		Vec3f cols[3];
		for (int i = 1; i < 4; ++i)
			cols[i - 1] = _vnt->nodeSpatialCoordinate(nodes[i]) - _vnt->nodeSpatialCoordinate(nodes[0]);
		Mat3x3f N(cols[0], cols[1], cols[2]);
		mr.N = N * _rest[mr.restIdx] * mr.materialNormal;
	}
	std::vector<boundingBox<float> > flapBox;
	boundingBox<float> bb;
	bb.Empty_Box();
	flapBox.assign(_flapBotTris.size(), bb);
	for (size_t n = _flapBotTris.size(), i = 0; i < n; ++i) {
		int* tr = _mt->triangleVertices(_flapBotTris[i]);
		for (int j = 0; j < 3; ++j)
			flapBox[i].Enlarge_To_Include_Point(reinterpret_cast<const float(&)[3]>(*_mt->vertexCoordinate(tr[j])));
	}
	std::vector<int> topTets, bottomTets;
	topTets.assign(_bedRays.size(), -1);
	bottomTets.assign(_bedRays.size(), -1);
	std::vector<std::array<float, 3> > topBarys, bottomBarys, collisionNormals;
	topBarys.assign(_bedRays.size(), std::array<float, 3>());
	bottomBarys.assign(_bedRays.size(), std::array<float, 3>());
	collisionNormals.assign(_bedRays.size(), std::array<float, 3>());
	std::atomic<bool> collisionsFound{false};
	tbb::parallel_for(tbb::blocked_range<size_t>(0, _bedRays.size()),
		[&](const tbb::blocked_range<size_t>& r) {
			for (size_t j = r.begin(); j != r.end(); ++j) {
				//	for (int n = _bedRays.size(), j = 0; j < n; ++j) {  // serial version
				float nearT = FLT_MAX;
				vertexRay& b = _bedRays[j];
				boundingBox<float> bedBox;
				bedBox.Empty_Box();
				bedBox.Enlarge_To_Include_Point(b.P.xyz);
				bedBox.Enlarge_To_Include_Point((b.P - b.N).xyz);  // normal negated for bed rays
				int nearV = -1;
				for (size_t n = _flapBotTris.size(), i = 0; i < n; ++i) {
					if (bedBox.Intersection(flapBox[i])) {
						Vec3f tri[3];
						int* tr = _mt->triangleVertices(_flapBotTris[i]);
						for (int k = 0; k < 3; ++k)
							_mt->getVertexCoordinate(tr[k], tri[k].xyz);
						Mat3x3f C(tri[1] - tri[0], tri[2] - tri[0], b.N);
						Vec3f R = C.Robust_Solve_Linear_System(b.P - tri[0]);
						if (R[0] < 1e-6f || R[1] < 1e-6f || R[2] < 1e-4f || R[0] + R[1] > 1.0f || R[0] > 1.0f || R[1] > 1.0f || R[2] > 1.0f)  // R[2] determines how deep the collision must go before processing triggered. Bigger makes less sticky.
							continue;
						if (nearT > R[2]) {
							nearT = R[2];
							if (R[0] + R[1] < 0.66667f)
								nearV = tr[0];
							else if (R[0] > R[1])
								nearV = tr[1];
							else
								nearV = tr[2];
							collisionsFound.store(true, std::memory_order_relaxed);
						}
					}
				}
				if (nearV < 0)
					continue;
				// found soft-soft collision pair
				topTets[j] = _vnt->getVertexTetrahedron(nearV);
				const Vec3f* W = _vnt->getVertexWeight(nearV);
				std::array<float, 3> tmp = { W->X, W->Y, W->Z };
				topBarys[j] = tmp;
				bottomTets[j] = _vnt->getVertexTetrahedron(b.vertex);
				W = _vnt->getVertexWeight(b.vertex);
				tmp = { W->X, W->Y, W->Z };
				bottomBarys[j] = tmp;
				Vec3f N = b.N * nearT;  // reverse sign of normal
				tmp = { N.X, N.Y, N.Z };
				collisionNormals[j] = tmp;
			}
		}
	);

	// Process midpoint rays for increased collision density on convex surfaces.
	// These use the same ray-triangle intersection test as vertex rays, but the
	// "bottom" of the collision pair uses the midpoint's tet and barycentric weight
	// rather than a mesh vertex's tet.
	std::vector<int> mpTopTets, mpBottomTets;
	std::vector<std::array<float, 3> > mpTopBarys, mpBottomBarys, mpCollisionNormals;
	if (!_midpointRays.empty()) {
		mpTopTets.assign(_midpointRays.size(), -1);
		mpBottomTets.assign(_midpointRays.size(), -1);
		mpTopBarys.assign(_midpointRays.size(), std::array<float, 3>());
		mpBottomBarys.assign(_midpointRays.size(), std::array<float, 3>());
		mpCollisionNormals.assign(_midpointRays.size(), std::array<float, 3>());
		tbb::parallel_for(tbb::blocked_range<size_t>(0, _midpointRays.size()),
			[&](const tbb::blocked_range<size_t>& r) {
				for (size_t j = r.begin(); j != r.end(); ++j) {
					float nearT = FLT_MAX;
					midpointRay& mr = _midpointRays[j];
					boundingBox<float> bedBox;
					bedBox.Empty_Box();
					bedBox.Enlarge_To_Include_Point(mr.P.xyz);
					bedBox.Enlarge_To_Include_Point((mr.P - mr.N).xyz);
					int nearV = -1;
					for (size_t n = _flapBotTris.size(), i = 0; i < n; ++i) {
						if (bedBox.Intersection(flapBox[i])) {
							Vec3f tri[3];
							int* tr = _mt->triangleVertices(_flapBotTris[i]);
							for (int k = 0; k < 3; ++k)
								_mt->getVertexCoordinate(tr[k], tri[k].xyz);
							Mat3x3f C(tri[1] - tri[0], tri[2] - tri[0], mr.N);
							Vec3f R = C.Robust_Solve_Linear_System(mr.P - tri[0]);
							if (R[0] < 1e-6f || R[1] < 1e-6f || R[2] < 1e-4f || R[0] + R[1] > 1.0f || R[0] > 1.0f || R[1] > 1.0f || R[2] > 1.0f)
								continue;
							if (nearT > R[2]) {
								nearT = R[2];
								if (R[0] + R[1] < 0.66667f)
									nearV = tr[0];
								else if (R[0] > R[1])
									nearV = tr[1];
								else
									nearV = tr[2];
								collisionsFound.store(true, std::memory_order_relaxed);
							}
						}
					}
					if (nearV < 0)
						continue;
					// found midpoint collision pair
					mpTopTets[j] = _vnt->getVertexTetrahedron(nearV);
					const Vec3f* W = _vnt->getVertexWeight(nearV);
					std::array<float, 3> tmp = { W->X, W->Y, W->Z };
					mpTopBarys[j] = tmp;
					// Bottom of midpoint collision uses the midpoint's own tet and barycentric weight
					mpBottomTets[j] = mr.tet;
					tmp = { mr.baryWeight.X, mr.baryWeight.Y, mr.baryWeight.Z };
					mpBottomBarys[j] = tmp;
					Vec3f Nv = mr.N * nearT;
					tmp = { Nv.X, Nv.Y, Nv.Z };
					mpCollisionNormals[j] = tmp;
				}
			}
		);
	}

	if (!collisionsFound.load(std::memory_order_acquire)) {
		_ptp->clearSoftCollisions();
		return;
	}
	// Compact vertex ray collision results
	int offset = 0;
	for (int n = topTets.size(), i = 0; i < n; ++i) {
		if (topTets[i] > -1) {
			topTets[offset] = topTets[i];
			bottomTets[offset] = bottomTets[i];
			topBarys[offset] = topBarys[i];
			bottomBarys[offset] = bottomBarys[i];
			collisionNormals[offset++] = collisionNormals[i];
		}
	}
	topTets.resize(offset);
	bottomTets.resize(offset);
	topBarys.resize(offset);
	bottomBarys.resize(offset);
	collisionNormals.resize(offset);
	// Append midpoint ray collision results into the same arrays
	for (size_t n = mpTopTets.size(), i = 0; i < n; ++i) {
		if (mpTopTets[i] > -1) {
			topTets.push_back(mpTopTets[i]);
			bottomTets.push_back(mpBottomTets[i]);
			topBarys.push_back(mpTopBarys[i]);
			bottomBarys.push_back(mpBottomBarys[i]);
			collisionNormals.push_back(mpCollisionNormals[i]);
		}
	}

//	tbb::tick_count t1 = tbb::tick_count::now();
//	double time = (t1 - t0).seconds();
//	if (_maxTime < time)
//		_maxTime = time;
//	if (_minTime > time)
//		_minTime = time;
//	std::cout << "Soft collision minimum processing time was " << _minTime << " and maximum processing time was " << _maxTime << "verts colliding " << topTets.size() << "\n";
	// tbb speeds up my 20 thread machine by a factor of 4 to 0.4495 milliseconds so overhead significant and on low core machine may not be worth it
	_ptp->currentSoftCollisionPairs(topTets, topBarys, bottomTets, bottomBarys, collisionNormals);
}


void tetCollisions::addFixedCollisionSet(const std::string& levelSetFile, std::vector<int>& vertexIndices) {  // call once at load
	fixedCollisionSet fc;
	fc.levelSetFilename = levelSetFile;
	fc.vertices.assign(vertexIndices.begin(), vertexIndices.end());
	_fixedCollisionSets.push_back(fc);
}

void tetCollisions::updateFixedCollisions(materialTriangles *mt, vnBccTetrahedra *vnt) {  // call after every topo change
	_mt = mt;
	_vnt = vnt;
	for (auto& fc : _fixedCollisionSets) {
		std::vector<int> tets;
		std::vector<std::array<float, 3> > weights;
		tets.reserve(fc.vertices.size());
		weights.reserve(fc.vertices.size());
		for (auto &v : fc.vertices) {
			int tet = _vnt->getVertexTetrahedron(v);
			if (tet < 0)  // vertex has been excised
				continue;
			tets.push_back(tet);
			const Vec3f* v3 = _vnt->getVertexWeight(v);
			std::array<float, 3> va = { v3->X, v3->Y, v3->Z };
			weights.push_back(va);
		}
		_ptp->addFixedCollisionSet(fc.levelSetFilename, tets, weights);
	}
}

float tetCollisions::rayDepth(const Vec3f &vtx, const Vec3f &nrm) {  // depth of a ray from vertex to nearest deep surface
	boundingBox<float> bb, tbb;
	bb.Empty_Box();
	bb.Enlarge_To_Include_Point(vtx.xyz);
	bb.Enlarge_To_Include_Point((vtx - nrm*3.0f).xyz);
	Vec3f P, T[3], N;
	float dSq, dSqMin = FLT_MAX, ret;
	// do slightly permissive find
	for (int n = _mt->numberOfTriangles(), j, i = 0; i < n; ++i) {
		int tm = _mt->triangleMaterial(i);
		if ( tm < 0)  // tm == 3 || tm == 4 ||  only look for permissible deep stop triangles.
			continue;
		int* tr = _mt->triangleVertices(i);
		tbb.Empty_Box();
		for (j = 0; j < 3; ++j) {
			_mt->getVertexCoordinate(tr[j], T[j].xyz);
			tbb.Enlarge_To_Include_Point(T[j].xyz);
		}
		if (!bb.Intersection(tbb))
			continue;
		N = (T[1] - T[0]) ^ (T[2] - T[0]);
		if (N * nrm > 0.0f)
			continue;
		Mat3x3f M;
		M.Initialize_With_Column_Vectors(T[1] - T[0], T[2] - T[0], nrm);
		P = M.Robust_Solve_Linear_System(vtx - T[0]);
		if (P.X < -1e-16 || P.Y < -1e-16 || P.X > 1.00001 || P.Y > 1.00001 || P.X + P.Y >= 1.00001)
			continue;
		if (P.Z <= 1e-3)  // look only in correct direction for non-self value
			continue;
		Vec3f intersect = T[0] * (1.0 - P.X - P.Y) + T[1] * P.X + T[2] * P.Y;
		dSq = (intersect - vtx).length2();
		if (dSq < dSqMin) {
			dSqMin = dSq;
		}
	}
	if (dSqMin < FLT_MAX && dSqMin > 1e-5f)
		ret = std::sqrt(dSqMin);
	else
		ret = (_vnt->getMaximumCorner() - _vnt->getMinimumCorner()).length() * _vnt->getTetUnitSize() * 0.02f;  // maximum allowable bed ray depth
	return ret;
}

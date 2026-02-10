///////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// File: deepCut.h
// Author: Court Cutting MD
// Date: 1/27/2020
// Purpose: Yet another version of deepCut tool.  This version is designed to deal with transiently inverted tets which arise in the physics.
//    Previous versions found the cut tets in spatial coords.  Unfortunately when inverted tets were righted this pulled parts of the triangulated
//    surface inside out.  The resulting occasional self intersections crashed the tet cutter.  For this reason the interior of this deep cutter
//    will have its vertices found in material coordinates so no inversions are possible.  This will result in the following loss of realism:
//    In previous versions pulling up the central part of a surface while holding the perifery down would result in one cut side being concave
//    and the other convex as a result of a single planar cut.  This version will lack that reality and both sides will be relatively planar.
//    This version will also dispense with the deep side of incisions being planar when cutting material 2.
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#ifndef __DEEP_CUT__
#define __DEEP_CUT__

#include <vector>
#include <array>
#include "Vec3f.h"
#include "materialTriangles.h"
#include "skinCutUndermineTets.h"

#pragma warning (disable : 4267)

// forward declarations
class vnBccTetrahedra;
class fence;
class SurgicalSimGui;
struct rayTriangleIntersect;

/** @brief Full-thickness incision tool that cuts through the BCC tet lattice.
 *
 * Performs deep surgical cuts by computing intersections in material coordinates
 * to avoid artifacts from transiently inverted tets in the physics simulation.
 * Extends skinCutUndermineTets with deep-plane cutting and periosteal undermining.
 */
class deepCut : public skinCutUndermineTets
{
public:
	/// @brief Enable or disable verbose diagnostic logging for cut operations.
	void setDiagnosticLog(bool enable) { _diagnosticLog = enable; }

	/** @brief Set the inverse of deep cut interior point spacing.
	 *  @param spacing  Inverse spacing value; higher means denser interior points. Default is 15.0f.
	 *
	 *  This value is model-dependent and should be configured per scene file.
	 */
	void setCutSpacingInv(float spacing) { _cutSpacingInv = spacing; }
	/// @brief Return the current inverse cut spacing value.
	float getCutSpacingInv() const { return _cutSpacingInv; }

	/// @brief Validate and correct a fence path before using it as a cut guide.
	bool inputCorrectFence(fence* fp, SurgicalSimGui* ffg);
	/** @brief Add a deep incision post at a surface triangle location.
	 *  @param triangle    Triangle index on the skin surface.
	 *  @param uv          Parametric coordinates on the triangle.
	 *  @param rayDirection  View ray direction for determining cut depth.
	 *  @param closedEnd   If true, this post closes the incision end.
	 *  @return The index of the newly added post, or -1 on failure.
	 */
	int addDeepPost(const int triangle, const float(&uv)[2], const Vec3d& rayDirection, bool closedEnd);
	/// @brief Remove the last added deep post (undo support).
	inline void popLastDeepPost() { if(!_deepPosts.empty()) _deepPosts.pop_back(); }
	/// @brief Return the number of deep posts currently placed.
	inline int numberOfDeepPosts() { return (int)_deepPosts.size(); }
	/// @brief Prevent the cut path from crossing over a previous incision.
	int preventPreviousCrossover(const int postNum);  // COURT make private with new interface
	/// @brief Retrieve the spatial positions and normals of all deep posts.
	void getDeepPosts(std::vector<Vec3f>& xyz, std::vector<Vec3f>& nrm);
	/** @brief Execute the deep cut using the currently placed deep posts.
	 *  @return True if the cut was completed successfully.
	 *
	 *  All post data must be loaded in _deepPosts before calling. Physics must be paused.
	 */
	bool cutDeep();  // data already loaded in _deepPosts in this updated version
	/// @brief Clear all deep posts and reset the cutter state.
	void clearDeepCutter(){_deepPosts.clear();}
	/// @brief Add a periosteal undermine triangle following a deep cut through periosteum.
	int addPeriostealUndermineTriangle(const int topTriangle, const Vec3f &linePickDirection, const bool incisionConnect);  // can only follow a deepCut through periosteum.
	deepCut() { _deepXyz.clear(); _deepPosts.clear(); }
	deepCut(const deepCut&) = delete;
	deepCut& operator=(const deepCut&) = delete;
	~deepCut(){}

protected:
	bool _diagnosticLog = false;
	bool _startOpen, _endOpen;
	std::vector<std::array<int, 3> > _firstSideTriangles;  // new triangles produced on first side of the cut. in sort order so can do binary search, but not usually consecutive.
	struct surfaceCutLine {  // a cut line intersecting a cutting triangle with the embedded surface
		int rtiPostTo;
		int rtiIndexTo;
		double lowestV;  // smallest v value of the bilinear surface in an interpost scl
		std::list<int> deepVertsTris;  // sequential deep mtTriangle vertices for this intersect line if cutting path.  If not contains triangles in path during topological search.
		std::list<Vec2d> deepUVs;  // sequential UV patch coordinates corresponding to deepVerts above
	};
	struct rayTriangleIntersect {
		int triangle;
		double uv[2];
		Vec3d intersect;
		double rayParam;
		int postNum;
		int rayIndex;
		bool solidDown;
		int mat2Vert;
		int deepVert;
		surfaceCutLine scl;
		std::vector<int> dcl;  // deep cut line vertices through interior solid. Always top to bottom.
	};
	struct bilinearPatch {  // patch data for nVidia intersection routine
		Vec3d e10;
		Vec3d e01;
		Vec3d e11;
		Vec3d e00;
		Vec3d qn;
		Vec3d P00;
		Vec3d P10;
		Vec3d P01;
		Vec3d P11;
	};
	struct matTriangle {
		int v[3];
		int tex[3];
		int material;
	};
	struct endPlane {
		Vec3d P;
		Vec3d U;
		Vec3d V;
		Vec3d N;
		double d;
		double VlengthSqInv;
		std::vector<matTriangle> quadTriangles;
//		std::vector<materialTriangles::matTriangle> quadTriangles;
	}_endPlanes[2];
	struct deepPost {
		bool closedEnd;
		std::vector<rayTriangleIntersect> triIntersects;
		Vec3d rayDirection;
		bilinearPatch bl;
		std::vector<matTriangle> quadTriangles;
//		std::vector<materialTriangles::matTriangle> quadTriangles;
	};
	std::vector< deepPost> _deepPosts;
	struct vertUvPolygon {
		std::vector<int> vertices;
		std::vector<Vec2d> uvs;
	};

	std::vector<Vec3d> _deepXyz;  // deep spatial coords for each mt vertex. material 2 vertices use deepBed coords.  rayIntersectSolids() repeatedly use these
	float _maxSceneSize;
	float _cutSpacingInv = 15.0f;  // inverse of deep cut interior point spacing; model-dependent, configurable via setCutSpacingInv()
	int _preDeepCutVerts;
	int _previousSkinTopEnd, _loopSkinTopBegin;
	std::list<std::list<int> > _holePolyLines;  // pair first is deepVert, second topVert

	void bilinearNormal(const double& u, const double& v, const bilinearPatch& bl, Vec3d& normal) {
		normal = bl.e11 * u + bl.e00 * (1.0 - u);
		Vec3d V = bl.e01 * v + bl.e10 * (1.0 - v);
		normal = normal ^ V;
	}

	bool getDeepSpatialCoordinates();  // used in new version.  Must have physics paused until deepCut complete or will be invalid.
	bool updateDeepSpatialCoordinates();
	bool rayIntersectMaterialTriangles(const Vec3d& rayStart, const Vec3d& rayDirection, std::vector<rayTriangleIntersect>& intersects);
	double surfacePath(rayTriangleIntersect& from, const rayTriangleIntersect& to, const bool cutPath, double& minimumBilinearV);
	void cutSkinLine(int startV, Vec2d& startUV, int endV, Vec2d& endUV, std::vector<unsigned int>& te, std::vector<float>& params, std::vector<Vec2d>& UVs, bool Tin, bool Tout, surfaceCutLine& scl);
	void cutDeepSurface(int startV, Vec2d& startUV, int endV, Vec2d& endUV, std::vector<unsigned int>& te, std::vector<float>& params, std::vector<Vec2d>& UVs, surfaceCutLine& scl);
	bool connectOpenEnd(int postNum);
	bool deepCutQuad(int postNum);
	void getDeepCutLine(rayTriangleIntersect& top, rayTriangleIntersect& bot);  // in material loci, not yet projected onto spatial plane
	bool uniqueSpatialTet(const Vec3f pos, int& tet, Vec3f& baryWeight);
	void rayBilinearPatchIntersection(Vec3d& rayStart, Vec3d& rayN, const Vec3d& P00, const Vec3d& P10, const Vec3d& P01, const Vec3d& P11, double(&rayParam)[2], double(&faceParam)[2][2]);
	void makeBilinearPatch(const Vec3d& P00, const Vec3d& P10, const Vec3d& P01, const Vec3d& P11, bilinearPatch& bl);
	int bilinearRayIntersection(const Vec3d& rayStart, const Vec3d& rayDir, const bilinearPatch& bl, double (&rayParam)[2], Vec2d (&faceParams)[2]);
	void findCutInteriorHoles(const bilinearPatch* blp, const endPlane* ep, const std::vector<Vec2d> &bUv, const std::vector<std::pair<int, Vec2d> >& deepOuterPolygon, std::list< vertUvPolygon >& holes);
	bool topConnectToPreviousPost(int postNum);
	bool deepConnectToPreviousPost(int postNum);
	void mat2BorderSplit(int borderV, int borderTx, int incisionTopV);
	bool planeRayIntersection(const Vec3d P, const Vec3d R, const endPlane* ep, double& rayParam, Vec2d& faceParam);
	void makePolygonTriangles(const std::list<int>& polyVerts, const std::list<Vec2d>& polyUV, const bilinearPatch* blp, const endPlane* ep, std::vector<matTriangle>& polyTriangles);
	bool deepCutEndPlane(int endPlane);
	double surfacePathSub(int topStartV, int deepStartV, int topEndV, int deepEndV, const unsigned int startTE, const double &startParam, const Vec2d& startUV, const int endTriangle,
		const bilinearPatch* bl, const endPlane* ep, const bool cutPath, surfaceCutLine& scl, double& minimumBilinearV);

};

#endif  // __DEEP_CUT__






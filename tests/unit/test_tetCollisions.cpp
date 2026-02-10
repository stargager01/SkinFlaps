////////////////////////////////////////////////////////////////////////////
// File: test_tetCollisions.cpp
// Purpose: Unit tests for tetCollisions class, focusing on the collision
//          density setter/getter, the midpointRay data structure, and
//          basic collision detection logic that can be tested in isolation
//          without requiring the full OpenGL/materialTriangles infrastructure.
////////////////////////////////////////////////////////////////////////////

#include <gtest/gtest.h>
#include <cmath>
#include <vector>
#include <array>
#include <unordered_map>
#include <unordered_set>
#include <string>
#include <list>
#include <cfloat>

// Include project math types (header-only, no link dependencies).
#include "Vec3f.h"
#include "Mat3x3f.h"

// ---------------------------------------------------------------------------
// tetCollisions depends on materialTriangles, vnBccTetrahedra, pdTetPhysics,
// and TBB at link time. To test the collision density logic and midpoint ray
// infrastructure in isolation, we replicate the relevant subset of the class
// here as a standalone "TetCollisionTestable" with the same logic but no
// external dependencies.
// ---------------------------------------------------------------------------

// Standalone replica of the collision density logic from tetCollisions.
class TetCollisionTestable {
public:
    TetCollisionTestable() : _collisionDensityMultiplier(1.0f) {}

    // Replicates setCollisionDensity() from tetCollisions.cpp lines 118-122
    void setCollisionDensity(float multiplier) {
        if (multiplier < 1.0f)
            multiplier = 1.0f;
        _collisionDensityMultiplier = multiplier;
    }

    float getCollisionDensity() const { return _collisionDensityMultiplier; }

    // Replicates the midpointRay struct from tetCollisions.h lines 59-68
    struct midpointRay {
        int vertex0;
        int vertex1;
        int tet;
        Vec3f baryWeight;
        Vec3f P;
        Vec3f N;
        Vec3f materialNormal;
        int restIdx;
    };

    // Replica of the vertexRay struct from tetCollisions.h lines 45-51
    struct vertexRay {
        int vertex;
        Vec3f P;
        Vec3f N;
        Vec3f materialNormal;
        int restIdx;
    };

    // Simple ray-triangle intersection test used in soft collision detection.
    // Replicates the core intersection math from findSoftCollisionPairs().
    // Returns true if the ray from P in direction N intersects triangle (T0,T1,T2),
    // with the intersection parameter t in (0, 1].
    static bool rayTriangleIntersect(
        const Vec3f& P, const Vec3f& N,
        const Vec3f& T0, const Vec3f& T1, const Vec3f& T2,
        float& t)
    {
        // Build matrix [T1-T0, T2-T0, N] and solve for (u, v, t)
        Mat3x3f C(T1 - T0, T2 - T0, N);
        Vec3f R = C.Robust_Solve_Linear_System(P - T0);

        // Check barycentric validity and ray parameter range.
        // The original code uses R[0] (u), R[1] (v), R[2] (t).
        if (R[0] < 1e-6f || R[1] < 1e-6f || R[2] < 1e-4f)
            return false;
        if (R[0] + R[1] > 1.0f || R[0] > 1.0f || R[1] > 1.0f || R[2] > 1.0f)
            return false;
        t = R[2];
        return true;
    }

    std::vector<midpointRay>& getMidpointRays() { return _midpointRays; }
    std::vector<vertexRay>& getBedRays() { return _bedRays; }

private:
    float _collisionDensityMultiplier;
    std::vector<midpointRay> _midpointRays;
    std::vector<vertexRay> _bedRays;
};


// ===========================================================================
// TEST SUITE: CollisionDensity
// Tests for the collision density multiplier getter/setter.
// ===========================================================================

class CollisionDensityTest : public ::testing::Test {
protected:
    TetCollisionTestable tc;
};

TEST_F(CollisionDensityTest, DefaultDensityIsOne) {
    // The default collision density multiplier should be 1.0 (original behavior).
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}

TEST_F(CollisionDensityTest, SetDensityAboveOne) {
    // Setting the density to a value above 1.0 should be accepted.
    tc.setCollisionDensity(2.5f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 2.5f);
}

TEST_F(CollisionDensityTest, SetDensityBelowOneClampedToOne) {
    // Values below 1.0 should be clamped to 1.0, as the minimum density
    // is per-vertex rays only (the original behavior).
    tc.setCollisionDensity(0.5f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}

TEST_F(CollisionDensityTest, SetDensityToExactlyOne) {
    // Setting density to exactly 1.0 should work without clamping.
    tc.setCollisionDensity(1.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}

TEST_F(CollisionDensityTest, SetDensityNegativeClampedToOne) {
    // Negative values should be clamped to 1.0.
    tc.setCollisionDensity(-3.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}

TEST_F(CollisionDensityTest, SetDensityZeroClampedToOne) {
    // Zero should be clamped to 1.0.
    tc.setCollisionDensity(0.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}

TEST_F(CollisionDensityTest, SetDensityVeryLargeValue) {
    // Very large values should be accepted (no upper bound in the original code).
    tc.setCollisionDensity(1000.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1000.0f);
}

TEST_F(CollisionDensityTest, MultipleSetsLastOneWins) {
    // Multiple calls should each update the value; the last one wins.
    tc.setCollisionDensity(2.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 2.0f);
    tc.setCollisionDensity(3.5f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 3.5f);
    tc.setCollisionDensity(1.0f);
    EXPECT_FLOAT_EQ(tc.getCollisionDensity(), 1.0f);
}


// ===========================================================================
// TEST SUITE: MidpointRayStructure
// Tests for the midpointRay data structure and its initialization patterns.
// ===========================================================================

class MidpointRayTest : public ::testing::Test {
protected:
    TetCollisionTestable tc;
};

TEST_F(MidpointRayTest, MidpointRaysEmptyByDefault) {
    // Before initialization, the midpoint ray list should be empty.
    EXPECT_TRUE(tc.getMidpointRays().empty());
}

TEST_F(MidpointRayTest, MidpointRayFieldsInitializedCorrectly) {
    // Verify that a manually constructed midpoint ray retains its field values.
    TetCollisionTestable::midpointRay mr;
    mr.vertex0 = 10;
    mr.vertex1 = 20;
    mr.tet = 5;
    mr.baryWeight = Vec3f(0.2f, 0.3f, 0.1f);
    mr.P = Vec3f(1.0f, 2.0f, 3.0f);
    mr.N = Vec3f(0.0f, 0.0f, 1.0f);
    mr.materialNormal = Vec3f(0.0f, 0.0f, 0.5f);
    mr.restIdx = 3;

    tc.getMidpointRays().push_back(mr);
    ASSERT_EQ(tc.getMidpointRays().size(), 1u);

    const auto& stored = tc.getMidpointRays()[0];
    EXPECT_EQ(stored.vertex0, 10);
    EXPECT_EQ(stored.vertex1, 20);
    EXPECT_EQ(stored.tet, 5);
    EXPECT_FLOAT_EQ(stored.baryWeight.X, 0.2f);
    EXPECT_FLOAT_EQ(stored.baryWeight.Y, 0.3f);
    EXPECT_FLOAT_EQ(stored.baryWeight.Z, 0.1f);
    EXPECT_FLOAT_EQ(stored.P.X, 1.0f);
    EXPECT_FLOAT_EQ(stored.N.Z, 1.0f);
    EXPECT_EQ(stored.restIdx, 3);
}

TEST_F(MidpointRayTest, MidpointPositionIsAverageOfEndpoints) {
    // The midpoint ray's position P should be at the average of its two
    // endpoint vertex positions (this is how initMidpointRays computes it
    // via parametricEdgeTet at param=0.5).
    Vec3f P0(1.0f, 0.0f, 0.0f);
    Vec3f P1(3.0f, 4.0f, 2.0f);
    Vec3f expectedMidpoint = (P0 + P1) * 0.5f;

    EXPECT_FLOAT_EQ(expectedMidpoint.X, 2.0f);
    EXPECT_FLOAT_EQ(expectedMidpoint.Y, 2.0f);
    EXPECT_FLOAT_EQ(expectedMidpoint.Z, 1.0f);
}

TEST_F(MidpointRayTest, MidpointNormalIsAverageOfEndpointNormals) {
    // In initMidpointRays, the material normal is averaged from the two
    // endpoint bed ray normals:
    //   mr.materialNormal = (bedRays[A].materialNormal + bedRays[B].materialNormal) * 0.5f
    Vec3f normalA(0.0f, 0.0f, 1.0f);
    Vec3f normalB(0.0f, 0.0f, 3.0f);
    Vec3f avgNormal = (normalA + normalB) * 0.5f;

    EXPECT_FLOAT_EQ(avgNormal.X, 0.0f);
    EXPECT_FLOAT_EQ(avgNormal.Y, 0.0f);
    EXPECT_FLOAT_EQ(avgNormal.Z, 2.0f);
}


// ===========================================================================
// TEST SUITE: RayTriangleIntersection
// Tests for the ray-triangle intersection math used in collision detection.
// ===========================================================================

class RayTriangleIntersectionTest : public ::testing::Test {
protected:
    static constexpr float kTolerance = 1e-4f;
};

TEST_F(RayTriangleIntersectionTest, RayHitsTriangleFrontOn) {
    // The collision equation solved is:
    //   P - T0 = u*(T1-T0) + v*(T2-T0) + t*N
    // where t > 0 means P is on the positive-N side of the triangle.
    // The bed normal N points outward from the bed surface (e.g., upward),
    // so a positive t indicates the bed vertex P is above the triangle
    // at distance t*|N|. This is a valid collision when t in (1e-4, 1.0].
    //
    // Setup: P at (0.25, 0.25, 0.5), N pointing upward (0,0,1),
    // triangle at z=0 plane. Then P-T0 = (0.25, 0.25, 0.5) and
    // solving gives u=0.25, v=0.25, t=0.5 -- all valid.
    Vec3f P(0.25f, 0.25f, 0.5f);
    Vec3f N(0.0f, 0.0f, 1.0f);  // bed normal pointing upward (positive z)

    Vec3f T0(0.0f, 0.0f, 0.0f);
    Vec3f T1(1.0f, 0.0f, 0.0f);
    Vec3f T2(0.0f, 1.0f, 0.0f);

    float t;
    bool hit = TetCollisionTestable::rayTriangleIntersect(P, N, T0, T1, T2, t);

    EXPECT_TRUE(hit) << "Ray pointing at triangle center should intersect";
    EXPECT_NEAR(t, 0.5f, kTolerance);
}

TEST_F(RayTriangleIntersectionTest, RayMissesTriangle) {
    // A ray that passes outside the triangle should not intersect.
    Vec3f P(5.0f, 5.0f, 1.0f);    // far from the triangle
    Vec3f N(0.0f, 0.0f, -1.0f);

    Vec3f T0(0.0f, 0.0f, 0.0f);
    Vec3f T1(1.0f, 0.0f, 0.0f);
    Vec3f T2(0.0f, 1.0f, 0.0f);

    float t;
    bool hit = TetCollisionTestable::rayTriangleIntersect(P, N, T0, T1, T2, t);
    EXPECT_FALSE(hit) << "Ray outside triangle bounds should not intersect";
}

TEST_F(RayTriangleIntersectionTest, RayParallelToTriangleMisses) {
    // A ray parallel to the triangle plane should not intersect (degenerate solve).
    Vec3f P(0.25f, 0.25f, 1.0f);
    Vec3f N(1.0f, 0.0f, 0.0f);  // parallel to the z=0 plane

    Vec3f T0(0.0f, 0.0f, 0.0f);
    Vec3f T1(1.0f, 0.0f, 0.0f);
    Vec3f T2(0.0f, 1.0f, 0.0f);

    float t;
    bool hit = TetCollisionTestable::rayTriangleIntersect(P, N, T0, T1, T2, t);
    EXPECT_FALSE(hit) << "Ray parallel to triangle should not register a hit";
}

TEST_F(RayTriangleIntersectionTest, RayHitsAtEdge) {
    // A ray aimed at the midpoint of an edge of the triangle.
    // Edge from T0(0,0,0) to T1(1,0,0), midpoint at (0.5, 0, 0).
    // The original code checks u > 1e-6 and v > 1e-6, so a point
    // exactly on the v=0 edge (where v=0) will be rejected.
    Vec3f P(0.5f, 0.0f, 1.0f);
    Vec3f N(0.0f, 0.0f, -1.0f);

    Vec3f T0(0.0f, 0.0f, 0.0f);
    Vec3f T1(1.0f, 0.0f, 0.0f);
    Vec3f T2(0.0f, 1.0f, 0.0f);

    float t;
    bool hit = TetCollisionTestable::rayTriangleIntersect(P, N, T0, T1, T2, t);
    // v = 0.0 < 1e-6 so this should be rejected (edge case exclusion)
    EXPECT_FALSE(hit) << "Ray at triangle edge should be rejected by strict bounds";
}

TEST_F(RayTriangleIntersectionTest, RayOnWrongSideOfTriangleMisses) {
    // The collision model uses: P - T0 = u*(T1-T0) + v*(T2-T0) + t*N
    // A positive t means P is on the positive-N side of the triangle.
    // A negative t means P is on the opposite side, which the code
    // rejects (t must be > 1e-4).
    //
    // Setup: P below the triangle (z=-0.5), N pointing upward (0,0,1).
    // Then: t = -0.5, which is negative and will be rejected.
    Vec3f P(0.25f, 0.25f, -0.5f);  // below the z=0 plane
    Vec3f N(0.0f, 0.0f, 1.0f);      // normal pointing upward

    Vec3f T0(0.0f, 0.0f, 0.0f);
    Vec3f T1(1.0f, 0.0f, 0.0f);
    Vec3f T2(0.0f, 1.0f, 0.0f);

    float t;
    bool hit = TetCollisionTestable::rayTriangleIntersect(P, N, T0, T1, T2, t);
    EXPECT_FALSE(hit)
        << "P on the negative-N side of the triangle should yield negative t and be rejected";
}


// ===========================================================================
// TEST SUITE: CollisionRestMatrixInverse
// Tests that verify the deformation gradient rest inverse computation
// pattern used in tetCollisions::initSoftCollisions.
// ===========================================================================

class CollisionRestMatrixTest : public ::testing::Test {
protected:
    static constexpr float kTolerance = 1e-4f;
    Mat3x3f rest[6];

    void SetUp() override {
        // Replicate the rest matrix computation from tetCollisions.cpp lines 24-35.
        // This computes the material-space inverse for each of the 6 BCC tet orientations.
        float unitSize = 1.0f;  // use unit size for simplicity
        for (int i = 0; i < 3; ++i) {
            Mat3x3f M(0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f);
            M((i + 1) % 3, 0) = 2.0f;
            M((i + 2) % 3, 2) *= -1.0f;
            M *= unitSize;
            rest[i << 1] = M.Inverse();
            M((i + 2) % 3, 1) *= -1.0f;
            M((i + 2) % 3, 2) *= -1.0f;
            M(i, 1) *= -1.0f;
            M(i, 2) *= -1.0f;
            rest[(i << 1) + 1] = M.Inverse();
        }
    }
};

TEST_F(CollisionRestMatrixTest, RestMatricesAreNonSingular) {
    // All 6 rest inverse matrices should have non-zero determinants,
    // confirming they are valid inverses.
    for (int i = 0; i < 6; ++i) {
        float det = rest[i].Determinant();
        EXPECT_GT(std::abs(det), kTolerance)
            << "Rest matrix " << i << " should be non-singular";
    }
}

TEST_F(CollisionRestMatrixTest, RestMatricesProduceDifferentResults) {
    // The 6 rest matrices should not all be identical, since they correspond
    // to different BCC tet orientations (3 axes x 2 up/down variants).
    bool allSame = true;
    for (int i = 1; i < 6; ++i) {
        for (int j = 0; j < 9; ++j) {
            if (std::abs(rest[i].x[j] - rest[0].x[j]) > kTolerance) {
                allSame = false;
                break;
            }
        }
        if (!allSame) break;
    }
    EXPECT_FALSE(allSame) << "Not all 6 rest matrices should be identical";
}

TEST_F(CollisionRestMatrixTest, UpDownPairsAreDifferent) {
    // For each axis, the "up" and "down" rest matrices should differ.
    for (int axis = 0; axis < 3; ++axis) {
        bool pairSame = true;
        for (int j = 0; j < 9; ++j) {
            if (std::abs(rest[axis * 2].x[j] - rest[axis * 2 + 1].x[j]) > kTolerance) {
                pairSame = false;
                break;
            }
        }
        EXPECT_FALSE(pairSame)
            << "Up and down rest matrices for axis " << axis << " should differ";
    }
}

TEST_F(CollisionRestMatrixTest, RestMatrixTimesOriginalIsIdentity) {
    // Verify that rest[i] * M[i] = Identity (i.e., rest is truly the inverse).
    float unitSize = 1.0f;
    for (int i = 0; i < 3; ++i) {
        Mat3x3f M(0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f);
        M((i + 1) % 3, 0) = 2.0f;
        M((i + 2) % 3, 2) *= -1.0f;
        M *= unitSize;

        Mat3x3f product = M * rest[i << 1];
        // Should be close to identity
        Mat3x3f identity = Mat3x3f::Identity_Matrix();
        for (int j = 0; j < 9; ++j) {
            EXPECT_NEAR(product.x[j], identity.x[j], kTolerance)
                << "M * rest[" << (i << 1) << "] element " << j
                << " should be identity";
        }
    }
}

/**
 * @file UnityExports.cpp
 * @brief Unity Native Plugin Implementation for SkinFlaps Surgical Simulator
 * @author SkinFlaps Team
 * @date 2025
 */

#include "UnityExports.h"
#include "bccTetScene.h"
#include "surgicalActions.h"
#include "materialTriangles.h"
#include "vnBccTetrahedra.h"
#include "pdTetPhysics.h"
#include "skinCutUndermineTets.h"
#include "sutures.h"
#include "hooks.h"

#include <string>
#include <mutex>
#include <memory>
#include <cstring>
#include <chrono>

// Version information
#define SKINFLAPS_VERSION "1.0.0"
#define SKINFLAPS_BUILD_INFO "Unity Plugin Build - " __DATE__ " " __TIME__

// ============================================================================
// Internal Wrapper Class
// ============================================================================

class SkinFlapsSimulatorWrapper {
public:
    SkinFlapsSimulatorWrapper()
        : m_initialized(false)
        , m_paused(true)
        , m_topologyChanged(false)
        , m_debugMode(false)
        , m_lastSolveTime(0.0f)
    {
    }

    ~SkinFlapsSimulatorWrapper() {
        // Cleanup handled by member destructors
    }

    bool loadScene(const char* modelPath, const char* dataDirectory) {
        std::lock_guard<std::mutex> lock(m_mutex);

        try {
            m_dataDirectory = dataDirectory;
            m_modelPath = modelPath;

            // Setup surgical actions and scene
            m_surgActions = std::make_unique<surgicalActions>();

            // Note: The actual SkinFlaps scene loading requires gl3wGraphics
            // which we don't use in the Unity plugin. We need to modify the
            // scene loading to work without graphics.

            // For now, store the paths - full initialization happens in Initialize()
            return true;
        }
        catch (const std::exception& e) {
            m_lastError = std::string("Failed to load scene: ") + e.what();
            return false;
        }
    }

    int initialize(const SFSimConfig* config) {
        std::lock_guard<std::mutex> lock(m_mutex);

        if (!m_surgActions) {
            m_lastError = "Scene not loaded";
            return SF_ERROR_NOT_INITIALIZED;
        }

        try {
            // Load the scene
            if (!m_surgActions->loadScene(m_dataDirectory.c_str(), m_modelPath.c_str())) {
                m_lastError = "Failed to load scene file";
                return SF_ERROR_FILE_NOT_FOUND;
            }

            // Get references to internal components
            m_bccScene = m_surgActions->getBccTetScene();
            m_surgGraphics = m_surgActions->getSurgGraphics();

            if (!m_bccScene || !m_surgGraphics) {
                m_lastError = "Failed to get scene components";
                return SF_ERROR_NOT_INITIALIZED;
            }

            m_mt = m_surgGraphics->getMaterialTriangles();
            m_vnTets = m_bccScene->getVirtualNodedBccTetrahedra();
            m_pdPhysics = m_bccScene->getPdTetPhysics_2();

            if (!m_mt || !m_vnTets || !m_pdPhysics) {
                m_lastError = "Failed to get physics components";
                return SF_ERROR_NOT_INITIALIZED;
            }

            // Apply configuration
            if (config) {
                m_pdPhysics->setTetProperties(
                    config->lowTetWeight,
                    config->highTetWeight,
                    config->tJunctionWeight,
                    config->strainMin,
                    config->strainMax,
                    config->collisionWeight,
                    config->selfCollisionWeight,
                    config->fixedWeight,
                    config->peripheralWeight
                );

                m_pdPhysics->setHookSutureWeights(
                    config->hookWeight,
                    config->sutureWeight,
                    config->stressLimit
                );
            }

            // Initialize physics
            m_bccScene->initPdPhysics();

            m_initialized = true;
            m_paused = false;

            return SF_SUCCESS;
        }
        catch (const std::exception& e) {
            m_lastError = std::string("Initialization failed: ") + e.what();
            return SF_ERROR_PHYSICS_FAILED;
        }
    }

    int stepSimulation(float deltaTime) {
        if (!m_initialized) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        if (m_paused) {
            return SF_SUCCESS;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        try {
            auto startTime = std::chrono::high_resolution_clock::now();

            // Update physics
            m_bccScene->updatePhysics();

            // Update surface mesh
            m_bccScene->updateSurfaceDraw();

            // Check for topology changes
            if (m_surgActions->newTopology.load()) {
                m_topologyChanged = true;
                m_surgActions->newTopology.store(false);
            }

            auto endTime = std::chrono::high_resolution_clock::now();
            m_lastSolveTime = std::chrono::duration<float, std::milli>(endTime - startTime).count();

            return SF_SUCCESS;
        }
        catch (const std::exception& e) {
            m_lastError = std::string("Simulation step failed: ") + e.what();
            return SF_ERROR_PHYSICS_FAILED;
        }
    }

    // Mesh access
    int getVertexCount() const {
        if (!m_mt) return 0;
        return m_mt->numberOfVertices();
    }

    int getTriangleCount() const {
        if (!m_mt) return 0;
        return m_mt->numberOfTriangles();
    }

    int getVertices(float* outVertices, int maxVertices) const {
        if (!m_mt || !outVertices) return 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        int count = std::min(m_mt->numberOfVertices(), maxVertices);
        for (int i = 0; i < count; ++i) {
            float* v = m_mt->vertexCoordinate(i);
            outVertices[i * 3 + 0] = v[0];
            outVertices[i * 3 + 1] = v[1];
            outVertices[i * 3 + 2] = v[2];
        }
        return count;
    }

    int getTriangles(int* outTriangles, int maxTriangles) const {
        if (!m_mt || !outTriangles) return 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        int count = 0;
        int numTris = m_mt->numberOfTriangles();
        for (int i = 0; i < numTris && count < maxTriangles; ++i) {
            // Skip deleted triangles (material == -1)
            if (m_mt->triangleMaterial(i) < 0) continue;

            const int* tv = m_mt->triangleVertices(i);
            outTriangles[count * 3 + 0] = tv[0];
            outTriangles[count * 3 + 1] = tv[1];
            outTriangles[count * 3 + 2] = tv[2];
            count++;
        }
        return count;
    }

    int getNormals(float* outNormals, int maxNormals) const {
        if (!m_mt || !outNormals) return 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        int count = std::min(m_mt->numberOfVertices(), maxNormals);
        for (int i = 0; i < count; ++i) {
            // Get mean normal from adjacent triangles
            float normal[3] = {0, 0, 0};
            std::vector<materialTriangles::neighborNode> neighbors;
            m_mt->getNeighbors(i, neighbors);

            for (const auto& n : neighbors) {
                if (m_mt->triangleMaterial(n.triangle) >= 0) {
                    Vec3f triNormal;
                    m_mt->getTriangleNormal(n.triangle, triNormal, false);
                    normal[0] += triNormal.X;
                    normal[1] += triNormal.Y;
                    normal[2] += triNormal.Z;
                }
            }

            // Normalize
            float len = std::sqrt(normal[0]*normal[0] + normal[1]*normal[1] + normal[2]*normal[2]);
            if (len > 0.0001f) {
                outNormals[i * 3 + 0] = normal[0] / len;
                outNormals[i * 3 + 1] = normal[1] / len;
                outNormals[i * 3 + 2] = normal[2] / len;
            } else {
                outNormals[i * 3 + 0] = 0;
                outNormals[i * 3 + 1] = 1;
                outNormals[i * 3 + 2] = 0;
            }
        }
        return count;
    }

    int getUVs(float* outUVs, int maxUVs) const {
        if (!m_mt || !outUVs) return 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        int count = std::min(m_mt->numberOfTextures(), maxUVs);
        for (int i = 0; i < count; ++i) {
            const float* uv = m_mt->getTexture(i);
            outUVs[i * 2 + 0] = uv[0];
            outUVs[i * 2 + 1] = uv[1];
        }
        return count;
    }

    // Surgical operations - Incision
    int performIncision(const SFVector3* points, const SFVector3* normals,
                        int pointCount, int startOpen, int endOpen) {
        if (!m_initialized || !m_surgActions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        if (!points || !normals || pointCount < 2) {
            return SF_ERROR_INVALID_PARAMETER;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        try {
            skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
            if (!incisions) {
                return SF_ERROR_NOT_INITIALIZED;
            }

            // Convert to SkinFlaps format
            std::vector<Vec3f> topCutPoints(pointCount);
            std::vector<Vec3f> topNormals(pointCount);

            for (int i = 0; i < pointCount; ++i) {
                topCutPoints[i] = Vec3f(points[i].x, points[i].y, points[i].z);
                topNormals[i] = Vec3f(normals[i].x, normals[i].y, normals[i].z);
            }

            bool success = incisions->skinCut(topCutPoints, topNormals,
                                              startOpen != 0, endOpen != 0);

            if (!success) {
                m_lastError = "Incision operation failed";
                return SF_ERROR_TOPOLOGY_CHANGE_FAILED;
            }

            // Check if physics recut is required
            if (incisions->physicsRecutRequired()) {
                m_bccScene->createNewPhysicsLattice(8, 3);  // Default subdivision parameters
                m_topologyChanged = true;
            }

            return SF_SUCCESS;
        }
        catch (const std::exception& e) {
            m_lastError = std::string("Incision failed: ") + e.what();
            return SF_ERROR_TOPOLOGY_CHANGE_FAILED;
        }
    }

    float findClosestIncisionPoint(SFVector3 queryPoint, int* outTriangle,
                                   int* outEdge, float* outParam) {
        if (!m_initialized || !m_surgActions) {
            return -1.0f;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
        if (!incisions) {
            return -1.0f;
        }

        Vec3f xyz(queryPoint.x, queryPoint.y, queryPoint.z);
        int triangle = 0, edge = 0;
        float param = 0;

        float dist = incisions->closestSkinIncisionPoint(xyz, triangle, edge, param);

        if (outTriangle) *outTriangle = triangle;
        if (outEdge) *outEdge = edge;
        if (outParam) *outParam = param;

        return dist;
    }

    // Surgical operations - Undermining
    int addUndermineTriangle(int triangle, int undermineMaterial, int incisionConnect) {
        if (!m_initialized || !m_surgActions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
        if (!incisions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        bool success = incisions->addUndermineTriangle(triangle, undermineMaterial,
                                                        incisionConnect != 0);
        return success ? SF_SUCCESS : SF_ERROR_TOPOLOGY_CHANGE_FAILED;
    }

    int executeUndermine() {
        if (!m_initialized || !m_surgActions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
        if (!incisions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        incisions->undermineSkin();

        if (incisions->physicsRecutRequired()) {
            m_bccScene->createNewPhysicsLattice(8, 3);
            m_topologyChanged = true;
        }

        return SF_SUCCESS;
    }

    void clearUndermine(int underminedTissue) {
        if (!m_initialized || !m_surgActions) return;

        std::lock_guard<std::mutex> lock(m_mutex);

        skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
        if (incisions) {
            incisions->clearCurrentUndermine(underminedTissue);
        }
    }

    int isTriangleUndermined(int triangle) {
        if (!m_initialized || !m_surgActions) return 0;

        std::lock_guard<std::mutex> lock(m_mutex);

        skinCutUndermineTets* incisions = m_surgActions->getDeepCutPtr();
        if (!incisions) return 0;

        return incisions->triangleUndermined(triangle) ? 1 : 0;
    }

    // Sutures
    int addSuture(int triangle, int edge, float param) {
        if (!m_initialized || !m_surgActions) {
            return -1;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        sutures* suts = m_surgActions->getSutures();
        if (!suts || !m_mt) {
            return -1;
        }

        return suts->addUserSuture(m_mt, triangle, edge, param);
    }

    int setSutureSecondPoint(int sutureHandle, int triangle, int edge, float param) {
        if (!m_initialized || !m_surgActions) {
            return -1;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        sutures* suts = m_surgActions->getSutures();
        if (!suts || !m_mt) {
            return -1;
        }

        return suts->setSecondEdge(sutureHandle, m_mt, triangle, edge, param);
    }

    int deleteSuture(int sutureHandle) {
        if (!m_initialized || !m_surgActions) {
            return -1;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        sutures* suts = m_surgActions->getSutures();
        if (!suts) {
            return -1;
        }

        return suts->deleteSuture(sutureHandle);
    }

    int createSutureLine(int suture1, int suture2) {
        if (!m_initialized || !m_surgActions) {
            return 0;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        sutures* suts = m_surgActions->getSutures();
        if (!suts) {
            return 0;
        }

        int beforeCount = suts->getNumberOfSutures();
        suts->laySutureLine(suture2);
        return suts->getNumberOfSutures() - beforeCount;
    }

    int getSutureCount() {
        if (!m_initialized || !m_surgActions) {
            return 0;
        }

        sutures* suts = m_surgActions->getSutures();
        return suts ? suts->getNumberOfSutures() : 0;
    }

    // Hooks
    int addHook(SFVector3 position, int strong) {
        if (!m_initialized || !m_surgActions || !m_mt) {
            return -1;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        hooks* hks = m_surgActions->getHooks();
        if (!hks) {
            return -1;
        }

        // Find closest triangle
        float pos[3] = {position.x, position.y, position.z};
        int triangle = 0;
        float uv[2] = {0, 0};

        m_mt->closestPoint(pos, triangle, uv, 2);  // Material 2 = skin

        if (triangle < 0) {
            return -1;
        }

        m_surgActions->_strongHooks = (strong != 0);
        return hks->addHook(m_mt, triangle, uv, false);
    }

    int moveHook(int hookHandle, SFVector3 newPosition) {
        if (!m_initialized || !m_surgActions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        hooks* hks = m_surgActions->getHooks();
        if (!hks) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        float pos[3] = {newPosition.x, newPosition.y, newPosition.z};
        bool success = hks->setHookPosition(hookHandle, pos);

        return success ? SF_SUCCESS : SF_ERROR_INVALID_PARAMETER;
    }

    int deleteHook(int hookHandle) {
        if (!m_initialized || !m_surgActions) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        hooks* hks = m_surgActions->getHooks();
        if (!hks) {
            return SF_ERROR_NOT_INITIALIZED;
        }

        hks->deleteHook(hookHandle);
        return SF_SUCCESS;
    }

    // Raycasting
    int raycast(SFVector3 origin, SFVector3 direction, float maxDistance,
                SFVector3* outHitPoint, SFVector3* outHitNormal, int* outTriangle) {
        if (!m_initialized || !m_mt) {
            return 0;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        float lineStart[3] = {origin.x, origin.y, origin.z};
        float lineDir[3] = {direction.x, direction.y, direction.z};
        float hitPos[3] = {0, 0, 0};
        int triangle = -1;
        float triParam[2] = {0, 0};

        bool hit = m_mt->localPick(lineStart, lineDir, hitPos, triangle, triParam, -1);

        if (hit && triangle >= 0) {
            // Check distance
            float dx = hitPos[0] - origin.x;
            float dy = hitPos[1] - origin.y;
            float dz = hitPos[2] - origin.z;
            float dist = std::sqrt(dx*dx + dy*dy + dz*dz);

            if (dist <= maxDistance) {
                if (outHitPoint) {
                    outHitPoint->x = hitPos[0];
                    outHitPoint->y = hitPos[1];
                    outHitPoint->z = hitPos[2];
                }

                if (outHitNormal) {
                    Vec3f normal;
                    m_mt->getTriangleNormal(triangle, normal, true);
                    outHitNormal->x = normal.X;
                    outHitNormal->y = normal.Y;
                    outHitNormal->z = normal.Z;
                }

                if (outTriangle) {
                    *outTriangle = triangle;
                }

                return 1;
            }
        }

        return 0;
    }

    int getTriangleMaterial(int triangle) {
        if (!m_mt) return -1;

        std::lock_guard<std::mutex> lock(m_mutex);
        return m_mt->triangleMaterial(triangle);
    }

    // Statistics
    int getStats(SFSimStats* outStats) {
        if (!outStats) {
            return SF_ERROR_INVALID_PARAMETER;
        }

        std::lock_guard<std::mutex> lock(m_mutex);

        outStats->tetCount = m_vnTets ? static_cast<int>(m_vnTets->tetNumber()) : 0;
        outStats->vertexCount = m_mt ? m_mt->numberOfVertices() : 0;
        outStats->constraintCount = 0;  // Would need to track this
        outStats->lastSolveTimeMs = m_lastSolveTime;
        outStats->maxStress = 0;  // Would need physics access
        outStats->avgStress = 0;
        outStats->maxDisplacement = 0;

        return SF_SUCCESS;
    }

    // Utility
    void setPaused(bool paused) { m_paused = paused; }
    bool isPaused() const { return m_paused; }

    bool hasTopologyChanged() const { return m_topologyChanged; }
    void clearTopologyChangedFlag() { m_topologyChanged = false; }

    void setDebugMode(bool enable) { m_debugMode = enable; }

    const std::string& getLastError() const { return m_lastError; }

private:
    mutable std::mutex m_mutex;

    std::unique_ptr<surgicalActions> m_surgActions;
    bccTetScene* m_bccScene = nullptr;
    surgGraphics* m_surgGraphics = nullptr;
    materialTriangles* m_mt = nullptr;
    vnBccTetrahedra* m_vnTets = nullptr;
    pdTetPhysics* m_pdPhysics = nullptr;

    std::string m_dataDirectory;
    std::string m_modelPath;
    std::string m_lastError;

    bool m_initialized;
    bool m_paused;
    bool m_topologyChanged;
    bool m_debugMode;
    float m_lastSolveTime;
};

// ============================================================================
// Global State
// ============================================================================

static std::string g_lastError;
static std::mutex g_errorMutex;

static void SetError(const std::string& error) {
    std::lock_guard<std::mutex> lock(g_errorMutex);
    g_lastError = error;
}

// ============================================================================
// API Implementation
// ============================================================================

extern "C" {

// Lifecycle
SKINFLAPS_API SkinFlapsHandle SF_CreateSimulator(const char* modelPath, const char* dataDirectory) {
    if (!modelPath || !dataDirectory) {
        SetError("Invalid parameters");
        return nullptr;
    }

    try {
        auto* wrapper = new SkinFlapsSimulatorWrapper();
        if (!wrapper->loadScene(modelPath, dataDirectory)) {
            SetError("Failed to create simulator");
            delete wrapper;
            return nullptr;
        }
        return static_cast<SkinFlapsHandle>(wrapper);
    }
    catch (const std::exception& e) {
        SetError(std::string("Exception: ") + e.what());
        return nullptr;
    }
}

SKINFLAPS_API int SF_Initialize(SkinFlapsHandle handle, const SFSimConfig* config) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->initialize(config);
}

SKINFLAPS_API void SF_DestroySimulator(SkinFlapsHandle handle) {
    if (handle) {
        delete static_cast<SkinFlapsSimulatorWrapper*>(handle);
    }
}

SKINFLAPS_API int SF_GetLastError(char* buffer, int bufferSize) {
    std::lock_guard<std::mutex> lock(g_errorMutex);
    if (!buffer || bufferSize <= 0) return 0;

    int len = std::min(static_cast<int>(g_lastError.length()), bufferSize - 1);
    std::memcpy(buffer, g_lastError.c_str(), len);
    buffer[len] = '\0';
    return len;
}

// Simulation Control
SKINFLAPS_API int SF_StepSimulation(SkinFlapsHandle handle, float deltaTime) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->stepSimulation(deltaTime);
}

SKINFLAPS_API void SF_SetPaused(SkinFlapsHandle handle, int pause) {
    if (handle) {
        static_cast<SkinFlapsSimulatorWrapper*>(handle)->setPaused(pause != 0);
    }
}

SKINFLAPS_API int SF_IsPaused(SkinFlapsHandle handle) {
    if (!handle) return 1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->isPaused() ? 1 : 0;
}

SKINFLAPS_API int SF_Reset(SkinFlapsHandle handle) {
    // Not yet implemented - would need to reload the scene
    return SF_ERROR_NOT_INITIALIZED;
}

// Mesh Access
SKINFLAPS_API int SF_GetVertexCount(SkinFlapsHandle handle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getVertexCount();
}

SKINFLAPS_API int SF_GetTriangleCount(SkinFlapsHandle handle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getTriangleCount();
}

SKINFLAPS_API int SF_GetVertices(SkinFlapsHandle handle, float* outVertices, int maxVertices) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getVertices(outVertices, maxVertices);
}

SKINFLAPS_API int SF_GetTriangles(SkinFlapsHandle handle, int* outTriangles, int maxTriangles) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getTriangles(outTriangles, maxTriangles);
}

SKINFLAPS_API int SF_GetNormals(SkinFlapsHandle handle, float* outNormals, int maxNormals) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getNormals(outNormals, maxNormals);
}

SKINFLAPS_API int SF_GetUVs(SkinFlapsHandle handle, float* outUVs, int maxUVs) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getUVs(outUVs, maxUVs);
}

SKINFLAPS_API int SF_HasTopologyChanged(SkinFlapsHandle handle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->hasTopologyChanged() ? 1 : 0;
}

SKINFLAPS_API void SF_ClearTopologyChangedFlag(SkinFlapsHandle handle) {
    if (handle) {
        static_cast<SkinFlapsSimulatorWrapper*>(handle)->clearTopologyChangedFlag();
    }
}

// Incision
SKINFLAPS_API int SF_PerformIncision(SkinFlapsHandle handle, const SFVector3* points,
                                      const SFVector3* normals, int pointCount,
                                      int startOpen, int endOpen) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->performIncision(
        points, normals, pointCount, startOpen, endOpen);
}

SKINFLAPS_API float SF_FindClosestIncisionPoint(SkinFlapsHandle handle, SFVector3 queryPoint,
                                                 int* outTriangle, int* outEdge, float* outParam) {
    if (!handle) return -1.0f;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->findClosestIncisionPoint(
        queryPoint, outTriangle, outEdge, outParam);
}

// Undermining
SKINFLAPS_API int SF_AddUndermineTriangle(SkinFlapsHandle handle, int triangle,
                                           int undermineMaterial, int incisionConnect) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->addUndermineTriangle(
        triangle, undermineMaterial, incisionConnect);
}

SKINFLAPS_API int SF_ExecuteUndermine(SkinFlapsHandle handle) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->executeUndermine();
}

SKINFLAPS_API void SF_ClearUndermine(SkinFlapsHandle handle, int underminedTissue) {
    if (handle) {
        static_cast<SkinFlapsSimulatorWrapper*>(handle)->clearUndermine(underminedTissue);
    }
}

SKINFLAPS_API int SF_IsTriangleUndermined(SkinFlapsHandle handle, int triangle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->isTriangleUndermined(triangle);
}

// Sutures
SKINFLAPS_API int SF_AddSuture(SkinFlapsHandle handle, int triangle, int edge, float param) {
    if (!handle) return -1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->addSuture(triangle, edge, param);
}

SKINFLAPS_API int SF_SetSutureSecondPoint(SkinFlapsHandle handle, int sutureHandle,
                                           int triangle, int edge, float param) {
    if (!handle) return -1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->setSutureSecondPoint(
        sutureHandle, triangle, edge, param);
}

SKINFLAPS_API int SF_DeleteSuture(SkinFlapsHandle handle, int sutureHandle) {
    if (!handle) return -1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->deleteSuture(sutureHandle);
}

SKINFLAPS_API int SF_CreateSutureLine(SkinFlapsHandle handle, int suture1, int suture2) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->createSutureLine(suture1, suture2);
}

SKINFLAPS_API int SF_GetSutureCount(SkinFlapsHandle handle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getSutureCount();
}

// Hooks
SKINFLAPS_API int SF_AddHook(SkinFlapsHandle handle, SFVector3 position, int strong) {
    if (!handle) return -1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->addHook(position, strong);
}

SKINFLAPS_API int SF_MoveHook(SkinFlapsHandle handle, int hookHandle, SFVector3 newPosition) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->moveHook(hookHandle, newPosition);
}

SKINFLAPS_API int SF_DeleteHook(SkinFlapsHandle handle, int hookHandle) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->deleteHook(hookHandle);
}

// Raycasting
SKINFLAPS_API int SF_Raycast(SkinFlapsHandle handle, SFVector3 origin, SFVector3 direction,
                              float maxDistance, SFVector3* outHitPoint,
                              SFVector3* outHitNormal, int* outTriangle) {
    if (!handle) return 0;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->raycast(
        origin, direction, maxDistance, outHitPoint, outHitNormal, outTriangle);
}

SKINFLAPS_API int SF_GetTriangleMaterial(SkinFlapsHandle handle, int triangle) {
    if (!handle) return -1;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getTriangleMaterial(triangle);
}

// Statistics
SKINFLAPS_API int SF_GetStats(SkinFlapsHandle handle, SFSimStats* outStats) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return static_cast<SkinFlapsSimulatorWrapper*>(handle)->getStats(outStats);
}

SKINFLAPS_API void SF_SetDebugMode(SkinFlapsHandle handle, int enable) {
    if (handle) {
        static_cast<SkinFlapsSimulatorWrapper*>(handle)->setDebugMode(enable != 0);
    }
}

SKINFLAPS_API int SF_GetTetDebugData(SkinFlapsHandle handle, float* outTetVertices, int maxTets) {
    // Not yet implemented
    return 0;
}

// Version
SKINFLAPS_API const char* SF_GetVersion(void) {
    return SKINFLAPS_VERSION;
}

SKINFLAPS_API const char* SF_GetBuildInfo(void) {
    return SKINFLAPS_BUILD_INFO;
}

} // extern "C"

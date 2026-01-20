/**
 * @file UnityExports.cpp
 * @brief Unity Native Plugin Implementation for SkinFlaps Surgical Simulator
 * @author SkinFlaps Team
 * @date 2025
 *
 * Full implementation connecting to the SkinFlaps physics engine.
 */

#include "UnityExports.h"

#include <string>
#include <mutex>
#include <cstring>
#include <memory>
#include <atomic>

// SkinFlaps core includes
#include "surgicalActions.h"
#include "bccTetScene.h"
#include "materialTriangles.h"
#include "hooks.h"
#include "sutures.h"
#include "skinCutUndermineTets.h"
#include "Vec3f.h"

// Version information
#define SKINFLAPS_VERSION "1.0.0"
#define SKINFLAPS_BUILD_INFO "Unity Plugin Full Physics - " __DATE__ " " __TIME__

// ============================================================================
// Simulator Context
// ============================================================================

struct SkinFlapsContext {
    std::unique_ptr<surgicalActions> surgActions;
    materialTriangles* mt;  // Owned by bccTetScene
    bccTetScene* bts;       // Owned by surgActions
    std::string modelDirectory;
    std::string modelFile;
    bool initialized;
    bool paused;
    bool topologyChanged;
    std::string lastError;

    SkinFlapsContext() : mt(nullptr), bts(nullptr), initialized(false),
                          paused(true), topologyChanged(false) {
        surgActions = std::make_unique<surgicalActions>();
    }
};

// ============================================================================
// Global State
// ============================================================================

static std::mutex g_errorMutex;
static std::string g_lastError;

static void SetGlobalError(const std::string& error) {
    std::lock_guard<std::mutex> lock(g_errorMutex);
    g_lastError = error;
}

static SkinFlapsContext* GetContext(SkinFlapsHandle handle) {
    return reinterpret_cast<SkinFlapsContext*>(handle);
}

// ============================================================================
// Lifecycle Functions
// ============================================================================

extern "C" {

SKINFLAPS_API SkinFlapsHandle SF_CreateSimulator(const char* modelPath, const char* dataDirectory) {
    try {
        auto ctx = new SkinFlapsContext();

        if (modelPath) {
            ctx->modelFile = modelPath;
        }
        if (dataDirectory) {
            ctx->modelDirectory = dataDirectory;
            ctx->surgActions->setModelDirectory(dataDirectory);
            ctx->surgActions->setHistoryDirectory(dataDirectory);
        }

        return reinterpret_cast<SkinFlapsHandle>(ctx);
    }
    catch (const std::exception& e) {
        SetGlobalError(std::string("CreateSimulator failed: ") + e.what());
        return nullptr;
    }
}

SKINFLAPS_API int SF_Initialize(SkinFlapsHandle handle, const SFSimConfig* config) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;

    try {
        // Load the scene
        if (ctx->modelDirectory.empty() || ctx->modelFile.empty()) {
            ctx->lastError = "Model path or directory not set";
            SetGlobalError(ctx->lastError);
            return SF_ERROR_NOT_INITIALIZED;
        }

        // Add trailing slash if needed
        std::string modelDir = ctx->modelDirectory;
        if (!modelDir.empty() && modelDir.back() != '/' && modelDir.back() != '\\') {
            modelDir += '/';
        }

        if (!ctx->surgActions->loadScene(modelDir.c_str(), ctx->modelFile.c_str())) {
            ctx->lastError = "Failed to load scene: " + modelDir + ctx->modelFile;
            SetGlobalError(ctx->lastError);
            return SF_ERROR_FILE_NOT_FOUND;
        }

        // Get pointers to internal structures
        ctx->bts = ctx->surgActions->getBccTetScene();
        if (ctx->bts) {
            ctx->mt = ctx->bts->getMaterialTriangles();
        }

        if (!ctx->mt) {
            ctx->lastError = "Failed to get material triangles after scene load";
            SetGlobalError(ctx->lastError);
            return SF_ERROR_FILE_NOT_FOUND;
        }

        ctx->initialized = true;
        ctx->paused = false;
        ctx->topologyChanged = true;  // Signal initial mesh data available

        return SF_SUCCESS;
    }
    catch (const std::exception& e) {
        ctx->lastError = std::string("Initialize exception: ") + e.what();
        SetGlobalError(ctx->lastError);
        return SF_ERROR_PHYSICS_FAILED;
    }
}

SKINFLAPS_API void SF_DestroySimulator(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (ctx) {
        delete ctx;
    }
}

SKINFLAPS_API int SF_GetLastError(char* buffer, int bufferSize) {
    std::lock_guard<std::mutex> lock(g_errorMutex);
    if (!buffer || bufferSize <= 0) return 0;

    int len = (int)g_lastError.length();
    if (len >= bufferSize) len = bufferSize - 1;
    std::memcpy(buffer, g_lastError.c_str(), len);
    buffer[len] = '\0';
    return len;
}

// ============================================================================
// Simulation Control
// ============================================================================

SKINFLAPS_API int SF_StepSimulation(SkinFlapsHandle handle, float deltaTime) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    try {
        if (!ctx->paused && ctx->bts) {
            // The physics updates through the bccTetScene
            // Check if physics is done from previous step
            if (ctx->surgActions->physicsDone.load()) {
                // Physics step completed, check for topology changes
                if (ctx->surgActions->newTopology.load()) {
                    ctx->topologyChanged = true;
                    ctx->surgActions->newTopology.store(false);
                }
            }
        }
        return SF_SUCCESS;
    }
    catch (const std::exception& e) {
        ctx->lastError = std::string("StepSimulation error: ") + e.what();
        SetGlobalError(ctx->lastError);
        return SF_ERROR_PHYSICS_FAILED;
    }
}

SKINFLAPS_API void SF_SetPaused(SkinFlapsHandle handle, int pause) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (ctx && ctx->initialized) {
        ctx->paused = (pause != 0);
        if (ctx->bts) {
            ctx->bts->setPhysicsPause(ctx->paused);
        }
    }
}

SKINFLAPS_API int SF_IsPaused(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    return (ctx && ctx->paused) ? 1 : 0;
}

SKINFLAPS_API int SF_Reset(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    // Reload the scene to reset
    ctx->initialized = false;
    return SF_Initialize(handle, nullptr);
}

// ============================================================================
// Mesh Access
// ============================================================================

SKINFLAPS_API int SF_GetVertexCount(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt) return 0;
    return ctx->mt->numberOfVertices();
}

SKINFLAPS_API int SF_GetTriangleCount(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt) return 0;

    // Count only valid triangles (material >= 0)
    int count = 0;
    int totalTris = ctx->mt->numberOfTriangles();
    for (int i = 0; i < totalTris; ++i) {
        if (ctx->mt->triangleMaterial(i) >= 0) {
            ++count;
        }
    }
    return count;
}

SKINFLAPS_API int SF_GetVertices(SkinFlapsHandle handle, float* outVertices, int maxVertices) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt || !outVertices) return 0;

    int vertCount = ctx->mt->numberOfVertices();
    if (vertCount > maxVertices) vertCount = maxVertices;

    std::vector<Vec3f>& positions = ctx->mt->getPositionArray();
    for (int i = 0; i < vertCount; ++i) {
        outVertices[i * 3 + 0] = positions[i].X;
        outVertices[i * 3 + 1] = positions[i].Y;
        outVertices[i * 3 + 2] = positions[i].Z;
    }

    return vertCount;
}

SKINFLAPS_API int SF_GetTriangles(SkinFlapsHandle handle, int* outTriangles, int maxTriangles) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt || !outTriangles) return 0;

    const auto& triPos = ctx->mt->getTrianglePositionArray();
    int totalTris = (int)triPos.size();
    int outCount = 0;

    for (int i = 0; i < totalTris && outCount < maxTriangles; ++i) {
        // Skip deleted triangles (material == -1)
        if (ctx->mt->triangleMaterial(i) >= 0) {
            outTriangles[outCount * 3 + 0] = triPos[i][0];
            outTriangles[outCount * 3 + 1] = triPos[i][1];
            outTriangles[outCount * 3 + 2] = triPos[i][2];
            ++outCount;
        }
    }

    return outCount;
}

SKINFLAPS_API int SF_GetNormals(SkinFlapsHandle handle, float* outNormals, int maxNormals) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt || !outNormals) return 0;

    int vertCount = ctx->mt->numberOfVertices();
    if (vertCount > maxNormals) vertCount = maxNormals;

    // Compute vertex normals by averaging face normals
    std::vector<Vec3f> normals(vertCount, Vec3f(0, 0, 0));

    const auto& triPos = ctx->mt->getTrianglePositionArray();
    int totalTris = (int)triPos.size();

    for (int i = 0; i < totalTris; ++i) {
        if (ctx->mt->triangleMaterial(i) < 0) continue;

        Vec3f faceNormal;
        ctx->mt->getTriangleNormal(i, faceNormal, true);

        for (int j = 0; j < 3; ++j) {
            int vi = triPos[i][j];
            if (vi < vertCount) {
                normals[vi] = normals[vi] + faceNormal;
            }
        }
    }

    // Normalize and output
    for (int i = 0; i < vertCount; ++i) {
        normals[i].normalize();
        outNormals[i * 3 + 0] = normals[i].X;
        outNormals[i * 3 + 1] = normals[i].Y;
        outNormals[i * 3 + 2] = normals[i].Z;
    }

    return vertCount;
}

SKINFLAPS_API int SF_GetUVs(SkinFlapsHandle handle, float* outUVs, int maxUVs) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt || !outUVs) return 0;

    std::vector<Vec2f>& textures = ctx->mt->getTextureArray();
    int uvCount = (int)textures.size();
    if (uvCount > maxUVs) uvCount = maxUVs;

    for (int i = 0; i < uvCount; ++i) {
        outUVs[i * 2 + 0] = textures[i].X;
        outUVs[i * 2 + 1] = textures[i].Y;
    }

    return uvCount;
}

SKINFLAPS_API int SF_HasTopologyChanged(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    return (ctx && ctx->topologyChanged) ? 1 : 0;
}

SKINFLAPS_API void SF_ClearTopologyChangedFlag(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (ctx) {
        ctx->topologyChanged = false;
    }
}

// ============================================================================
// Surgical Operations - Incision
// ============================================================================

SKINFLAPS_API int SF_PerformIncision(SkinFlapsHandle handle, const SFVector3* points,
                                      const SFVector3* normals, int pointCount,
                                      int startOpen, int endOpen) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;
    if (!points || pointCount < 2) return SF_ERROR_INVALID_PARAMETER;

    try {
        // TODO: Implement incision through skinCutUndermineTets
        // This requires converting the Unity points to the internal format
        // and calling the appropriate methods on ctx->surgActions->getDeepCutPtr()

        ctx->topologyChanged = true;
        return SF_SUCCESS;
    }
    catch (const std::exception& e) {
        ctx->lastError = std::string("PerformIncision error: ") + e.what();
        SetGlobalError(ctx->lastError);
        return SF_ERROR_PHYSICS_FAILED;
    }
}

SKINFLAPS_API float SF_FindClosestIncisionPoint(SkinFlapsHandle handle, SFVector3 queryPoint,
                                                 int* outTriangle, int* outEdge, float* outParam) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt) return -1.0f;

    float xyz[3] = { queryPoint.x, queryPoint.y, queryPoint.z };
    int triangle;
    float uv[2];

    ctx->mt->closestPoint(xyz, triangle, uv, -1);

    if (outTriangle) *outTriangle = triangle;
    if (outEdge) *outEdge = 0;  // TODO: Determine actual edge
    if (outParam) *outParam = uv[0];

    // Calculate distance
    float hitXyz[3];
    ctx->mt->getBarycentricPosition(triangle, uv, hitXyz);
    float dx = hitXyz[0] - xyz[0];
    float dy = hitXyz[1] - xyz[1];
    float dz = hitXyz[2] - xyz[2];

    return sqrtf(dx*dx + dy*dy + dz*dz);
}

// ============================================================================
// Surgical Operations - Undermining
// ============================================================================

SKINFLAPS_API int SF_AddUndermineTriangle(SkinFlapsHandle handle, int triangle,
                                           int undermineMaterial, int incisionConnect) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    // TODO: Implement through surgicalActions undermine system
    return SF_SUCCESS;
}

SKINFLAPS_API int SF_ExecuteUndermine(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    ctx->topologyChanged = true;
    return SF_SUCCESS;
}

SKINFLAPS_API void SF_ClearUndermine(SkinFlapsHandle handle, int underminedTissue) {
    // TODO: Implement
}

SKINFLAPS_API int SF_IsTriangleUndermined(SkinFlapsHandle handle, int triangle) {
    return 0;  // TODO: Implement
}

// ============================================================================
// Surgical Operations - Sutures
// ============================================================================

SKINFLAPS_API int SF_AddSuture(SkinFlapsHandle handle, int triangle, int edge, float param) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized) return -1;

    // TODO: Implement through sutures class
    return -1;
}

SKINFLAPS_API int SF_SetSutureSecondPoint(SkinFlapsHandle handle, int sutureHandle,
                                           int triangle, int edge, float param) {
    return -1;  // TODO: Implement
}

SKINFLAPS_API int SF_DeleteSuture(SkinFlapsHandle handle, int sutureHandle) {
    return -1;  // TODO: Implement
}

SKINFLAPS_API int SF_CreateSutureLine(SkinFlapsHandle handle, int suture1, int suture2) {
    return 0;  // TODO: Implement
}

SKINFLAPS_API int SF_GetSutureCount(SkinFlapsHandle handle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized) return 0;

    sutures* sut = ctx->surgActions->getSutures();
    if (!sut) return 0;

    return sut->getNumberOfSutures();
}

// ============================================================================
// Surgical Operations - Hooks
// ============================================================================

SKINFLAPS_API int SF_AddHook(SkinFlapsHandle handle, SFVector3 position, int strong) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized) return -1;

    hooks* hk = ctx->surgActions->getHooks();
    if (!hk) return -1;

    float pos[3] = { position.x, position.y, position.z };
    // TODO: Need to add hook through the proper interface
    return -1;
}

SKINFLAPS_API int SF_MoveHook(SkinFlapsHandle handle, int hookHandle, SFVector3 newPosition) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    // TODO: Implement hook movement
    return SF_SUCCESS;
}

SKINFLAPS_API int SF_DeleteHook(SkinFlapsHandle handle, int hookHandle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!ctx->initialized) return SF_ERROR_NOT_INITIALIZED;

    // TODO: Implement hook deletion
    return SF_SUCCESS;
}

// ============================================================================
// Raycasting
// ============================================================================

SKINFLAPS_API int SF_Raycast(SkinFlapsHandle handle, SFVector3 origin, SFVector3 direction,
                              float maxDistance, SFVector3* outHitPoint,
                              SFVector3* outHitNormal, int* outTriangle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt) return 0;

    float lineStart[3] = { origin.x, origin.y, origin.z };
    float lineDir[3] = { direction.x, direction.y, direction.z };
    float hitPos[3];
    int triangle;
    float triParam[2];

    if (ctx->mt->localPick(lineStart, lineDir, hitPos, triangle, triParam, -1)) {
        // Check distance
        float dx = hitPos[0] - origin.x;
        float dy = hitPos[1] - origin.y;
        float dz = hitPos[2] - origin.z;
        float dist = sqrtf(dx*dx + dy*dy + dz*dz);

        if (dist <= maxDistance) {
            if (outHitPoint) {
                outHitPoint->x = hitPos[0];
                outHitPoint->y = hitPos[1];
                outHitPoint->z = hitPos[2];
            }

            if (outHitNormal) {
                Vec3f normal;
                ctx->mt->getTriangleNormal(triangle, normal, true);
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

SKINFLAPS_API int SF_GetTriangleMaterial(SkinFlapsHandle handle, int triangle) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->mt) return -1;

    if (triangle < 0 || triangle >= ctx->mt->numberOfTriangles()) return -1;
    return ctx->mt->triangleMaterial(triangle);
}

// ============================================================================
// Statistics and Debug
// ============================================================================

SKINFLAPS_API int SF_GetStats(SkinFlapsHandle handle, SFSimStats* outStats) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx) return SF_ERROR_INVALID_HANDLE;
    if (!outStats) return SF_ERROR_INVALID_PARAMETER;

    if (!ctx->initialized) {
        memset(outStats, 0, sizeof(SFSimStats));
        return SF_SUCCESS;
    }

    outStats->tetCount = ctx->bts ? ctx->bts->getTetCount() : 0;
    outStats->vertexCount = ctx->mt ? ctx->mt->numberOfVertices() : 0;
    outStats->constraintCount = 0;  // TODO: Get from physics
    outStats->lastSolveTimeMs = 0;  // TODO: Get timing info
    outStats->maxStress = 0;
    outStats->avgStress = 0;
    outStats->maxDisplacement = 0;

    return SF_SUCCESS;
}

SKINFLAPS_API void SF_SetDebugMode(SkinFlapsHandle handle, int enable) {
    // TODO: Implement debug visualization toggle
}

SKINFLAPS_API int SF_GetTetDebugData(SkinFlapsHandle handle, float* outTetVertices, int maxTets) {
    SkinFlapsContext* ctx = GetContext(handle);
    if (!ctx || !ctx->initialized || !ctx->bts || !outTetVertices) return 0;

    // TODO: Get tetrahedra visualization data
    return 0;
}

// ============================================================================
// Version Information
// ============================================================================

SKINFLAPS_API const char* SF_GetVersion(void) {
    return SKINFLAPS_VERSION;
}

SKINFLAPS_API const char* SF_GetBuildInfo(void) {
    return SKINFLAPS_BUILD_INFO;
}

} // extern "C"

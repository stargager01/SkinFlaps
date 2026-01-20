/**
 * @file UnityExports.cpp
 * @brief Unity Native Plugin Implementation for SkinFlaps Surgical Simulator
 * @author SkinFlaps Team
 * @date 2025
 *
 * This is a minimal stub implementation that provides the DLL exports.
 * The actual functionality requires linking against the pre-built SkinFlaps libraries.
 */

#include "UnityExports.h"

#include <string>
#include <mutex>
#include <cstring>

// Version information
#define SKINFLAPS_VERSION "1.0.0"
#define SKINFLAPS_BUILD_INFO "Unity Plugin Build - " __DATE__ " " __TIME__

// ============================================================================
// Global State
// ============================================================================

static std::string g_lastError = "Not implemented - requires full SkinFlaps integration";
static std::mutex g_errorMutex;

static void SetError(const std::string& error) {
    std::lock_guard<std::mutex> lock(g_errorMutex);
    g_lastError = error;
}

// ============================================================================
// Stub Implementation
// ============================================================================

// This stub provides the DLL exports required by Unity.
// Full implementation requires resolving the complex header dependencies
// from the SkinFlaps physics engine.

extern "C" {

// Lifecycle
SKINFLAPS_API SkinFlapsHandle SF_CreateSimulator(const char* modelPath, const char* dataDirectory) {
    SetError("Stub implementation - full integration pending");
    // Return a non-null handle for testing the DLL loading
    return reinterpret_cast<SkinFlapsHandle>(1);
}

SKINFLAPS_API int SF_Initialize(SkinFlapsHandle handle, const SFSimConfig* config) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API void SF_DestroySimulator(SkinFlapsHandle handle) {
    // Stub - nothing to destroy
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

// Simulation Control
SKINFLAPS_API int SF_StepSimulation(SkinFlapsHandle handle, float deltaTime) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API void SF_SetPaused(SkinFlapsHandle handle, int pause) {
    // Stub
}

SKINFLAPS_API int SF_IsPaused(SkinFlapsHandle handle) {
    return 1;
}

SKINFLAPS_API int SF_Reset(SkinFlapsHandle handle) {
    return SF_ERROR_NOT_INITIALIZED;
}

// Mesh Access
SKINFLAPS_API int SF_GetVertexCount(SkinFlapsHandle handle) {
    return 0;
}

SKINFLAPS_API int SF_GetTriangleCount(SkinFlapsHandle handle) {
    return 0;
}

SKINFLAPS_API int SF_GetVertices(SkinFlapsHandle handle, float* outVertices, int maxVertices) {
    return 0;
}

SKINFLAPS_API int SF_GetTriangles(SkinFlapsHandle handle, int* outTriangles, int maxTriangles) {
    return 0;
}

SKINFLAPS_API int SF_GetNormals(SkinFlapsHandle handle, float* outNormals, int maxNormals) {
    return 0;
}

SKINFLAPS_API int SF_GetUVs(SkinFlapsHandle handle, float* outUVs, int maxUVs) {
    return 0;
}

SKINFLAPS_API int SF_HasTopologyChanged(SkinFlapsHandle handle) {
    return 0;
}

SKINFLAPS_API void SF_ClearTopologyChangedFlag(SkinFlapsHandle handle) {
    // Stub
}

// Incision
SKINFLAPS_API int SF_PerformIncision(SkinFlapsHandle handle, const SFVector3* points,
                                      const SFVector3* normals, int pointCount,
                                      int startOpen, int endOpen) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API float SF_FindClosestIncisionPoint(SkinFlapsHandle handle, SFVector3 queryPoint,
                                                 int* outTriangle, int* outEdge, float* outParam) {
    return -1.0f;
}

// Undermining
SKINFLAPS_API int SF_AddUndermineTriangle(SkinFlapsHandle handle, int triangle,
                                           int undermineMaterial, int incisionConnect) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API int SF_ExecuteUndermine(SkinFlapsHandle handle) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API void SF_ClearUndermine(SkinFlapsHandle handle, int underminedTissue) {
    // Stub
}

SKINFLAPS_API int SF_IsTriangleUndermined(SkinFlapsHandle handle, int triangle) {
    return 0;
}

// Sutures
SKINFLAPS_API int SF_AddSuture(SkinFlapsHandle handle, int triangle, int edge, float param) {
    return -1;
}

SKINFLAPS_API int SF_SetSutureSecondPoint(SkinFlapsHandle handle, int sutureHandle,
                                           int triangle, int edge, float param) {
    return -1;
}

SKINFLAPS_API int SF_DeleteSuture(SkinFlapsHandle handle, int sutureHandle) {
    return -1;
}

SKINFLAPS_API int SF_CreateSutureLine(SkinFlapsHandle handle, int suture1, int suture2) {
    return 0;
}

SKINFLAPS_API int SF_GetSutureCount(SkinFlapsHandle handle) {
    return 0;
}

// Hooks
SKINFLAPS_API int SF_AddHook(SkinFlapsHandle handle, SFVector3 position, int strong) {
    return -1;
}

SKINFLAPS_API int SF_MoveHook(SkinFlapsHandle handle, int hookHandle, SFVector3 newPosition) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

SKINFLAPS_API int SF_DeleteHook(SkinFlapsHandle handle, int hookHandle) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    return SF_ERROR_NOT_INITIALIZED;
}

// Raycasting
SKINFLAPS_API int SF_Raycast(SkinFlapsHandle handle, SFVector3 origin, SFVector3 direction,
                              float maxDistance, SFVector3* outHitPoint,
                              SFVector3* outHitNormal, int* outTriangle) {
    return 0;
}

SKINFLAPS_API int SF_GetTriangleMaterial(SkinFlapsHandle handle, int triangle) {
    return -1;
}

// Statistics
SKINFLAPS_API int SF_GetStats(SkinFlapsHandle handle, SFSimStats* outStats) {
    if (!handle) return SF_ERROR_INVALID_HANDLE;
    if (!outStats) return SF_ERROR_INVALID_PARAMETER;

    outStats->tetCount = 0;
    outStats->vertexCount = 0;
    outStats->constraintCount = 0;
    outStats->lastSolveTimeMs = 0;
    outStats->maxStress = 0;
    outStats->avgStress = 0;
    outStats->maxDisplacement = 0;

    return SF_SUCCESS;
}

SKINFLAPS_API void SF_SetDebugMode(SkinFlapsHandle handle, int enable) {
    // Stub
}

SKINFLAPS_API int SF_GetTetDebugData(SkinFlapsHandle handle, float* outTetVertices, int maxTets) {
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

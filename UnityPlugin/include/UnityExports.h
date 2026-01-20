/**
 * @file UnityExports.h
 * @brief Unity Native Plugin Interface for SkinFlaps Surgical Simulator
 * @author SkinFlaps Team
 * @date 2025
 *
 * This header defines the C API for interfacing SkinFlaps physics simulation
 * with Unity3D via P/Invoke. The API provides access to:
 * - Simulation lifecycle management
 * - Physics stepping
 * - Mesh data extraction
 * - Surgical operations (incision, suture, undermine)
 * - Constraint management (hooks)
 */

#ifndef __SKINFLAPS_UNITY_EXPORTS_H__
#define __SKINFLAPS_UNITY_EXPORTS_H__

#ifdef _WIN32
    #ifdef SKINFLAPS_DLL_EXPORT
        #define SKINFLAPS_API __declspec(dllexport)
    #else
        #define SKINFLAPS_API __declspec(dllimport)
    #endif
#else
    #define SKINFLAPS_API __attribute__((visibility("default")))
#endif

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Type Definitions
// ============================================================================

/// Opaque handle to a SkinFlaps simulator instance
typedef void* SkinFlapsHandle;

/// 3D vector structure for position/direction data
typedef struct {
    float x, y, z;
} SFVector3;

/// Simulation configuration parameters
typedef struct {
    float lowTetWeight;
    float highTetWeight;
    float tJunctionWeight;
    float strainMin;
    float strainMax;
    float collisionWeight;
    float selfCollisionWeight;
    float fixedWeight;
    float peripheralWeight;
    float hookWeight;
    float sutureWeight;
    float stressLimit;
} SFSimConfig;

/// Mesh data output structure
typedef struct {
    float* vertices;           // [vertexCount * 3] xyz positions
    int* triangles;            // [triangleCount * 3] vertex indices
    float* normals;            // [vertexCount * 3] normal vectors (optional)
    float* uvs;                // [vertexCount * 2] texture coordinates (optional)
    int vertexCount;
    int triangleCount;
} SFMeshData;

/// Incision parameters
typedef struct {
    SFVector3 startPoint;
    SFVector3 endPoint;
    SFVector3 startNormal;
    SFVector3 endNormal;
    int startOpen;             // 1 = open end, 0 = closed
    int endOpen;
} SFIncisionParams;

/// Suture attachment point
typedef struct {
    int triangle;
    int edge;
    float param;               // 0.0-1.0 parameter along edge
} SFSuturePoint;

/// Simulation statistics for monitoring
typedef struct {
    float maxStress;
    float avgStress;
    float maxDisplacement;
    int tetCount;
    int vertexCount;
    int constraintCount;
    float lastSolveTimeMs;
} SFSimStats;

/// Error codes
typedef enum {
    SF_SUCCESS = 0,
    SF_ERROR_INVALID_HANDLE = -1,
    SF_ERROR_NOT_INITIALIZED = -2,
    SF_ERROR_INVALID_PARAMETER = -3,
    SF_ERROR_FILE_NOT_FOUND = -4,
    SF_ERROR_PHYSICS_FAILED = -5,
    SF_ERROR_TOPOLOGY_CHANGE_FAILED = -6,
    SF_ERROR_OUT_OF_MEMORY = -7,
    SF_ERROR_UNKNOWN = -99
} SFErrorCode;

// ============================================================================
// Simulator Lifecycle
// ============================================================================

/**
 * Create a new SkinFlaps simulator instance
 * @param modelPath Path to the .smd model file
 * @param dataDirectory Path to the data directory containing model assets
 * @return Handle to the simulator, or NULL on failure
 */
SKINFLAPS_API SkinFlapsHandle SF_CreateSimulator(const char* modelPath, const char* dataDirectory);

/**
 * Initialize the simulator with configuration parameters
 * @param handle Simulator handle
 * @param config Pointer to configuration structure
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_Initialize(SkinFlapsHandle handle, const SFSimConfig* config);

/**
 * Destroy a simulator instance and free all resources
 * @param handle Simulator handle
 */
SKINFLAPS_API void SF_DestroySimulator(SkinFlapsHandle handle);

/**
 * Get the last error message for debugging
 * @param buffer Output buffer for error message
 * @param bufferSize Size of the buffer
 * @return Length of error message, or 0 if no error
 */
SKINFLAPS_API int SF_GetLastError(char* buffer, int bufferSize);

// ============================================================================
// Simulation Control
// ============================================================================

/**
 * Step the physics simulation forward
 * @param handle Simulator handle
 * @param deltaTime Time step in seconds (typically 1/60)
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_StepSimulation(SkinFlapsHandle handle, float deltaTime);

/**
 * Pause/resume physics simulation
 * @param handle Simulator handle
 * @param pause 1 to pause, 0 to resume
 */
SKINFLAPS_API void SF_SetPaused(SkinFlapsHandle handle, int pause);

/**
 * Check if physics simulation is paused
 * @param handle Simulator handle
 * @return 1 if paused, 0 if running
 */
SKINFLAPS_API int SF_IsPaused(SkinFlapsHandle handle);

/**
 * Reset simulation to initial state
 * @param handle Simulator handle
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_Reset(SkinFlapsHandle handle);

// ============================================================================
// Mesh Data Access
// ============================================================================

/**
 * Get current vertex count
 * @param handle Simulator handle
 * @return Number of vertices
 */
SKINFLAPS_API int SF_GetVertexCount(SkinFlapsHandle handle);

/**
 * Get current triangle count
 * @param handle Simulator handle
 * @return Number of triangles
 */
SKINFLAPS_API int SF_GetTriangleCount(SkinFlapsHandle handle);

/**
 * Copy vertex positions to output buffer
 * @param handle Simulator handle
 * @param outVertices Output buffer [vertexCount * 3]
 * @param maxVertices Maximum vertices to copy
 * @return Number of vertices copied
 */
SKINFLAPS_API int SF_GetVertices(SkinFlapsHandle handle, float* outVertices, int maxVertices);

/**
 * Copy triangle indices to output buffer
 * @param handle Simulator handle
 * @param outTriangles Output buffer [triangleCount * 3]
 * @param maxTriangles Maximum triangles to copy
 * @return Number of triangles copied
 */
SKINFLAPS_API int SF_GetTriangles(SkinFlapsHandle handle, int* outTriangles, int maxTriangles);

/**
 * Copy vertex normals to output buffer
 * @param handle Simulator handle
 * @param outNormals Output buffer [vertexCount * 3]
 * @param maxNormals Maximum normals to copy
 * @return Number of normals copied
 */
SKINFLAPS_API int SF_GetNormals(SkinFlapsHandle handle, float* outNormals, int maxNormals);

/**
 * Copy texture coordinates to output buffer
 * @param handle Simulator handle
 * @param outUVs Output buffer [vertexCount * 2]
 * @param maxUVs Maximum UVs to copy
 * @return Number of UVs copied
 */
SKINFLAPS_API int SF_GetUVs(SkinFlapsHandle handle, float* outUVs, int maxUVs);

/**
 * Check if mesh topology has changed since last query
 * @param handle Simulator handle
 * @return 1 if topology changed, 0 if unchanged
 */
SKINFLAPS_API int SF_HasTopologyChanged(SkinFlapsHandle handle);

/**
 * Clear the topology changed flag
 * @param handle Simulator handle
 */
SKINFLAPS_API void SF_ClearTopologyChangedFlag(SkinFlapsHandle handle);

// ============================================================================
// Surgical Operations - Incision
// ============================================================================

/**
 * Perform a skin incision along a path
 * @param handle Simulator handle
 * @param points Array of incision points
 * @param normals Array of surface normals at each point
 * @param pointCount Number of points in the path
 * @param startOpen 1 if start is open, 0 if closed
 * @param endOpen 1 if end is open, 0 if closed
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_PerformIncision(
    SkinFlapsHandle handle,
    const SFVector3* points,
    const SFVector3* normals,
    int pointCount,
    int startOpen,
    int endOpen
);

/**
 * Find the closest point on an existing incision edge
 * @param handle Simulator handle
 * @param queryPoint Point to search from
 * @param outTriangle Output: triangle index
 * @param outEdge Output: edge index (0-2)
 * @param outParam Output: parameter along edge (0-1)
 * @return Distance to closest point, or -1 on error
 */
SKINFLAPS_API float SF_FindClosestIncisionPoint(
    SkinFlapsHandle handle,
    SFVector3 queryPoint,
    int* outTriangle,
    int* outEdge,
    float* outParam
);

// ============================================================================
// Surgical Operations - Undermining
// ============================================================================

/**
 * Add a triangle to the current undermine selection
 * @param handle Simulator handle
 * @param triangle Triangle index
 * @param undermineMaterial Material ID for undermining (4, 5, or 6)
 * @param incisionConnect 1 to connect to incision, 0 otherwise
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_AddUndermineTriangle(
    SkinFlapsHandle handle,
    int triangle,
    int undermineMaterial,
    int incisionConnect
);

/**
 * Execute the undermine operation on selected triangles
 * @param handle Simulator handle
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_ExecuteUndermine(SkinFlapsHandle handle);

/**
 * Clear the current undermine selection
 * @param handle Simulator handle
 * @param underminedTissue Material ID to clear
 */
SKINFLAPS_API void SF_ClearUndermine(SkinFlapsHandle handle, int underminedTissue);

/**
 * Check if a triangle has been undermined
 * @param handle Simulator handle
 * @param triangle Triangle index
 * @return 1 if undermined, 0 if not
 */
SKINFLAPS_API int SF_IsTriangleUndermined(SkinFlapsHandle handle, int triangle);

// ============================================================================
// Surgical Operations - Sutures
// ============================================================================

/**
 * Add a suture at the first attachment point
 * @param handle Simulator handle
 * @param triangle Triangle index
 * @param edge Edge index (0-2)
 * @param param Parameter along edge (0-1)
 * @return Suture handle, or -1 on error
 */
SKINFLAPS_API int SF_AddSuture(
    SkinFlapsHandle handle,
    int triangle,
    int edge,
    float param
);

/**
 * Set the second attachment point for a suture
 * @param handle Simulator handle
 * @param sutureHandle Handle from SF_AddSuture
 * @param triangle Triangle index
 * @param edge Edge index (0-2)
 * @param param Parameter along edge (0-1)
 * @return 0 = normal, 1 = one-sided, 2 = same tet, 3 = different bodies
 */
SKINFLAPS_API int SF_SetSutureSecondPoint(
    SkinFlapsHandle handle,
    int sutureHandle,
    int triangle,
    int edge,
    float param
);

/**
 * Delete a suture
 * @param handle Simulator handle
 * @param sutureHandle Suture handle
 * @return 0 if user suture, or linked suture number
 */
SKINFLAPS_API int SF_DeleteSuture(SkinFlapsHandle handle, int sutureHandle);

/**
 * Create a line of sutures between two existing sutures
 * @param handle Simulator handle
 * @param suture1 First suture handle
 * @param suture2 Second suture handle
 * @return Number of sutures created
 */
SKINFLAPS_API int SF_CreateSutureLine(
    SkinFlapsHandle handle,
    int suture1,
    int suture2
);

/**
 * Get the number of active sutures
 * @param handle Simulator handle
 * @return Number of sutures
 */
SKINFLAPS_API int SF_GetSutureCount(SkinFlapsHandle handle);

// ============================================================================
// Constraints - Hooks (Tissue Manipulation)
// ============================================================================

/**
 * Add a hook constraint at a position
 * @param handle Simulator handle
 * @param position World position for the hook
 * @param strong 1 for strong hook, 0 for normal
 * @return Hook handle, or -1 on error
 */
SKINFLAPS_API int SF_AddHook(
    SkinFlapsHandle handle,
    SFVector3 position,
    int strong
);

/**
 * Move an existing hook to a new position
 * @param handle Simulator handle
 * @param hookHandle Hook handle
 * @param newPosition New world position
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_MoveHook(
    SkinFlapsHandle handle,
    int hookHandle,
    SFVector3 newPosition
);

/**
 * Delete a hook constraint
 * @param handle Simulator handle
 * @param hookHandle Hook handle
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_DeleteHook(SkinFlapsHandle handle, int hookHandle);

// ============================================================================
// Raycasting and Picking
// ============================================================================

/**
 * Raycast against the simulation mesh
 * @param handle Simulator handle
 * @param origin Ray origin
 * @param direction Ray direction (normalized)
 * @param maxDistance Maximum ray distance
 * @param outHitPoint Output: hit position
 * @param outHitNormal Output: hit normal
 * @param outTriangle Output: hit triangle index
 * @return 1 if hit, 0 if miss
 */
SKINFLAPS_API int SF_Raycast(
    SkinFlapsHandle handle,
    SFVector3 origin,
    SFVector3 direction,
    float maxDistance,
    SFVector3* outHitPoint,
    SFVector3* outHitNormal,
    int* outTriangle
);

/**
 * Get the material ID of a triangle
 * @param handle Simulator handle
 * @param triangle Triangle index
 * @return Material ID (2=skin, 3=incision wall, 4-6=deep surfaces)
 */
SKINFLAPS_API int SF_GetTriangleMaterial(SkinFlapsHandle handle, int triangle);

// ============================================================================
// Statistics and Debugging
// ============================================================================

/**
 * Get simulation statistics
 * @param handle Simulator handle
 * @param outStats Output statistics structure
 * @return SF_SUCCESS or error code
 */
SKINFLAPS_API int SF_GetStats(SkinFlapsHandle handle, SFSimStats* outStats);

/**
 * Enable/disable debug visualization data
 * @param handle Simulator handle
 * @param enable 1 to enable, 0 to disable
 */
SKINFLAPS_API void SF_SetDebugMode(SkinFlapsHandle handle, int enable);

/**
 * Get tetrahedra data for debug visualization
 * @param handle Simulator handle
 * @param outTetVertices Output: tet vertex positions [tetCount * 4 * 3]
 * @param maxTets Maximum tets to copy
 * @return Number of tets copied
 */
SKINFLAPS_API int SF_GetTetDebugData(
    SkinFlapsHandle handle,
    float* outTetVertices,
    int maxTets
);

// ============================================================================
// Version Information
// ============================================================================

/**
 * Get the library version
 * @return Version string
 */
SKINFLAPS_API const char* SF_GetVersion(void);

/**
 * Get build information
 * @return Build info string
 */
SKINFLAPS_API const char* SF_GetBuildInfo(void);

#ifdef __cplusplus
}
#endif

#endif // __SKINFLAPS_UNITY_EXPORTS_H__

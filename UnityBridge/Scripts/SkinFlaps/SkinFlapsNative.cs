/**
 * SkinFlapsNative.cs
 * P/Invoke wrapper for SkinFlaps native plugin
 *
 * This class provides a thin wrapper around the native SkinFlapsCore DLL,
 * marshaling data between C# and the C++ physics simulation.
 */

using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace SkinFlaps
{
    /// <summary>
    /// 3D vector structure matching the native SFVector3
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct SFVector3
    {
        public float x, y, z;

        public SFVector3(float x, float y, float z)
        {
            this.x = x;
            this.y = y;
            this.z = z;
        }

        public SFVector3(Vector3 v)
        {
            x = v.x;
            y = v.y;
            z = v.z;
        }

        public Vector3 ToUnityVector3()
        {
            return new Vector3(x, y, z);
        }

        public static implicit operator Vector3(SFVector3 v) => new Vector3(v.x, v.y, v.z);
        public static implicit operator SFVector3(Vector3 v) => new SFVector3(v.x, v.y, v.z);
    }

    /// <summary>
    /// Simulation configuration parameters
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct SFSimConfig
    {
        public float lowTetWeight;
        public float highTetWeight;
        public float tJunctionWeight;
        public float strainMin;
        public float strainMax;
        public float collisionWeight;
        public float selfCollisionWeight;
        public float fixedWeight;
        public float peripheralWeight;
        public float hookWeight;
        public float sutureWeight;
        public float stressLimit;

        /// <summary>
        /// Creates a default configuration suitable for soft tissue simulation
        /// </summary>
        public static SFSimConfig Default => new SFSimConfig
        {
            lowTetWeight = 0.1f,
            highTetWeight = 1.0f,
            tJunctionWeight = 100.0f,
            strainMin = 0.8f,
            strainMax = 1.2f,
            collisionWeight = 1000.0f,
            selfCollisionWeight = 100.0f,
            fixedWeight = 10000.0f,
            peripheralWeight = 1000.0f,
            hookWeight = 500.0f,
            sutureWeight = 1000.0f,
            stressLimit = float.MaxValue
        };
    }

    /// <summary>
    /// Simulation statistics for monitoring performance
    /// </summary>
    [StructLayout(LayoutKind.Sequential)]
    public struct SFSimStats
    {
        public float maxStress;
        public float avgStress;
        public float maxDisplacement;
        public int tetCount;
        public int vertexCount;
        public int constraintCount;
        public float lastSolveTimeMs;
    }

    /// <summary>
    /// Error codes returned by native functions
    /// </summary>
    public enum SFErrorCode
    {
        Success = 0,
        InvalidHandle = -1,
        NotInitialized = -2,
        InvalidParameter = -3,
        FileNotFound = -4,
        PhysicsFailed = -5,
        TopologyChangeFailed = -6,
        OutOfMemory = -7,
        Unknown = -99
    }

    /// <summary>
    /// Static class containing P/Invoke declarations for the native plugin
    /// </summary>
    public static class SkinFlapsNative
    {
#if UNITY_IOS && !UNITY_EDITOR
        private const string DLL_NAME = "__Internal";
#else
        private const string DLL_NAME = "SkinFlapsCore";
#endif

        // ====================================================================
        // Simulator Lifecycle
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern IntPtr SF_CreateSimulator(
            [MarshalAs(UnmanagedType.LPStr)] string modelPath,
            [MarshalAs(UnmanagedType.LPStr)] string dataDirectory);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_Initialize(IntPtr handle, ref SFSimConfig config);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern void SF_DestroySimulator(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetLastError(
            [MarshalAs(UnmanagedType.LPStr)] System.Text.StringBuilder buffer,
            int bufferSize);

        // ====================================================================
        // Simulation Control
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_StepSimulation(IntPtr handle, float deltaTime);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern void SF_SetPaused(IntPtr handle, int pause);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_IsPaused(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_Reset(IntPtr handle);

        // ====================================================================
        // Mesh Data Access
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetVertexCount(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetTriangleCount(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetVertices(IntPtr handle,
            [Out] float[] outVertices, int maxVertices);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetTriangles(IntPtr handle,
            [Out] int[] outTriangles, int maxTriangles);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetNormals(IntPtr handle,
            [Out] float[] outNormals, int maxNormals);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetUVs(IntPtr handle,
            [Out] float[] outUVs, int maxUVs);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_HasTopologyChanged(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern void SF_ClearTopologyChangedFlag(IntPtr handle);

        // ====================================================================
        // Surgical Operations - Incision
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_PerformIncision(IntPtr handle,
            [In] SFVector3[] points,
            [In] SFVector3[] normals,
            int pointCount,
            int startOpen,
            int endOpen);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern float SF_FindClosestIncisionPoint(IntPtr handle,
            SFVector3 queryPoint,
            out int outTriangle,
            out int outEdge,
            out float outParam);

        // ====================================================================
        // Surgical Operations - Undermining
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_AddUndermineTriangle(IntPtr handle,
            int triangle, int undermineMaterial, int incisionConnect);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_ExecuteUndermine(IntPtr handle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern void SF_ClearUndermine(IntPtr handle, int underminedTissue);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_IsTriangleUndermined(IntPtr handle, int triangle);

        // ====================================================================
        // Surgical Operations - Sutures
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_AddSuture(IntPtr handle,
            int triangle, int edge, float param);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_SetSutureSecondPoint(IntPtr handle,
            int sutureHandle, int triangle, int edge, float param);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_DeleteSuture(IntPtr handle, int sutureHandle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_CreateSutureLine(IntPtr handle,
            int suture1, int suture2);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetSutureCount(IntPtr handle);

        // ====================================================================
        // Constraints - Hooks
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_AddHook(IntPtr handle, SFVector3 position, int strong);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_MoveHook(IntPtr handle,
            int hookHandle, SFVector3 newPosition);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_DeleteHook(IntPtr handle, int hookHandle);

        // ====================================================================
        // Raycasting
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_Raycast(IntPtr handle,
            SFVector3 origin, SFVector3 direction, float maxDistance,
            out SFVector3 outHitPoint, out SFVector3 outHitNormal, out int outTriangle);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetTriangleMaterial(IntPtr handle, int triangle);

        // ====================================================================
        // Statistics and Debugging
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetStats(IntPtr handle, out SFSimStats outStats);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern void SF_SetDebugMode(IntPtr handle, int enable);

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        public static extern int SF_GetTetDebugData(IntPtr handle,
            [Out] float[] outTetVertices, int maxTets);

        // ====================================================================
        // Version Information
        // ====================================================================

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr SF_GetVersion();

        [DllImport(DLL_NAME, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr SF_GetBuildInfo();

        public static string GetVersion()
        {
            return Marshal.PtrToStringAnsi(SF_GetVersion());
        }

        public static string GetBuildInfo()
        {
            return Marshal.PtrToStringAnsi(SF_GetBuildInfo());
        }

        // ====================================================================
        // Helper Methods
        // ====================================================================

        /// <summary>
        /// Gets the last error message from the native plugin
        /// </summary>
        public static string GetLastErrorString()
        {
            var buffer = new System.Text.StringBuilder(1024);
            SF_GetLastError(buffer, buffer.Capacity);
            return buffer.ToString();
        }

        /// <summary>
        /// Checks if a result code indicates success
        /// </summary>
        public static bool IsSuccess(int result)
        {
            return result == (int)SFErrorCode.Success;
        }

        /// <summary>
        /// Throws an exception if the result code indicates failure
        /// </summary>
        public static void ThrowIfFailed(int result, string context = "")
        {
            if (result != (int)SFErrorCode.Success)
            {
                string error = GetLastErrorString();
                string message = string.IsNullOrEmpty(context)
                    ? $"SkinFlaps error: {(SFErrorCode)result} - {error}"
                    : $"SkinFlaps error in {context}: {(SFErrorCode)result} - {error}";
                throw new SkinFlapsException(message, (SFErrorCode)result);
            }
        }
    }

    /// <summary>
    /// Exception thrown by SkinFlaps operations
    /// </summary>
    public class SkinFlapsException : Exception
    {
        public SFErrorCode ErrorCode { get; }

        public SkinFlapsException(string message, SFErrorCode errorCode)
            : base(message)
        {
            ErrorCode = errorCode;
        }
    }
}

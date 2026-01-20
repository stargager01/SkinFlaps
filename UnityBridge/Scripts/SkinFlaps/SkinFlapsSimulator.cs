/**
 * SkinFlapsSimulator.cs
 * Main Unity MonoBehaviour for SkinFlaps soft tissue simulation
 *
 * This component manages the lifecycle of the native simulation,
 * handles mesh synchronization, and provides a high-level API
 * for surgical operations.
 */

using System;
using System.Collections.Generic;
using UnityEngine;

namespace SkinFlaps
{
    /// <summary>
    /// Main SkinFlaps simulation component for Unity.
    /// Attach this to a GameObject with a MeshFilter and MeshRenderer.
    /// </summary>
    [RequireComponent(typeof(MeshFilter))]
    [RequireComponent(typeof(MeshRenderer))]
    public class SkinFlapsSimulator : MonoBehaviour
    {
        #region Inspector Fields

        [Header("Model Configuration")]
        [Tooltip("Path to the .smd model file (relative to StreamingAssets or absolute)")]
        [SerializeField] private string modelPath = "SkinFlaps/FacialFlaps.smd";

        [Tooltip("Path to the data directory containing model assets")]
        [SerializeField] private string dataDirectory = "";

        [Header("Simulation Settings")]
        [Tooltip("Enable simulation on start")]
        [SerializeField] private bool autoStart = true;

        [Tooltip("Physics timestep (seconds)")]
        [SerializeField] private float physicsTimestep = 1f / 60f;

        [Tooltip("Maximum vertex count for mesh buffers")]
        [SerializeField] private int maxVertices = 700000;

        [Tooltip("Maximum triangle count for mesh buffers")]
        [SerializeField] private int maxTriangles = 1400000;

        [Header("Advanced Physics")]
        [SerializeField] private float lowTetWeight = 0.1f;
        [SerializeField] private float highTetWeight = 1.0f;
        [SerializeField] private float tJunctionWeight = 100.0f;
        [SerializeField] private float strainMin = 0.8f;
        [SerializeField] private float strainMax = 1.2f;
        [SerializeField] private float collisionWeight = 1000.0f;
        [SerializeField] private float selfCollisionWeight = 100.0f;
        [SerializeField] private float hookWeight = 500.0f;
        [SerializeField] private float sutureWeight = 1000.0f;

        [Header("Debug")]
        [SerializeField] private bool enableDebugMode = false;
        [SerializeField] private bool showStats = false;

        #endregion

        #region Public Properties

        /// <summary>
        /// Is the simulation currently running?
        /// </summary>
        public bool IsRunning => _isRunning && !IsPaused;

        /// <summary>
        /// Is the simulation paused?
        /// </summary>
        public bool IsPaused
        {
            get => _handle != IntPtr.Zero && SkinFlapsNative.SF_IsPaused(_handle) != 0;
            set
            {
                if (_handle != IntPtr.Zero)
                {
                    SkinFlapsNative.SF_SetPaused(_handle, value ? 1 : 0);
                }
            }
        }

        /// <summary>
        /// Current simulation statistics
        /// </summary>
        public SFSimStats Stats => _stats;

        /// <summary>
        /// Number of active sutures
        /// </summary>
        public int SutureCount => _handle != IntPtr.Zero
            ? SkinFlapsNative.SF_GetSutureCount(_handle)
            : 0;

        /// <summary>
        /// Has the mesh topology changed since last update?
        /// </summary>
        public bool TopologyChanged => _topologyChanged;

        /// <summary>
        /// Event fired when mesh topology changes (after incision/undermine)
        /// </summary>
        public event Action OnTopologyChanged;

        /// <summary>
        /// Event fired each physics frame
        /// </summary>
        public event Action OnPhysicsUpdate;

        #endregion

        #region Private Fields

        private IntPtr _handle = IntPtr.Zero;
        private MeshFilter _meshFilter;
        private Mesh _mesh;
        private bool _isRunning = false;
        private bool _topologyChanged = false;
        private float _physicsAccumulator = 0f;

        // Mesh data buffers
        private float[] _vertexBuffer;
        private int[] _triangleBuffer;
        private float[] _normalBuffer;
        private float[] _uvBuffer;
        private Vector3[] _unityVertices;
        private Vector3[] _unityNormals;
        private Vector2[] _unityUVs;

        private SFSimStats _stats;

        #endregion

        #region Unity Lifecycle

        private void Awake()
        {
            _meshFilter = GetComponent<MeshFilter>();
            _mesh = new Mesh();
            _mesh.name = "SkinFlaps Dynamic Mesh";
            _mesh.MarkDynamic();
            _meshFilter.mesh = _mesh;

            // Allocate buffers
            _vertexBuffer = new float[maxVertices * 3];
            _triangleBuffer = new int[maxTriangles * 3];
            _normalBuffer = new float[maxVertices * 3];
            _uvBuffer = new float[maxVertices * 2];
            _unityVertices = new Vector3[maxVertices];
            _unityNormals = new Vector3[maxVertices];
            _unityUVs = new Vector2[maxVertices];
        }

        private void Start()
        {
            if (autoStart)
            {
                Initialize();
            }
        }

        private void FixedUpdate()
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return;

            _physicsAccumulator += Time.fixedDeltaTime;

            while (_physicsAccumulator >= physicsTimestep)
            {
                StepSimulation();
                _physicsAccumulator -= physicsTimestep;
            }
        }

        private void LateUpdate()
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return;

            // Check for topology changes
            if (SkinFlapsNative.SF_HasTopologyChanged(_handle) != 0)
            {
                _topologyChanged = true;
                SkinFlapsNative.SF_ClearTopologyChangedFlag(_handle);
                OnTopologyChanged?.Invoke();
            }

            // Update mesh
            UpdateMesh();
        }

        private void OnDestroy()
        {
            Shutdown();
        }

        private void OnGUI()
        {
            if (showStats && _isRunning)
            {
                DrawStatsGUI();
            }
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Initialize the simulation with the configured model
        /// </summary>
        public void Initialize()
        {
            if (_isRunning)
            {
                Debug.LogWarning("SkinFlapsSimulator: Already initialized");
                return;
            }

            try
            {
                // Resolve paths
                string resolvedDataDir = string.IsNullOrEmpty(dataDirectory)
                    ? Application.streamingAssetsPath
                    : dataDirectory;

                string resolvedModelPath = System.IO.Path.IsPathRooted(modelPath)
                    ? modelPath
                    : System.IO.Path.Combine(resolvedDataDir, modelPath);

                Debug.Log($"SkinFlapsSimulator: Loading model from {resolvedModelPath}");

                // Create simulator
                _handle = SkinFlapsNative.SF_CreateSimulator(resolvedModelPath, resolvedDataDir);
                if (_handle == IntPtr.Zero)
                {
                    throw new SkinFlapsException(
                        $"Failed to create simulator: {SkinFlapsNative.GetLastErrorString()}",
                        SFErrorCode.Unknown);
                }

                // Configure and initialize
                var config = new SFSimConfig
                {
                    lowTetWeight = lowTetWeight,
                    highTetWeight = highTetWeight,
                    tJunctionWeight = tJunctionWeight,
                    strainMin = strainMin,
                    strainMax = strainMax,
                    collisionWeight = collisionWeight,
                    selfCollisionWeight = selfCollisionWeight,
                    fixedWeight = 10000.0f,
                    peripheralWeight = 1000.0f,
                    hookWeight = hookWeight,
                    sutureWeight = sutureWeight,
                    stressLimit = float.MaxValue
                };

                int result = SkinFlapsNative.SF_Initialize(_handle, ref config);
                SkinFlapsNative.ThrowIfFailed(result, "Initialize");

                if (enableDebugMode)
                {
                    SkinFlapsNative.SF_SetDebugMode(_handle, 1);
                }

                _isRunning = true;
                _topologyChanged = true; // Force initial mesh update

                Debug.Log($"SkinFlapsSimulator: Initialized successfully. Version: {SkinFlapsNative.GetVersion()}");
            }
            catch (Exception e)
            {
                Debug.LogError($"SkinFlapsSimulator: Initialization failed - {e.Message}");
                Shutdown();
                throw;
            }
        }

        /// <summary>
        /// Shutdown the simulation and release resources
        /// </summary>
        public void Shutdown()
        {
            if (_handle != IntPtr.Zero)
            {
                SkinFlapsNative.SF_DestroySimulator(_handle);
                _handle = IntPtr.Zero;
            }
            _isRunning = false;
        }

        /// <summary>
        /// Perform a skin incision along a path
        /// </summary>
        /// <param name="points">World-space points defining the incision path</param>
        /// <param name="normals">Surface normals at each point</param>
        /// <param name="startOpen">Leave the start of the incision open</param>
        /// <param name="endOpen">Leave the end of the incision open</param>
        public void PerformIncision(Vector3[] points, Vector3[] normals, bool startOpen = true, bool endOpen = true)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
            {
                Debug.LogWarning("SkinFlapsSimulator: Cannot perform incision - not running");
                return;
            }

            if (points == null || normals == null || points.Length < 2 || points.Length != normals.Length)
            {
                Debug.LogError("SkinFlapsSimulator: Invalid incision parameters");
                return;
            }

            // Convert to local space
            var localPoints = new SFVector3[points.Length];
            var localNormals = new SFVector3[normals.Length];

            for (int i = 0; i < points.Length; i++)
            {
                Vector3 localPos = transform.InverseTransformPoint(points[i]);
                Vector3 localNorm = transform.InverseTransformDirection(normals[i]).normalized;

                localPoints[i] = new SFVector3(localPos);
                localNormals[i] = new SFVector3(localNorm);
            }

            int result = SkinFlapsNative.SF_PerformIncision(
                _handle, localPoints, localNormals, points.Length,
                startOpen ? 1 : 0, endOpen ? 1 : 0);

            SkinFlapsNative.ThrowIfFailed(result, "PerformIncision");
        }

        /// <summary>
        /// Perform a skin incision between two world-space points
        /// </summary>
        public void PerformIncision(Vector3 start, Vector3 end, Vector3 normal, bool startOpen = true, bool endOpen = true)
        {
            PerformIncision(
                new Vector3[] { start, end },
                new Vector3[] { normal, normal },
                startOpen, endOpen);
        }

        /// <summary>
        /// Add a hook at the specified world position
        /// </summary>
        /// <returns>Hook handle for later manipulation, or -1 on failure</returns>
        public int AddHook(Vector3 worldPosition, bool strong = false)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return -1;

            Vector3 localPos = transform.InverseTransformPoint(worldPosition);
            return SkinFlapsNative.SF_AddHook(_handle, new SFVector3(localPos), strong ? 1 : 0);
        }

        /// <summary>
        /// Move an existing hook to a new position
        /// </summary>
        public void MoveHook(int hookHandle, Vector3 worldPosition)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return;

            Vector3 localPos = transform.InverseTransformPoint(worldPosition);
            SkinFlapsNative.SF_MoveHook(_handle, hookHandle, new SFVector3(localPos));
        }

        /// <summary>
        /// Delete a hook
        /// </summary>
        public void DeleteHook(int hookHandle)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return;

            SkinFlapsNative.SF_DeleteHook(_handle, hookHandle);
        }

        /// <summary>
        /// Add a suture at the first attachment point
        /// </summary>
        /// <returns>Suture handle, or -1 on failure</returns>
        public int AddSuture(int triangle, int edge, float param)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return -1;

            return SkinFlapsNative.SF_AddSuture(_handle, triangle, edge, param);
        }

        /// <summary>
        /// Set the second attachment point for a suture
        /// </summary>
        public int SetSutureSecondPoint(int sutureHandle, int triangle, int edge, float param)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return -1;

            return SkinFlapsNative.SF_SetSutureSecondPoint(_handle, sutureHandle, triangle, edge, param);
        }

        /// <summary>
        /// Delete a suture
        /// </summary>
        public void DeleteSuture(int sutureHandle)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return;

            SkinFlapsNative.SF_DeleteSuture(_handle, sutureHandle);
        }

        /// <summary>
        /// Create a line of sutures between two existing sutures
        /// </summary>
        /// <returns>Number of sutures created</returns>
        public int CreateSutureLine(int suture1, int suture2)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return 0;

            return SkinFlapsNative.SF_CreateSutureLine(_handle, suture1, suture2);
        }

        /// <summary>
        /// Perform a raycast against the simulation mesh
        /// </summary>
        public bool Raycast(Ray ray, out RaycastHit hitInfo, float maxDistance = 1000f)
        {
            hitInfo = default;

            if (!_isRunning || _handle == IntPtr.Zero)
                return false;

            // Convert to local space
            Vector3 localOrigin = transform.InverseTransformPoint(ray.origin);
            Vector3 localDir = transform.InverseTransformDirection(ray.direction);

            int hit = SkinFlapsNative.SF_Raycast(
                _handle,
                new SFVector3(localOrigin),
                new SFVector3(localDir),
                maxDistance,
                out SFVector3 hitPoint,
                out SFVector3 hitNormal,
                out int triangle);

            if (hit != 0)
            {
                hitInfo = new RaycastHit
                {
                    point = transform.TransformPoint(hitPoint.ToUnityVector3()),
                    normal = transform.TransformDirection(hitNormal.ToUnityVector3()),
                    triangleIndex = triangle,
                    distance = Vector3.Distance(ray.origin, hitInfo.point)
                };
                return true;
            }

            return false;
        }

        /// <summary>
        /// Get the material ID of a triangle
        /// </summary>
        public int GetTriangleMaterial(int triangle)
        {
            if (!_isRunning || _handle == IntPtr.Zero)
                return -1;

            return SkinFlapsNative.SF_GetTriangleMaterial(_handle, triangle);
        }

        #endregion

        #region Private Methods

        private void StepSimulation()
        {
            if (_handle == IntPtr.Zero)
                return;

            int result = SkinFlapsNative.SF_StepSimulation(_handle, physicsTimestep);

            if (result == (int)SFErrorCode.Success)
            {
                // Update stats
                SkinFlapsNative.SF_GetStats(_handle, out _stats);
                OnPhysicsUpdate?.Invoke();
            }
        }

        private void UpdateMesh()
        {
            if (_handle == IntPtr.Zero)
                return;

            int vertCount = SkinFlapsNative.SF_GetVertices(_handle, _vertexBuffer, maxVertices);
            int triCount = SkinFlapsNative.SF_GetTriangles(_handle, _triangleBuffer, maxTriangles);
            int normCount = SkinFlapsNative.SF_GetNormals(_handle, _normalBuffer, maxVertices);
            int uvCount = SkinFlapsNative.SF_GetUVs(_handle, _uvBuffer, maxVertices);

            if (vertCount == 0 || triCount == 0)
                return;

            // Convert vertex data
            for (int i = 0; i < vertCount; i++)
            {
                _unityVertices[i] = new Vector3(
                    _vertexBuffer[i * 3 + 0],
                    _vertexBuffer[i * 3 + 1],
                    _vertexBuffer[i * 3 + 2]);
            }

            // Convert normal data
            for (int i = 0; i < normCount; i++)
            {
                _unityNormals[i] = new Vector3(
                    _normalBuffer[i * 3 + 0],
                    _normalBuffer[i * 3 + 1],
                    _normalBuffer[i * 3 + 2]);
            }

            // Convert UV data
            for (int i = 0; i < uvCount; i++)
            {
                _unityUVs[i] = new Vector2(
                    _uvBuffer[i * 2 + 0],
                    _uvBuffer[i * 2 + 1]);
            }

            // Update mesh
            _mesh.Clear();
            _mesh.SetVertices(_unityVertices, 0, vertCount);
            _mesh.SetTriangles(_triangleBuffer, 0, triCount * 3, 0);

            if (normCount > 0)
            {
                _mesh.SetNormals(_unityNormals, 0, normCount);
            }
            else
            {
                _mesh.RecalculateNormals();
            }

            if (uvCount > 0)
            {
                _mesh.SetUVs(0, _unityUVs, 0, uvCount);
            }

            _mesh.RecalculateBounds();
            _topologyChanged = false;
        }

        private void DrawStatsGUI()
        {
            GUILayout.BeginArea(new Rect(10, 10, 300, 200));
            GUILayout.BeginVertical("box");

            GUILayout.Label("SkinFlaps Statistics", GUI.skin.GetStyle("boldLabel"));
            GUILayout.Label($"Vertices: {_stats.vertexCount:N0}");
            GUILayout.Label($"Tetrahedra: {_stats.tetCount:N0}");
            GUILayout.Label($"Solve Time: {_stats.lastSolveTimeMs:F2} ms");
            GUILayout.Label($"Max Stress: {_stats.maxStress:F4}");
            GUILayout.Label($"Sutures: {SutureCount}");

            GUILayout.EndVertical();
            GUILayout.EndArea();
        }

        #endregion

        #region Editor Support

#if UNITY_EDITOR
        private void OnValidate()
        {
            maxVertices = Mathf.Max(1000, maxVertices);
            maxTriangles = Mathf.Max(1000, maxTriangles);
            physicsTimestep = Mathf.Clamp(physicsTimestep, 0.001f, 0.1f);
        }
#endif

        #endregion
    }

    /// <summary>
    /// Extended RaycastHit with triangle index
    /// </summary>
    public struct RaycastHit
    {
        public Vector3 point;
        public Vector3 normal;
        public int triangleIndex;
        public float distance;
    }
}

/**
 * SutureTool.cs
 * Interactive suturing tool for SkinFlaps
 *
 * This component allows users to place sutures to close incisions.
 * Sutures are placed by clicking on two edges of an incision.
 */

using System;
using System.Collections.Generic;
using UnityEngine;

namespace SkinFlaps.Tools
{
    /// <summary>
    /// Represents a suture attachment point
    /// </summary>
    public struct SutureAttachment
    {
        public int triangle;
        public int edge;
        public float param;
        public Vector3 worldPosition;

        public bool IsValid => triangle >= 0;

        public static SutureAttachment Invalid => new SutureAttachment { triangle = -1 };
    }

    /// <summary>
    /// Interactive tool for placing sutures
    /// </summary>
    public class SutureTool : MonoBehaviour
    {
        #region Inspector Fields

        [Header("References")]
        [SerializeField] private SkinFlapsSimulator simulator;
        [SerializeField] private Camera mainCamera;

        [Header("Tool Settings")]
        [SerializeField] private float raycastDistance = 10f;
        [SerializeField] private float snapDistance = 0.005f;

        [Header("Suture Options")]
        [SerializeField] private bool autoCreateLine = true;
        [SerializeField] private float sutureSpacing = 0.005f;

        [Header("Visual Feedback")]
        [SerializeField] private GameObject sutureMarkerPrefab;
        [SerializeField] private LineRenderer suturePreview;
        [SerializeField] private Color firstPointColor = Color.yellow;
        [SerializeField] private Color secondPointColor = Color.green;

        #endregion

        #region Private Fields

        private bool _toolActive = false;
        private SutureAttachment _firstPoint = SutureAttachment.Invalid;
        private int _currentSutureHandle = -1;
        private List<int> _placedSutures = new List<int>();
        private List<GameObject> _sutureMarkers = new List<GameObject>();
        private int _lastLinkedSuture = -1;

        #endregion

        #region Public Properties

        /// <summary>
        /// Is the tool currently active?
        /// </summary>
        public bool IsActive
        {
            get => _toolActive;
            set
            {
                _toolActive = value;
                if (!value)
                {
                    CancelCurrentSuture();
                }
            }
        }

        /// <summary>
        /// Is waiting for the second suture point?
        /// </summary>
        public bool IsPlacingSecondPoint => _firstPoint.IsValid;

        /// <summary>
        /// Number of placed sutures
        /// </summary>
        public int SutureCount => simulator != null ? simulator.SutureCount : 0;

        /// <summary>
        /// Event fired when a suture is completed
        /// </summary>
        public event System.Action<int> OnSuturePlaced;

        #endregion

        #region Unity Lifecycle

        private void Awake()
        {
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
            }

            if (suturePreview != null)
            {
                suturePreview.positionCount = 0;
            }
        }

        private void Update()
        {
            if (!_toolActive || simulator == null || !simulator.IsRunning)
                return;

            HandleInput();
            UpdatePreview();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Activate the suture tool
        /// </summary>
        public void Activate()
        {
            IsActive = true;
        }

        /// <summary>
        /// Deactivate the suture tool
        /// </summary>
        public void Deactivate()
        {
            IsActive = false;
        }

        /// <summary>
        /// Cancel the current suture placement
        /// </summary>
        public void CancelCurrentSuture()
        {
            if (_currentSutureHandle >= 0 && simulator != null)
            {
                simulator.DeleteSuture(_currentSutureHandle);
            }

            _firstPoint = SutureAttachment.Invalid;
            _currentSutureHandle = -1;

            if (suturePreview != null)
            {
                suturePreview.positionCount = 0;
            }
        }

        /// <summary>
        /// Delete the most recently placed suture
        /// </summary>
        public void UndoLastSuture()
        {
            if (_placedSutures.Count == 0 || simulator == null)
                return;

            int lastSuture = _placedSutures[_placedSutures.Count - 1];
            simulator.DeleteSuture(lastSuture);
            _placedSutures.RemoveAt(_placedSutures.Count - 1);

            // Remove marker if present
            if (_sutureMarkers.Count > 0)
            {
                GameObject marker = _sutureMarkers[_sutureMarkers.Count - 1];
                if (marker != null)
                {
                    Destroy(marker);
                }
                _sutureMarkers.RemoveAt(_sutureMarkers.Count - 1);
            }

            // Reset linked suture tracking
            if (_placedSutures.Count > 0)
            {
                _lastLinkedSuture = _placedSutures[_placedSutures.Count - 1];
            }
            else
            {
                _lastLinkedSuture = -1;
            }
        }

        /// <summary>
        /// Delete all placed sutures
        /// </summary>
        public void ClearAllSutures()
        {
            foreach (int sutureHandle in _placedSutures)
            {
                if (simulator != null)
                {
                    simulator.DeleteSuture(sutureHandle);
                }
            }
            _placedSutures.Clear();

            foreach (GameObject marker in _sutureMarkers)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            _sutureMarkers.Clear();

            _lastLinkedSuture = -1;
        }

        /// <summary>
        /// Create a line of automatic sutures between two existing sutures
        /// </summary>
        public int CreateSutureLine(int suture1, int suture2)
        {
            if (simulator == null || !simulator.IsRunning)
                return 0;

            return simulator.CreateSutureLine(suture1, suture2);
        }

        #endregion

        #region Private Methods

        private void HandleInput()
        {
            Vector3 mousePos = Input.mousePosition;

            // Place suture point on click
            if (Input.GetMouseButtonDown(0))
            {
                TryPlaceSuturePoint(mousePos);
            }

            // Cancel with right-click or Escape
            if (Input.GetMouseButtonDown(1) || Input.GetKeyDown(KeyCode.Escape))
            {
                CancelCurrentSuture();
            }

            // Undo with Ctrl+Z
            if ((Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl)) &&
                Input.GetKeyDown(KeyCode.Z))
            {
                UndoLastSuture();
            }
        }

        private void TryPlaceSuturePoint(Vector3 screenPos)
        {
            Ray ray = mainCamera.ScreenPointToRay(screenPos);

            if (!simulator.Raycast(ray, out RaycastHit hit, raycastDistance))
                return;

            // Only allow sutures on incision wall material (material 3)
            int material = simulator.GetTriangleMaterial(hit.triangleIndex);
            if (material != 3)
            {
                Debug.Log("SutureTool: Sutures can only be placed on incision edges (material 3)");
                return;
            }

            // Find closest incision edge
            SFVector3 queryPoint = new SFVector3(
                simulator.transform.InverseTransformPoint(hit.point));

            float dist = SkinFlapsNative.SF_FindClosestIncisionPoint(
                GetSimulatorHandle(),
                queryPoint,
                out int triangle,
                out int edge,
                out float param);

            if (dist < 0 || dist > snapDistance)
            {
                Debug.Log("SutureTool: No incision edge found nearby");
                return;
            }

            SutureAttachment attachment = new SutureAttachment
            {
                triangle = triangle,
                edge = edge,
                param = param,
                worldPosition = hit.point
            };

            if (!_firstPoint.IsValid)
            {
                // Place first point
                _firstPoint = attachment;
                _currentSutureHandle = simulator.AddSuture(triangle, edge, param);

                if (_currentSutureHandle >= 0)
                {
                    CreateMarker(hit.point, firstPointColor);
                }
            }
            else
            {
                // Place second point and complete suture
                int result = simulator.SetSutureSecondPoint(
                    _currentSutureHandle, triangle, edge, param);

                if (result >= 0)
                {
                    CreateMarker(hit.point, secondPointColor);
                    _placedSutures.Add(_currentSutureHandle);

                    // Auto-create suture line if enabled and we have a previous suture
                    if (autoCreateLine && _lastLinkedSuture >= 0)
                    {
                        int created = simulator.CreateSutureLine(_lastLinkedSuture, _currentSutureHandle);
                        Debug.Log($"SutureTool: Created {created} auto-sutures");
                    }

                    _lastLinkedSuture = _currentSutureHandle;
                    OnSuturePlaced?.Invoke(_currentSutureHandle);
                }
                else
                {
                    Debug.LogWarning($"SutureTool: Failed to complete suture (result: {result})");
                    simulator.DeleteSuture(_currentSutureHandle);
                }

                // Reset for next suture
                _firstPoint = SutureAttachment.Invalid;
                _currentSutureHandle = -1;
            }
        }

        private void UpdatePreview()
        {
            if (suturePreview == null)
                return;

            if (!_firstPoint.IsValid)
            {
                suturePreview.positionCount = 0;
                return;
            }

            // Show line from first point to current mouse position
            Vector3 mousePos = Input.mousePosition;
            Ray ray = mainCamera.ScreenPointToRay(mousePos);

            if (simulator.Raycast(ray, out RaycastHit hit, raycastDistance))
            {
                suturePreview.positionCount = 2;
                suturePreview.SetPosition(0, _firstPoint.worldPosition);
                suturePreview.SetPosition(1, hit.point);
            }
            else
            {
                suturePreview.positionCount = 2;
                suturePreview.SetPosition(0, _firstPoint.worldPosition);
                suturePreview.SetPosition(1, ray.GetPoint(0.1f));
            }
        }

        private void CreateMarker(Vector3 position, Color color)
        {
            if (sutureMarkerPrefab != null)
            {
                GameObject marker = Instantiate(sutureMarkerPrefab, position, Quaternion.identity);
                marker.transform.SetParent(transform);

                Renderer renderer = marker.GetComponent<Renderer>();
                if (renderer != null)
                {
                    renderer.material.color = color;
                }

                _sutureMarkers.Add(marker);
            }
        }

        private IntPtr GetSimulatorHandle()
        {
            // Access the native handle through reflection or a public property
            // This is a workaround - ideally SkinFlapsSimulator would expose this
            var field = typeof(SkinFlapsSimulator).GetField("_handle",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            return field != null ? (IntPtr)field.GetValue(simulator) : IntPtr.Zero;
        }

        #endregion
    }
}

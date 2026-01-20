/**
 * IncisionTool.cs
 * Interactive incision drawing tool for SkinFlaps
 *
 * This component allows users to draw incision lines on the skin surface
 * using mouse or touch input. Supports both single-stroke and multi-point
 * incision modes.
 */

using System.Collections.Generic;
using UnityEngine;

namespace SkinFlaps.Tools
{
    /// <summary>
    /// Incision drawing modes
    /// </summary>
    public enum IncisionMode
    {
        /// <summary>Single continuous stroke while holding button</summary>
        Continuous,
        /// <summary>Click to place points, double-click or Enter to finish</summary>
        PointByPoint
    }

    /// <summary>
    /// Interactive tool for performing skin incisions
    /// </summary>
    public class IncisionTool : MonoBehaviour
    {
        #region Inspector Fields

        [Header("References")]
        [SerializeField] private SkinFlapsSimulator simulator;
        [SerializeField] private Camera mainCamera;
        [SerializeField] private LineRenderer incisionPreview;

        [Header("Tool Settings")]
        [SerializeField] private IncisionMode mode = IncisionMode.Continuous;
        [SerializeField] private float minPointSpacing = 0.002f;
        [SerializeField] private float raycastDistance = 10f;
        [SerializeField] private LayerMask skinLayerMask = ~0;

        [Header("Incision Options")]
        [SerializeField] private bool startOpen = true;
        [SerializeField] private bool endOpen = true;

        [Header("Visual Feedback")]
        [SerializeField] private Color previewColor = new Color(1f, 0f, 0f, 0.8f);
        [SerializeField] private Color validColor = new Color(0f, 1f, 0f, 0.8f);
        [SerializeField] private float previewLineWidth = 0.002f;

        #endregion

        #region Private Fields

        private List<Vector3> _incisionPoints = new List<Vector3>();
        private List<Vector3> _incisionNormals = new List<Vector3>();
        private bool _isDrawing = false;
        private Vector3 _lastPoint;
        private bool _toolActive = false;

        #endregion

        #region Public Properties

        /// <summary>
        /// Is the tool currently active and accepting input?
        /// </summary>
        public bool IsActive
        {
            get => _toolActive;
            set
            {
                _toolActive = value;
                if (!value)
                {
                    CancelIncision();
                }
            }
        }

        /// <summary>
        /// Number of points in the current incision
        /// </summary>
        public int PointCount => _incisionPoints.Count;

        /// <summary>
        /// Is an incision currently being drawn?
        /// </summary>
        public bool IsDrawing => _isDrawing;

        /// <summary>
        /// Event fired when an incision is completed
        /// </summary>
        public event System.Action<Vector3[], Vector3[]> OnIncisionCompleted;

        #endregion

        #region Unity Lifecycle

        private void Awake()
        {
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
            }

            if (incisionPreview != null)
            {
                incisionPreview.positionCount = 0;
                incisionPreview.startWidth = previewLineWidth;
                incisionPreview.endWidth = previewLineWidth;
                SetPreviewColor(previewColor);
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
        /// Activate the incision tool
        /// </summary>
        public void Activate()
        {
            IsActive = true;
        }

        /// <summary>
        /// Deactivate the incision tool
        /// </summary>
        public void Deactivate()
        {
            IsActive = false;
        }

        /// <summary>
        /// Cancel the current incision without applying it
        /// </summary>
        public void CancelIncision()
        {
            _incisionPoints.Clear();
            _incisionNormals.Clear();
            _isDrawing = false;
            UpdatePreview();
        }

        /// <summary>
        /// Complete and apply the current incision
        /// </summary>
        public void CompleteIncision()
        {
            if (_incisionPoints.Count < 2)
            {
                Debug.LogWarning("IncisionTool: Need at least 2 points for incision");
                CancelIncision();
                return;
            }

            try
            {
                Vector3[] points = _incisionPoints.ToArray();
                Vector3[] normals = _incisionNormals.ToArray();

                simulator.PerformIncision(points, normals, startOpen, endOpen);

                OnIncisionCompleted?.Invoke(points, normals);

                SetPreviewColor(validColor);
            }
            catch (SkinFlapsException e)
            {
                Debug.LogError($"IncisionTool: Failed to perform incision - {e.Message}");
            }
            finally
            {
                _incisionPoints.Clear();
                _incisionNormals.Clear();
                _isDrawing = false;
                UpdatePreview();
            }
        }

        /// <summary>
        /// Add a point to the incision path
        /// </summary>
        public void AddPoint(Vector3 worldPosition, Vector3 normal)
        {
            if (_incisionPoints.Count > 0)
            {
                float dist = Vector3.Distance(worldPosition, _lastPoint);
                if (dist < minPointSpacing)
                    return;
            }

            _incisionPoints.Add(worldPosition);
            _incisionNormals.Add(normal.normalized);
            _lastPoint = worldPosition;
            _isDrawing = true;

            UpdatePreview();
        }

        #endregion

        #region Private Methods

        private void HandleInput()
        {
            Vector3 mousePos = Input.mousePosition;

            switch (mode)
            {
                case IncisionMode.Continuous:
                    HandleContinuousMode(mousePos);
                    break;

                case IncisionMode.PointByPoint:
                    HandlePointByPointMode(mousePos);
                    break;
            }

            // Cancel with right-click or Escape
            if (Input.GetMouseButtonDown(1) || Input.GetKeyDown(KeyCode.Escape))
            {
                CancelIncision();
            }
        }

        private void HandleContinuousMode(Vector3 mousePos)
        {
            if (Input.GetMouseButtonDown(0))
            {
                // Start new incision
                _incisionPoints.Clear();
                _incisionNormals.Clear();
                TryAddPointAtScreenPosition(mousePos);
            }
            else if (Input.GetMouseButton(0) && _isDrawing)
            {
                // Continue drawing
                TryAddPointAtScreenPosition(mousePos);
            }
            else if (Input.GetMouseButtonUp(0) && _isDrawing)
            {
                // Finish incision
                CompleteIncision();
            }
        }

        private void HandlePointByPointMode(Vector3 mousePos)
        {
            if (Input.GetMouseButtonDown(0))
            {
                TryAddPointAtScreenPosition(mousePos);
            }

            // Complete with Enter key
            if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
            {
                CompleteIncision();
            }
        }

        private void TryAddPointAtScreenPosition(Vector3 screenPos)
        {
            Ray ray = mainCamera.ScreenPointToRay(screenPos);

            if (simulator.Raycast(ray, out RaycastHit hit, raycastDistance))
            {
                // Only allow incisions on skin material (material 2)
                int material = simulator.GetTriangleMaterial(hit.triangleIndex);
                if (material == 2) // Skin material
                {
                    AddPoint(hit.point, hit.normal);
                }
            }
        }

        private void UpdatePreview()
        {
            if (incisionPreview == null)
                return;

            if (_incisionPoints.Count == 0)
            {
                incisionPreview.positionCount = 0;
                return;
            }

            incisionPreview.positionCount = _incisionPoints.Count;
            for (int i = 0; i < _incisionPoints.Count; i++)
            {
                // Offset slightly along normal for visibility
                Vector3 offsetPoint = _incisionPoints[i] + _incisionNormals[i] * 0.001f;
                incisionPreview.SetPosition(i, offsetPoint);
            }
        }

        private void SetPreviewColor(Color color)
        {
            if (incisionPreview != null)
            {
                incisionPreview.startColor = color;
                incisionPreview.endColor = color;
            }
        }

        #endregion
    }
}

/**
 * HookTool.cs
 * Interactive tissue manipulation tool for SkinFlaps
 *
 * This component allows users to grab and manipulate tissue using
 * virtual hooks. Supports mouse/touch and VR controller input.
 */

using System.Collections.Generic;
using UnityEngine;

namespace SkinFlaps.Tools
{
    /// <summary>
    /// Represents an active hook in the scene
    /// </summary>
    public class ActiveHook
    {
        public int handle;
        public Vector3 grabOffset;
        public Vector3 currentPosition;
        public bool isStrong;
        public GameObject visualObject;
    }

    /// <summary>
    /// Interactive tool for tissue manipulation using hooks
    /// </summary>
    public class HookTool : MonoBehaviour
    {
        #region Inspector Fields

        [Header("References")]
        [SerializeField] private SkinFlapsSimulator simulator;
        [SerializeField] private Camera mainCamera;

        [Header("Tool Settings")]
        [SerializeField] private float raycastDistance = 10f;
        [SerializeField] private float dragSensitivity = 1f;
        [SerializeField] private float maxDragDistance = 0.1f;

        [Header("Hook Options")]
        [SerializeField] private bool useStrongHooks = false;
        [SerializeField] private bool multipleHooksAllowed = true;
        [SerializeField] private int maxHooks = 5;

        [Header("Visual Feedback")]
        [SerializeField] private GameObject hookPrefab;
        [SerializeField] private Color normalHookColor = Color.cyan;
        [SerializeField] private Color strongHookColor = Color.red;
        [SerializeField] private Color draggedHookColor = Color.yellow;

        #endregion

        #region Private Fields

        private bool _toolActive = false;
        private List<ActiveHook> _hooks = new List<ActiveHook>();
        private ActiveHook _draggedHook = null;
        private Vector3 _dragStartPosition;
        private Vector3 _dragStartMouseWorld;

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
                    StopDragging();
                }
            }
        }

        /// <summary>
        /// Is currently dragging a hook?
        /// </summary>
        public bool IsDragging => _draggedHook != null;

        /// <summary>
        /// Number of active hooks
        /// </summary>
        public int HookCount => _hooks.Count;

        /// <summary>
        /// Use strong hooks for more forceful manipulation
        /// </summary>
        public bool UseStrongHooks
        {
            get => useStrongHooks;
            set => useStrongHooks = value;
        }

        /// <summary>
        /// Event fired when a hook is placed
        /// </summary>
        public event System.Action<int, Vector3> OnHookPlaced;

        /// <summary>
        /// Event fired when a hook is moved
        /// </summary>
        public event System.Action<int, Vector3> OnHookMoved;

        /// <summary>
        /// Event fired when a hook is removed
        /// </summary>
        public event System.Action<int> OnHookRemoved;

        #endregion

        #region Unity Lifecycle

        private void Awake()
        {
            if (mainCamera == null)
            {
                mainCamera = Camera.main;
            }
        }

        private void Update()
        {
            if (!_toolActive || simulator == null || !simulator.IsRunning)
                return;

            HandleInput();
            UpdateHookVisuals();
        }

        private void OnDestroy()
        {
            ClearAllHooks();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Activate the hook tool
        /// </summary>
        public void Activate()
        {
            IsActive = true;
        }

        /// <summary>
        /// Deactivate the hook tool
        /// </summary>
        public void Deactivate()
        {
            IsActive = false;
        }

        /// <summary>
        /// Place a hook at the specified world position
        /// </summary>
        public int PlaceHook(Vector3 worldPosition, bool strong = false)
        {
            if (simulator == null || !simulator.IsRunning)
                return -1;

            if (!multipleHooksAllowed && _hooks.Count > 0)
            {
                // Remove existing hook
                RemoveHook(_hooks[0].handle);
            }
            else if (_hooks.Count >= maxHooks)
            {
                Debug.LogWarning($"HookTool: Maximum hooks ({maxHooks}) reached");
                return -1;
            }

            int handle = simulator.AddHook(worldPosition, strong);
            if (handle < 0)
            {
                Debug.LogWarning("HookTool: Failed to place hook");
                return -1;
            }

            ActiveHook hook = new ActiveHook
            {
                handle = handle,
                grabOffset = Vector3.zero,
                currentPosition = worldPosition,
                isStrong = strong,
                visualObject = CreateHookVisual(worldPosition, strong)
            };

            _hooks.Add(hook);
            OnHookPlaced?.Invoke(handle, worldPosition);

            return handle;
        }

        /// <summary>
        /// Move a hook to a new position
        /// </summary>
        public void MoveHook(int hookHandle, Vector3 newPosition)
        {
            ActiveHook hook = _hooks.Find(h => h.handle == hookHandle);
            if (hook == null)
                return;

            // Clamp movement to max drag distance
            Vector3 delta = newPosition - hook.currentPosition;
            if (delta.magnitude > maxDragDistance)
            {
                delta = delta.normalized * maxDragDistance;
                newPosition = hook.currentPosition + delta;
            }

            simulator.MoveHook(hookHandle, newPosition);
            hook.currentPosition = newPosition;

            if (hook.visualObject != null)
            {
                hook.visualObject.transform.position = newPosition;
            }

            OnHookMoved?.Invoke(hookHandle, newPosition);
        }

        /// <summary>
        /// Remove a hook
        /// </summary>
        public void RemoveHook(int hookHandle)
        {
            ActiveHook hook = _hooks.Find(h => h.handle == hookHandle);
            if (hook == null)
                return;

            if (_draggedHook == hook)
            {
                StopDragging();
            }

            simulator.DeleteHook(hookHandle);

            if (hook.visualObject != null)
            {
                Destroy(hook.visualObject);
            }

            _hooks.Remove(hook);
            OnHookRemoved?.Invoke(hookHandle);
        }

        /// <summary>
        /// Remove all hooks
        /// </summary>
        public void ClearAllHooks()
        {
            StopDragging();

            foreach (ActiveHook hook in _hooks)
            {
                if (simulator != null && simulator.IsRunning)
                {
                    simulator.DeleteHook(hook.handle);
                }

                if (hook.visualObject != null)
                {
                    Destroy(hook.visualObject);
                }
            }

            _hooks.Clear();
        }

        /// <summary>
        /// Get the position of a hook
        /// </summary>
        public Vector3? GetHookPosition(int hookHandle)
        {
            ActiveHook hook = _hooks.Find(h => h.handle == hookHandle);
            return hook?.currentPosition;
        }

        #endregion

        #region Private Methods

        private void HandleInput()
        {
            Vector3 mousePos = Input.mousePosition;

            // Left click to place or grab hook
            if (Input.GetMouseButtonDown(0))
            {
                HandleLeftClick(mousePos);
            }
            // Drag while holding
            else if (Input.GetMouseButton(0) && _draggedHook != null)
            {
                HandleDrag(mousePos);
            }
            // Release to stop dragging
            else if (Input.GetMouseButtonUp(0) && _draggedHook != null)
            {
                StopDragging();
            }

            // Right click to remove hook
            if (Input.GetMouseButtonDown(1))
            {
                HandleRightClick(mousePos);
            }

            // Delete key to remove all hooks
            if (Input.GetKeyDown(KeyCode.Delete))
            {
                ClearAllHooks();
            }
        }

        private void HandleLeftClick(Vector3 screenPos)
        {
            // Check if clicking on existing hook
            ActiveHook clickedHook = FindHookAtScreenPosition(screenPos);
            if (clickedHook != null)
            {
                // Start dragging existing hook
                StartDragging(clickedHook, screenPos);
                return;
            }

            // Otherwise, try to place new hook on skin
            Ray ray = mainCamera.ScreenPointToRay(screenPos);
            if (simulator.Raycast(ray, out RaycastHit hit, raycastDistance))
            {
                // Only place hooks on skin material
                int material = simulator.GetTriangleMaterial(hit.triangleIndex);
                if (material == 2)
                {
                    int handle = PlaceHook(hit.point, useStrongHooks);
                    if (handle >= 0)
                    {
                        // Immediately start dragging the new hook
                        ActiveHook newHook = _hooks.Find(h => h.handle == handle);
                        if (newHook != null)
                        {
                            StartDragging(newHook, screenPos);
                        }
                    }
                }
            }
        }

        private void HandleRightClick(Vector3 screenPos)
        {
            ActiveHook clickedHook = FindHookAtScreenPosition(screenPos);
            if (clickedHook != null)
            {
                RemoveHook(clickedHook.handle);
            }
        }

        private void HandleDrag(Vector3 screenPos)
        {
            if (_draggedHook == null)
                return;

            // Project mouse movement onto a plane at the hook's depth
            Ray ray = mainCamera.ScreenPointToRay(screenPos);
            Plane dragPlane = new Plane(-mainCamera.transform.forward, _draggedHook.currentPosition);

            if (dragPlane.Raycast(ray, out float distance))
            {
                Vector3 newPosition = ray.GetPoint(distance);

                // Apply drag sensitivity
                Vector3 delta = (newPosition - _dragStartMouseWorld) * dragSensitivity;
                newPosition = _dragStartPosition + delta;

                MoveHook(_draggedHook.handle, newPosition);
            }
        }

        private void StartDragging(ActiveHook hook, Vector3 screenPos)
        {
            _draggedHook = hook;
            _dragStartPosition = hook.currentPosition;

            Ray ray = mainCamera.ScreenPointToRay(screenPos);
            Plane dragPlane = new Plane(-mainCamera.transform.forward, hook.currentPosition);

            if (dragPlane.Raycast(ray, out float distance))
            {
                _dragStartMouseWorld = ray.GetPoint(distance);
            }

            // Visual feedback
            if (hook.visualObject != null)
            {
                SetHookColor(hook.visualObject, draggedHookColor);
            }
        }

        private void StopDragging()
        {
            if (_draggedHook != null)
            {
                // Restore visual color
                if (_draggedHook.visualObject != null)
                {
                    SetHookColor(_draggedHook.visualObject,
                        _draggedHook.isStrong ? strongHookColor : normalHookColor);
                }
            }

            _draggedHook = null;
        }

        private ActiveHook FindHookAtScreenPosition(Vector3 screenPos)
        {
            float closestDist = float.MaxValue;
            ActiveHook closest = null;

            foreach (ActiveHook hook in _hooks)
            {
                Vector3 screenPoint = mainCamera.WorldToScreenPoint(hook.currentPosition);
                float dist = Vector2.Distance(screenPos, new Vector2(screenPoint.x, screenPoint.y));

                // Check if within click radius (30 pixels)
                if (dist < 30f && dist < closestDist && screenPoint.z > 0)
                {
                    closestDist = dist;
                    closest = hook;
                }
            }

            return closest;
        }

        private void UpdateHookVisuals()
        {
            // Update hook visual positions if they've moved due to physics
            foreach (ActiveHook hook in _hooks)
            {
                if (hook.visualObject != null && hook != _draggedHook)
                {
                    // The hook position might have changed due to tissue movement
                    hook.visualObject.transform.position = hook.currentPosition;
                }
            }
        }

        private GameObject CreateHookVisual(Vector3 position, bool strong)
        {
            if (hookPrefab != null)
            {
                GameObject visual = Instantiate(hookPrefab, position, Quaternion.identity);
                visual.transform.SetParent(transform);
                SetHookColor(visual, strong ? strongHookColor : normalHookColor);
                return visual;
            }
            else
            {
                // Create default sphere visual
                GameObject visual = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                visual.transform.position = position;
                visual.transform.localScale = Vector3.one * 0.005f;
                visual.transform.SetParent(transform);

                // Remove collider
                Collider col = visual.GetComponent<Collider>();
                if (col != null) Destroy(col);

                SetHookColor(visual, strong ? strongHookColor : normalHookColor);
                return visual;
            }
        }

        private void SetHookColor(GameObject hookVisual, Color color)
        {
            if (hookVisual == null)
                return;

            Renderer renderer = hookVisual.GetComponent<Renderer>();
            if (renderer != null)
            {
                if (Application.isPlaying)
                {
                    renderer.material.color = color;
                }
                else
                {
                    renderer.sharedMaterial.color = color;
                }
            }
        }

        #endregion
    }
}

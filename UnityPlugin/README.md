# SkinFlaps Unity Integration Guide

This guide explains how to integrate the SkinFlaps soft tissue surgery simulator into Unity3D.

## Overview

SkinFlaps is a real-time soft tissue simulation system using Projective Dynamics physics. This Unity integration allows you to:

- Render and interact with deformable tissue meshes
- Perform surgical operations (incisions, suturing, undermining)
- Manipulate tissue using virtual hooks
- Build VR/AR surgical training applications

## Prerequisites

### Build Requirements

- **Windows 10/11** or **Linux** (Ubuntu 20.04+)
- **Visual Studio 2019/2022** (Windows) or **GCC 9+** (Linux)
- **CMake 3.17+**
- **Intel oneAPI Base Toolkit** (includes MKL and TBB)
  - Download: https://www.intel.com/content/www/us/en/developer/tools/oneapi/base-toolkit.html
- **CUDA Toolkit 11+** (optional, for GPU solver)

### Unity Requirements

- **Unity 2021.3 LTS** or later (2022.3 LTS recommended)
- **Universal Render Pipeline (URP)** or **High Definition Render Pipeline (HDRP)**
- For VR: **XR Interaction Toolkit 2.0+**

## Quick Start

### Step 1: Build the Native Plugin

```bash
# Clone the repository
git clone https://github.com/uwgraphics/SkinFlaps.git
cd SkinFlaps

# Create build directory
mkdir build && cd build

# Configure (Windows with Visual Studio 2022)
cmake -G "Visual Studio 17 2022" -A x64 ../UnityPlugin

# Build Release configuration
cmake --build . --config Release

# The DLL will be in: build/bin/Release/SkinFlapsCore.dll
```

For Linux:
```bash
cmake -DCMAKE_BUILD_TYPE=Release ../UnityPlugin
cmake --build .
# Output: build/libSkinFlapsCore.so
```

### Step 2: Setup Unity Project

1. Create a new Unity project with URP or HDRP

2. Copy the plugin files:
   ```
   Assets/
   ├── Plugins/
   │   └── SkinFlaps/
   │       ├── x86_64/
   │       │   ├── SkinFlapsCore.dll (Windows)
   │       │   └── libSkinFlapsCore.so (Linux)
   │       └── SkinFlapsCore.bundle (macOS)
   └── Scripts/
       └── SkinFlaps/
           ├── SkinFlapsNative.cs
           ├── SkinFlapsSimulator.cs
           └── SurgicalTools/
               ├── IncisionTool.cs
               ├── SutureTool.cs
               └── HookTool.cs
   ```

3. Copy the C# scripts from `UnityBridge/Scripts/SkinFlaps/` to `Assets/Scripts/SkinFlaps/`

4. Copy model files to StreamingAssets:
   ```
   Assets/
   └── StreamingAssets/
       └── SkinFlaps/
           ├── FacialFlaps.smd
           ├── Model/
           │   ├── *.obj
           │   └── *.jpg
           └── History/
   ```

### Step 3: Create a Simulation Scene

1. Create a new scene

2. Add an empty GameObject and name it "SkinFlapsSimulator"

3. Add the `SkinFlapsSimulator` component

4. Add a `MeshFilter` and `MeshRenderer` component

5. Configure the simulator:
   - Set **Model Path**: `SkinFlaps/FacialFlaps.smd`
   - Enable **Auto Start**

6. Add a material to the MeshRenderer (use a standard shader)

7. Press Play to start the simulation

## Component Reference

### SkinFlapsSimulator

Main simulation component that manages the physics and mesh synchronization.

**Inspector Properties:**

| Property | Description |
|----------|-------------|
| Model Path | Path to .smd model file (relative to StreamingAssets) |
| Data Directory | Path to data directory (empty = StreamingAssets) |
| Auto Start | Start simulation when scene loads |
| Physics Timestep | Fixed timestep for physics (default: 1/60) |
| Max Vertices | Maximum vertex buffer size |
| Max Triangles | Maximum triangle buffer size |

**Physics Properties:**

| Property | Description | Default |
|----------|-------------|---------|
| Low Tet Weight | Stiffness for smaller tetrahedra | 0.1 |
| High Tet Weight | Stiffness for larger tetrahedra | 1.0 |
| Strain Min/Max | Allowable strain range | 0.8 - 1.2 |
| Collision Weight | Collision constraint strength | 1000 |
| Hook Weight | Hook constraint strength | 500 |
| Suture Weight | Suture constraint strength | 1000 |

**Public Methods:**

```csharp
// Initialize simulation
simulator.Initialize();

// Perform incision
Vector3[] points = { start, end };
Vector3[] normals = { normal, normal };
simulator.PerformIncision(points, normals, startOpen: true, endOpen: true);

// Add/move/delete hooks
int hookId = simulator.AddHook(position, strong: false);
simulator.MoveHook(hookId, newPosition);
simulator.DeleteHook(hookId);

// Raycast against mesh
if (simulator.Raycast(ray, out RaycastHit hit, maxDistance))
{
    int material = simulator.GetTriangleMaterial(hit.triangleIndex);
}
```

### IncisionTool

Interactive tool for drawing incisions on the skin surface.

**Usage:**
```csharp
[SerializeField] private IncisionTool incisionTool;

void Start()
{
    incisionTool.OnIncisionCompleted += HandleIncisionCompleted;
}

public void ActivateIncisionMode()
{
    incisionTool.Activate();
}

void HandleIncisionCompleted(Vector3[] points, Vector3[] normals)
{
    Debug.Log($"Incision completed with {points.Length} points");
}
```

### SutureTool

Interactive tool for placing sutures to close incisions.

**Usage:**
```csharp
[SerializeField] private SutureTool sutureTool;

void Start()
{
    sutureTool.OnSuturePlaced += HandleSuturePlaced;
}

void HandleSuturePlaced(int sutureHandle)
{
    Debug.Log($"Suture placed: {sutureHandle}");
}
```

### HookTool

Interactive tool for grabbing and manipulating tissue.

**Usage:**
```csharp
[SerializeField] private HookTool hookTool;

void Update()
{
    // Toggle strong hooks
    if (Input.GetKeyDown(KeyCode.S))
    {
        hookTool.UseStrongHooks = !hookTool.UseStrongHooks;
    }
}
```

## Material IDs

The simulation uses material IDs to identify different tissue types:

| Material ID | Description |
|-------------|-------------|
| 2 | Skin surface (can receive hooks, start incisions) |
| 3 | Incision wall (can receive sutures) |
| 4 | Deep surface - subcutaneous |
| 5 | Deep surface - undermined |
| 6 | Deep surface - periosteal |

## VR Integration

### XR Interaction Toolkit Setup

1. Install XR Interaction Toolkit from Package Manager

2. Create VR hand controllers with XRDirectInteractor

3. Modify tools to use XR input:

```csharp
using UnityEngine.XR.Interaction.Toolkit;

public class VRHookTool : XRGrabInteractable
{
    [SerializeField] private SkinFlapsSimulator simulator;
    private int currentHookHandle = -1;

    protected override void OnSelectEntered(SelectEnterEventArgs args)
    {
        base.OnSelectEntered(args);

        // Place hook at interactor position
        Vector3 position = args.interactorObject.transform.position;
        currentHookHandle = simulator.AddHook(position, strong: false);
    }

    protected override void OnSelectExited(SelectExitEventArgs args)
    {
        base.OnSelectExited(args);

        if (currentHookHandle >= 0)
        {
            simulator.DeleteHook(currentHookHandle);
            currentHookHandle = -1;
        }
    }

    public override void ProcessInteractable(XRInteractionUpdateOrder.UpdatePhase updatePhase)
    {
        base.ProcessInteractable(updatePhase);

        if (isSelected && currentHookHandle >= 0)
        {
            // Move hook with hand
            simulator.MoveHook(currentHookHandle, transform.position);
        }
    }
}
```

## Performance Optimization

### Recommended Settings

| Platform | Max Vertices | Max Tets | Physics Rate |
|----------|--------------|----------|--------------|
| Desktop | 700,000 | 600,000 | 60 Hz |
| VR (Quest 2) | 300,000 | 200,000 | 72 Hz |
| Mobile | 100,000 | 80,000 | 30 Hz |

### Tips

1. **Reduce mesh resolution** for mobile/VR platforms
2. **Use LOD** for distant views
3. **Limit physics updates** when not interacting
4. **Pool mesh arrays** to avoid GC allocation

## Troubleshooting

### DLL Not Found

Make sure the DLL is in the correct platform folder:
- Windows x64: `Assets/Plugins/SkinFlaps/x86_64/SkinFlapsCore.dll`
- Linux: `Assets/Plugins/SkinFlaps/x86_64/libSkinFlapsCore.so`

Also ensure Intel MKL runtime DLLs are included.

### Physics Not Running

1. Check that Auto Start is enabled or call `Initialize()` manually
2. Verify model file path is correct
3. Check Console for error messages

### Mesh Not Visible

1. Ensure MeshRenderer has a valid material
2. Check that MeshFilter is assigned
3. Verify vertex/triangle counts in Stats display

### Poor Performance

1. Enable Physics Pause when not interacting
2. Reduce Max Vertices/Triangles
3. Check for GPU bottleneck (reduce mesh complexity)
4. Enable CUDA solver if available

## API Reference

See the C header file `UnityExports.h` for the complete native API documentation.

## License

SkinFlaps is licensed under BSD-3-Clause. See LICENSE file for details.

## Support

- GitHub Issues: https://github.com/uwgraphics/SkinFlaps/issues
- Documentation: See README.md in the repository root

## Citation

If you use SkinFlaps in your research, please cite:

```bibtex
@article{wang2022skinflaps,
  title={A computer based facial flaps simulator using projective dynamics},
  author={Wang, Qisi and others},
  year={2022}
}
```

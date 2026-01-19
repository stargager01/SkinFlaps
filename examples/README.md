# SkinFlaps Simple Model Examples

This directory contains simplified geometry models for beginners to learn and experiment with the SkinFlaps surgical simulator.

## Contents

| File | Description |
|------|-------------|
| `simple_rect_patch.obj` | A 4x4 subdivided rectangular patch (25 vertices, 32 triangles) |
| `simple_circle_patch.obj` | A circular patch with 3 rings (49 vertices, 80 triangles) |
| `simple_patch.smd` | Configuration file for the rectangular patch |
| `simple_circle.smd` | Configuration file for the circular patch |
| `SIMPLE_MODEL_CHECKLIST.md` | Step-by-step beginner's guide (Korean) |

## Quick Start

1. **Build SkinFlaps** following the main README instructions
2. **Launch SkinFlaps** executable
3. **Open Scene** (File > Open Scene) and select `simple_patch.smd`
4. **Run Simulation** and observe the physics behavior

## Model Specifications

### Rectangular Patch (`simple_rect_patch.obj`)
- **Size**: 2.0 x 2.0 units centered at origin
- **Grid**: 5x5 vertices (4x4 quads, triangulated)
- **Use Case**: Basic deformation, cutting, and suturing tests

### Circular Patch (`simple_circle_patch.obj`)
- **Radius**: 1.0 unit centered at origin
- **Structure**: Center point + 3 concentric rings with 16 segments
- **Use Case**: Radial flap simulations, circular wound closure

## Configuration Parameters

The `.smd` configuration files use simplified physics parameters optimized for these small models:

```json
{
    "minStrain": 0.85,      // Compression limit (lower = more compressible)
    "maxStrain": 1.20,      // Stretch limit (higher = more stretchable)
    "lowTetWeight": 400.0,  // Softness (lower = softer)
    "highTetWeight": 800.0, // Stiffness (higher = stiffer)
    "nTetSizeLevels": 3     // Multi-resolution levels
}
```

## Modifying Models

### Using Blender

1. Import: File > Import > Wavefront (.obj)
2. Edit in Edit Mode (Tab key)
3. Export: File > Export > Wavefront (.obj)
   - **Important**: Enable "Triangulate Faces" in export settings

### Creating New Configurations

1. Copy an existing `.smd` file
2. Update the `dynamicObjects` section with your new model filename
3. Adjust physics parameters as needed

## Learning Resources

- [SkinFlaps YouTube Tutorial](https://youtu.be/xuKLgMS5gzk)
- [Cleft Lip Tutorial](https://youtu.be/CzBiVJ5Q508)
- [Academic Paper](https://doi.org/10.1016/j.cmpb.2022.106730)

## Contributing

If you create interesting model variations or discover useful parameter settings, please share them via GitHub Issues or Pull Requests!

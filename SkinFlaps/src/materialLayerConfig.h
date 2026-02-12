////////////////////////////////////////////////////////////////////////////
// File: materialLayerConfig.h
// Purpose: Configurable material layer ID mapping for surgical simulation.
//   Extracted from bccTetScene.h to allow inclusion by cut/undermine classes
//   without circular dependency.
////////////////////////////////////////////////////////////////////////////

#ifndef __MATERIAL_LAYER_CONFIG__
#define __MATERIAL_LAYER_CONFIG__

/// @brief Configurable material layer ID mapping, loaded from .smd scene file.
/// Allows different anatomies (face, shoulder, etc.) to define their own tissue layer semantics.
/// Default values match the hardcoded facial tissue IDs used throughout the codebase.
struct materialLayerConfig {
	int boundary = 1;              ///< Blank/peripheral boundary
	int skinSurface = 2;           ///< Top skin surface (textured)
	int incisionEdge = 3;          ///< Incised skin edge (procedural dermis/fat)
	int subcutaneous = 4;          ///< Flap bottom / subcutaneous layer
	int deepBed = 5;               ///< Deep tissue bed surface
	int muscle = 6;                ///< Deep cut muscle layer
	int periosteum = 7;            ///< Periosteum / bone surface, not undermined
	int periosteumUndermined = 8;  ///< Periosteum, undermined
	int undermineMarker = 10;      ///< Visual marker for undermined tissue

	// Extension fields for non-facial anatomies (not used in facial model).
	// A value of -1 indicates the layer is not present in the current anatomy.
	int tendon = -1;               ///< Tendon layer (e.g., rotator cuff)
	int jointCapsule = -1;         ///< Joint capsule / labrum
	int boneSurface = -1;          ///< Bone surface (e.g., humeral head)
	int arthroscopicPortal = -1;   ///< Arthroscopic entry portal
};

#endif // __MATERIAL_LAYER_CONFIG__

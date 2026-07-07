# 3D anatomy model assets

Place a de-identified mandible or jaw surface model in this directory to replace
the procedural demo model in the 2D-3D spatial evidence panel.

The intended workflow is compatible with outputs from tools such as 3D Slicer:
segment CT/CBCT data externally, export a surface model, then load that model in
the frontend as a spatial reference for ICG ROI evidence. The web frontend does
not embed 3D Slicer itself or provide surgical navigation.

Supported filenames, in priority order:

1. `mandible.glb`
2. `mandible.gltf`
3. `mandible.stl`

Optional panoramic/scout reference image:

- `panoramic-reference.jpg`

The model should be de-identified and suitable for research or competition
prototype display. Do not place raw DICOM, NIfTI, or patient-identifying data in
this directory.

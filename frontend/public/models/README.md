# 3D Anatomy Model Assets

This directory is reserved for optional local 3D anatomy assets used by the
2D-3D spatial evidence panel. Large model files are intentionally not committed
to Git.

Recommended workflow:

1. Segment a de-identified CT/CBCT case in an external tool such as 3D Slicer.
2. Export a surface model to GLB, GLTF, or STL.
3. Place the local file here only for local platform validation.
4. Record source, license, de-identification status, file size, checksum, and
   intended use in a separate traceable manifest before sharing with teammates.

Supported local filenames, in priority order:

1. `mandible.glb`
2. `mandible.gltf`
3. `mandible.stl`

Optional local reference image:

- `panoramic-reference.jpg`

Do not place raw DICOM, NIfTI, patient-identifying data, or unlicensed public
dataset models in this directory. The 3D view is a spatial reference layer for
ICG ROI evidence and is not surgical navigation, automatic diagnosis, or a
precise resection boundary.

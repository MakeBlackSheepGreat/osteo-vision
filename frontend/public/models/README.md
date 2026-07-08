# 3D Anatomy Model Assets

This directory is reserved for optional local 3D anatomy assets used by the
2D-3D spatial evidence panel. Large model files are intentionally not committed
to Git.

Recommended workflow:

1. Segment a de-identified CT/CBCT case in an external tool such as 3D Slicer.
2. Export a surface model to GLB, GLTF, or STL.
3. If the model is exported from 3D Slicer, record the Slicer scene/source case,
   segmentation method, exported segment name, coordinate space, and whether any
   registration transform has been applied.
4. Place the local file here only for local platform validation.
5. Record source, license, de-identification status, file size, checksum,
   registration status, registration error if measured, physician review state,
   and intended use in a separate traceable manifest before sharing with
   teammates.

Recommended `three_d_evidence` fields for a case/run response:

- `model_path`, `model_format`, `model_file_name`, `model_source`
- `exported_from`, `dicom_series_uid`, `coordinate_space`, `transform_path`
- `segmentation_source`, `segmentation_review_status`
- `registration_status`, `registration_method`, `registration_error_mm`
- `fiducial_count`, `surface_point_count`
- `registration_markups`: optional paired landmark rows with `id`, `label`,
  `source_label`, `target_label`, `source_point_mm`, `target_point_mm`,
  `residual_mm`, and `status`
- `transform_chain`: optional ordered transform steps with `name`,
  `from_space`, `to_space`, `path`, `error_mm`, and `status`
- `doctor_review_status`, `navigation_ready`, `boundary_note`

Only set `navigation_ready=true` after the coordinate transform, point or
surface registration evidence, measured error, and physician review boundary
are all traceable. Otherwise the frontend will keep the panel in reference /
non-navigation mode.

For Slicer/BoneReconstructionPlanner-derived work, keep the markups and
transform chain close to the original planning semantics: DICOM/CBCT volume,
mandible/fibula segmentations, mandibular curve, cut planes, fibula line,
mandible-to-fibula transforms, exported STL/GLB models, and any point/surface
registration residuals. The frontend may display these as a Slicer-style
planning workbench, but it must still label incomplete or unreviewed data as
missing/reference and avoid navigation wording.

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

When no case-level 3D evidence manifest is available, the frontend must treat
the model as an unregistered reference. Candidate regions may be shown only as
2D-derived illustrative projections until a coordinate transform and error
record are available.

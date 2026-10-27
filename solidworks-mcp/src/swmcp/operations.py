"""Every catalog operation as a typed method. GENERATED: do not edit by hand.

Regenerate with ``uv run solidworks-mcp --write-artifacts``. ``pytest`` fails while
this file is stale, so it cannot quietly fall behind the ``@op`` handlers it mirrors.

Each method takes its arguments as keywords, as a dict, or as the operation's args
model, and returns the operation's result model. All of them go through
:meth:`swmcp.library.SolidWorks.call`, and from there through the same dispatch
pipeline the MCP server uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel

    from swmcp.schemas.assembly import (
        AsmComponentSetArgs,
        AsmComponentSetResult,
        AsmInsertArgs,
        AsmInsertResult,
        AsmTreeArgs,
        AsmTreeResult,
    )
    from swmcp.schemas.batch import BatchExportArgs, BatchExportResult
    from swmcp.schemas.bom import BomExportArgs, BomExportResult
    from swmcp.schemas.discovery import (
        ApiBatchInvokeArgs,
        ApiBatchInvokeResult,
        ApiInvokeArgs,
        ApiInvokeResult,
        ApiInvokeWriteArgs,
        ApiInvokeWriteResult,
        ApiSearchArgs,
        ApiSearchResult,
    )
    from swmcp.schemas.document import (
        DocActivateArgs,
        DocActivateResult,
        DocCloseArgs,
        DocCloseResult,
        DocListArgs,
        DocListResult,
        DocNewArgs,
        DocNewResult,
        DocOpenArgs,
        DocOpenResult,
        DocRebuildArgs,
        DocRebuildResult,
        DocSaveArgs,
        DocSaveResult,
        DocUndoArgs,
        DocUndoResult,
    )
    from swmcp.schemas.drawing import (
        DrawingAnnotateModelArgs,
        DrawingAnnotateModelResult,
        DrawingExportArgs,
        DrawingExportResult,
        DrawingListArgs,
        DrawingListResult,
        DrawingNewArgs,
        DrawingNewResult,
        DrawingNoteAddArgs,
        DrawingNoteAddResult,
        DrawingReviewArgs,
        DrawingReviewResult,
        DrawingSheetAddArgs,
        DrawingSheetAddResult,
        DrawingTableAddArgs,
        DrawingTableAddResult,
        DrawingViewAddArgs,
        DrawingViewAddResult,
    )
    from swmcp.schemas.exchange import ExportArgs, ExportResult, ImportArgs, ImportResult
    from swmcp.schemas.feature import (
        BodyListArgs,
        BodyListResult,
        ChamferArgs,
        DatumAxisCreateArgs,
        DatumAxisCreateResult,
        DatumCsysCreateArgs,
        DatumCsysCreateResult,
        DatumListArgs,
        DatumListResult,
        DatumPlaneCreateArgs,
        DatumPlaneCreateResult,
        DatumPointCreateArgs,
        DatumPointCreateResult,
        DraftArgs,
        DraftResult,
        EdgeFeatureResult,
        ExtrudeArgs,
        ExtrudeResult,
        FeatureDeleteArgs,
        FeatureDeleteResult,
        FeatureEditArgs,
        FeatureEditResult,
        FeatureListArgs,
        FeatureListResult,
        FilletArgs,
        HoleArgs,
        HoleResult,
        LoftArgs,
        LoftResult,
        MeasureArgs,
        MeasureResult,
        PatternArgs,
        PatternResult,
        RevolveArgs,
        RevolveResult,
        SweepArgs,
        SweepResult,
    )
    from swmcp.schemas.mate import (
        InterferenceCheckArgs,
        InterferenceCheckResult,
        MateAddArgs,
        MateAddResult,
        MateDeleteArgs,
        MateDeleteResult,
        MateDofArgs,
        MateDofResult,
        MateEditArgs,
        MateEditResult,
        MateListArgs,
        MateListResult,
        MateProbeArgs,
        MateProbeResult,
    )
    from swmcp.schemas.material import (
        MaterialGetArgs,
        MaterialGetResult,
        MaterialSetArgs,
        MaterialSetResult,
    )
    from swmcp.schemas.parameter import (
        ConfigActivateArgs,
        ConfigActivateResult,
        ConfigCreateArgs,
        ConfigCreateResult,
        ConfigDeleteArgs,
        ConfigDeleteResult,
        ConfigListArgs,
        ConfigListResult,
        EquationListArgs,
        EquationListResult,
        EquationSetArgs,
        EquationSetResult,
        ParameterTableExportArgs,
        ParameterTableExportResult,
        ParameterTableImportArgs,
        ParameterTableImportResult,
        PropertyListArgs,
        PropertyListResult,
        PropertySetArgs,
        PropertySetResult,
    )
    from swmcp.schemas.reference import (
        ProbeFacesArgs,
        ProbeFacesResult,
        ProbeRayArgs,
        ProbeRayResult,
        RefCaptureArgs,
        RefCaptureResult,
        RefResolveArgs,
        RefResolveResult,
        SelectionGetArgs,
        SelectionGetResult,
        SelectionSetArgs,
        SelectionSetResult,
    )
    from swmcp.schemas.review import SafeExecuteArgs, SafeExecuteResult
    from swmcp.schemas.review_checks import (
        ReviewHolesArgs,
        ReviewHolesResult,
        ReviewInspectArgs,
        ReviewInspectResult,
        ReviewReportArgs,
        ReviewReportResult,
        ReviewValidateArgs,
        ReviewValidateResult,
    )
    from swmcp.schemas.safety import (
        AuditTailArgs,
        AuditTailResult,
        CheckpointCreateArgs,
        CheckpointCreateResult,
        CheckpointListArgs,
        CheckpointListResult,
        CheckpointRestoreArgs,
        CheckpointRestoreResult,
        ExplainErrorArgs,
        ExplainErrorResult,
        PathPolicyArgs,
        PathPolicyResult,
    )
    from swmcp.schemas.sketch import (
        DimensionListArgs,
        DimensionListResult,
        DimensionSetArgs,
        DimensionSetResult,
        SketchAddDimensionsArgs,
        SketchAddDimensionsResult,
        SketchAddGeometryArgs,
        SketchAddGeometryResult,
        SketchAddRelationsArgs,
        SketchAddRelationsResult,
        SketchAutoDimensionArgs,
        SketchAutoDimensionResult,
        SketchConvertEntitiesArgs,
        SketchConvertEntitiesResult,
        SketchCreateArgs,
        SketchCreateResult,
        SketchDeleteArgs,
        SketchDeleteResult,
        SketchDeriveArgs,
        SketchDeriveResult,
        SketchDiagnoseArgs,
        SketchDiagnoseResult,
        SketchExitArgs,
        SketchExitResult,
        SketchListArgs,
        SketchListResult,
        SketchModifyArgs,
        SketchModifyResult,
        SketchSetConstructionArgs,
        SketchSetConstructionResult,
        SketchStartArgs,
        SketchStartResult,
        SketchTextArgs,
        SketchTextResult,
    )
    from swmcp.schemas.solid import (
        PrimitiveArgs,
        PrimitiveResult,
        RibArgs,
        RibResult,
        ShellArgs,
        ShellResult,
    )
    from swmcp.schemas.surface import SurfaceCreateArgs, SurfaceCreateResult
    from swmcp.schemas.system import (
        CapabilitiesArgs,
        CapabilitiesResult,
        ConnectArgs,
        ConnectResult,
        HealthArgs,
        HealthResult,
        ResolveNamesArgs,
        ResolveNamesResult,
        SystemInfoArgs,
        SystemInfoResult,
    )
    from swmcp.schemas.view import (
        AppearanceGetArgs,
        AppearanceGetResult,
        AppearanceResult,
        AppearanceSetArgs,
        ViewCaptureArgs,
        ViewCaptureResult,
        ViewSetArgs,
        ViewSetResult,
        VisibilitySetArgs,
        VisibilitySetResult,
    )


class Operations:
    """Mixin: 115 operations, each a thin call into :meth:`call`."""

    __slots__ = ()

    def call(
        self,
        name: str,
        args: BaseModel | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError

    def api_batch_invoke(
        self,
        args: ApiBatchInvokeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ApiBatchInvokeResult:
        """Read several SOLIDWORKS API members in one round trip, applying the same
        read-only allowlist to each and reporting failures per call.

        ``sw_api_batch_invoke``: tier advanced, read, document any.

        Arguments (keywords, a dict, or ``ApiBatchInvokeArgs``):
            document: optional. Which document to act on.
            calls: required.
            stop_on_error: default False. Abandon the batch at the first failure.
        """
        return self.call("sw_api_batch_invoke", args, **kwargs)

    def api_invoke(
        self,
        args: ApiInvokeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ApiInvokeResult:
        """Read a SOLIDWORKS API member on an allowlisted object. This is a research and
        diagnostics tool, not a substitute for the typed operations, and it refuses any
        member that would change state.

        ``sw_api_invoke``: tier advanced, read, document any.

        Arguments (keywords, a dict, or ``ApiInvokeArgs``):
            target: default 'doc'.
            ref: default None. Required when target is 'ref': the entity to call on.
            member: required. Member name to read or call.
            args: optional. Arguments, JSON scalars only.
            document: optional. Which document to act on.
        """
        return self.call("sw_api_invoke", args, **kwargs)

    def api_invoke_write(
        self,
        args: ApiInvokeWriteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ApiInvokeWriteResult:
        """Call a state-changing SOLIDWORKS API member directly. Development only: it is
        gated behind SWMCP_ENABLE_LOWLEVEL_WRITE, requires confirmation, is checkpointed
        and audited, and its effect is not verified beyond a before and after snapshot.

        ``sw_api_invoke_write``: tier debug, destructive mutation, confirm, document
        any.

        Arguments (keywords, a dict, or ``ApiInvokeWriteArgs``):
            target: default 'doc'.
            ref: default None. Required when target is 'ref': the entity to call on.
            member: required. Member name to read or call.
            args: optional. Arguments, JSON scalars only.
            document: optional. Which document to act on.
            confirm: required. Must be true.
        """
        return self.call("sw_api_invoke_write", args, **kwargs)

    def api_search(
        self,
        args: ApiSearchArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ApiSearchResult:
        """Search the SOLIDWORKS constants registered on this machine by name, so a caller
        can find the enum member a low-level call needs without guessing its value.

        ``sw_api_search``: tier extended, read, document none.

        Arguments (keywords, a dict, or ``ApiSearchArgs``):
            query: default ''. Text matched against names.
            kind: default 'any'.
            limit: default 40.
        """
        return self.call("sw_api_search", args, **kwargs)

    def appearance_get(
        self,
        args: AppearanceGetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AppearanceGetResult:
        """Read the colour, transparency, and shading of the document, a body, a feature,
        or a face, reporting whether the value is its own or inherited.

        ``sw_appearance_get``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``AppearanceGetArgs``):
            document: optional. Which document to act on.
            target: default 'document'.
            body_name: default None.
            feature_name: default None.
            face_ref: default None.
        """
        return self.call("sw_appearance_get", args, **kwargs)

    def appearance_set(
        self,
        args: AppearanceSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AppearanceResult:
        """Set the colour, transparency, and shading of the document, a body, a feature, or
        a face, changing only the values given and reading the result back.

        ``sw_appearance_set``: tier core, side effect, document part_or_assembly.

        Arguments (keywords, a dict, or ``AppearanceSetArgs``):
            document: optional. Which document to act on.
            target: default 'document'. What the appearance is applied to.
            body_name: default None. Required when target is 'body'.
            feature_name: default None. Required when target is 'feature'.
            face_ref: default None. Entity reference to a face; required when target is
                'face'.
            color: default None. RGB, each 0.0-1.0.
            ambient: default None.
            diffuse: default None.
            specular: default None.
            shininess: default None.
            transparency: default None. 0 is opaque, 1 is fully transparent.
            emission: default None.
        """
        return self.call("sw_appearance_set", args, **kwargs)

    def asm_component_set(
        self,
        args: AsmComponentSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AsmComponentSetResult:
        """Change one component's suppression, fixed state, visibility, or referenced
        configuration, reading each back rather than trusting the call.

        ``sw_asm_component_set``: tier core, mutation, document assembly.

        Arguments (keywords, a dict, or ``AsmComponentSetArgs``):
            document: optional. Which document to act on.
            component_name: required. Component instance name, e.g.
            suppression: default None. Suppress, make lightweight, or resolve the
                component.
            fixed: default None. Fix in place, or float it.
            visible: default None. Show or hide it.
            configuration: default None. Switch which configuration this instance
                references.
        """
        return self.call("sw_asm_component_set", args, **kwargs)

    def asm_insert(
        self,
        args: AsmInsertArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AsmInsertResult:
        """Insert a part or subassembly into the open assembly at a position, with an
        optional configuration and fixed state, verified by finding it in the tree.

        ``sw_asm_insert``: tier core, mutation, document assembly.

        Arguments (keywords, a dict, or ``AsmInsertArgs``):
            document: optional. Which document to act on.
            component_path: required. Full path to the .SLDPRT or .SLDASM to insert.
            at: optional. Where to place the component's origin.
            configuration: default None. Configuration of the inserted component.
            fixed: default False. Fix the component in place.
        """
        return self.call("sw_asm_insert", args, **kwargs)

    def asm_tree(
        self,
        args: AsmTreeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AsmTreeResult:
        """List the assembly's components with path, configuration, quantity, suppression,
        lightweight, hidden, fixed, envelope, virtual, and broken-reference state.

        ``sw_asm_tree``: tier core, read, document assembly.

        Arguments (keywords, a dict, or ``AsmTreeArgs``):
            document: optional. Which document to act on.
            top_level_only: default False. List only the top level rather than walking
                subassemblies.
            max_depth: default 16. Guard against a pathological nesting depth.
        """
        return self.call("sw_asm_tree", args, **kwargs)

    def audit_tail(
        self,
        args: AuditTailArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> AuditTailResult:
        """Read the most recent entries from the append-only write audit, including the
        checkpoint each mutation was covered by.

        ``sw_audit_tail``: tier extended, read, document none.

        Arguments (keywords, a dict, or ``AuditTailArgs``):
            limit: default 20.
            tool: default None. Only entries for this operation.
            failures_only: default False.
        """
        return self.call("sw_audit_tail", args, **kwargs)

    def batch_export(
        self,
        args: BatchExportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> BatchExportResult:
        """Export many documents, configurations, sheets, and formats in one call, writing
        a JSON manifest that names every file with its size, timestamp, and SHA-256, and
        reporting each requested output as written, failed, or skipped.

        ``sw_batch_export``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``BatchExportArgs``):
            items: required. The documents to export, in the order they will be
                processed.
            output_dir: required. Directory for every written file and, by default, the
                manifest.
            manifest_path: default None. Where to write the JSON manifest.
            overwrite: default 'version'. Applied to every written file and to the
                manifest.
            continue_on_error: default True. Keep going when one output fails.
            close_opened: default True. Close documents this call opened.
            stop_when_strained: default True. Stop between items once SOLIDWORKS has
                reached the measured point where calls hang rather than fail.
            stl_quality: default 'fine'. Mesh tessellation quality for STL, 3MF, OBJ,
                and PLY.
            stl_binary: default True. Write STL as binary rather than ASCII.
            mesh_unit: default 'mm'. Unit written into mesh formats, which carry no unit
                of their own.
            step_protocol: default 'ap214'. STEP application protocol.
        """
        return self.call("sw_batch_export", args, **kwargs)

    def body_list(
        self,
        args: BodyListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> BodyListResult:
        """List the solid and surface bodies with their owning features, material,
        visibility, face and edge counts, and mass properties.

        ``sw_body_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``BodyListArgs``):
            document: optional. Which document to act on.
            include_surfaces: default True.
        """
        return self.call("sw_body_list", args, **kwargs)

    def body_primitive(
        self,
        args: PrimitiveArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> PrimitiveResult:
        """Build a box, cylinder, sphere, cone, frustum, torus, wedge, or prism as an
        ordinary sketch and boss, and check the measured volume against the closed-form
        volume its dimensions imply.

        ``sw_body_primitive``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``PrimitiveArgs``):
            document: optional. Which document to act on.
            kind: required. Which primitive to build.
            plane: default 'front'. Standard plane the defining sketch is drawn on.
            at: optional. Where the primitive is centred in the sketch plane.
            width: default None. Box and wedge: X size.
            depth: default None. Box and wedge: Y size.
            height: default None. Extrusion or revolve height for every solid that has
                one.
            radius: default None. Cylinder, sphere, cone base, torus tube centre, prism.
            top_radius: default None. Frustum only: the radius at the top.
            tube_radius: default None. Torus only: the radius of the tube itself.
            sides: default None. Prism only: how many sides.
            name: default None.
        """
        return self.call("sw_body_primitive", args, **kwargs)

    def bom_export(
        self,
        args: BomExportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> BomExportResult:
        """Write a component and property bill of materials to CSV, with a traceability
        matrix naming every instance behind each quantity and whether each property
        value came from the configuration or the file. Labelled a precursor, always.

        ``sw_bom_export``: tier core, side effect, document assembly.

        Arguments (keywords, a dict, or ``BomExportArgs``):
            document: optional. Which document to act on.
            output_path: required. CSV destination for the bill of materials.
            matrix_path: default None. CSV destination for the traceability matrix, one
                row per component instance.
            matrix: default True. Write the traceability matrix.
            shape: default 'parts_only'. 'parts_only' rolls every part in the tree up by
                part number, 'top_level_only' lists only the assembly's direct children,
                'indented' keeps the levels and numbers them 1, 1.1, 1.2, 2.
            properties: default None. Property columns, in this order.
            configuration: default None. Activate this configuration of the assembly
                first, and restore the previous one afterwards.
            include_suppressed: default False. Count suppressed components in the
                quantities.
            include_excluded: default False. Count components flagged 'Exclude from bill
                of materials'.
            max_depth: default 16. How far down the component tree to walk.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
        """
        return self.call("sw_bom_export", args, **kwargs)

    def capabilities(
        self,
        args: CapabilitiesArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> CapabilitiesResult:
        """Probe what this installation can actually do — edition, add-ins, type libraries,
        and template availability — so a caller can branch on evidence rather than
        assuming a feature exists.

        ``sw_capabilities``: tier extended, read, document none.
        """
        return self.call("sw_capabilities", args, **kwargs)

    def checkpoint_create(
        self,
        args: CheckpointCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> CheckpointCreateResult:
        """Snapshot a document so a later change can be rolled back. Prefers a SaveAs-Copy
        so unsaved session state is captured, and reports which method was used.

        ``sw_checkpoint_create``: tier core, side effect, document any.

        Arguments (keywords, a dict, or ``CheckpointCreateArgs``):
            document: optional. Which document to act on.
            force: default True. Take a snapshot even if a recent one exists (bypasses
                the debounce).
            tag: default ''. Optional label folded into the checkpoint filename.
        """
        return self.call("sw_checkpoint_create", args, **kwargs)

    def checkpoint_list(
        self,
        args: CheckpointListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> CheckpointListResult:
        """List the snapshots available for a document, newest first, with sizes and times.

        ``sw_checkpoint_list``: tier core, read, document any.

        Arguments (keywords, a dict, or ``CheckpointListArgs``):
            document: optional. Which document to act on.
            limit: default 20.
        """
        return self.call("sw_checkpoint_list", args, **kwargs)

    def checkpoint_restore(
        self,
        args: CheckpointRestoreArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> CheckpointRestoreResult:
        """Restore a document from a checkpoint, overwriting its current contents. A
        snapshot of the present state is staged first, so restoring by mistake is itself
        reversible.

        ``sw_checkpoint_restore``: tier core, destructive mutation, confirm, document
        none.

        Arguments (keywords, a dict, or ``CheckpointRestoreArgs``):
            checkpoint_path: required. Checkpoint file to restore from.
            target_path: default None. Document to overwrite.
            confirm: required. Must be true.
            close_open_document: default True. Close the document in SOLIDWORKS first.
            reopen: default True. Reopen the document after restoring.
        """
        return self.call("sw_checkpoint_restore", args, **kwargs)

    def config_activate(
        self,
        args: ConfigActivateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ConfigActivateResult:
        """Switch the active configuration and read back which one is active afterwards,
        since a mis-typed name leaves the previous configuration in place.

        ``sw_config_activate``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``ConfigActivateArgs``):
            document: optional. Which document to act on.
            name: required.
            rebuild: default True.
        """
        return self.call("sw_config_activate", args, **kwargs)

    def config_create(
        self,
        args: ConfigCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ConfigCreateResult:
        """Create a configuration, optionally derived from an existing one, and read the
        configuration list back to confirm it exists.

        ``sw_config_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``ConfigCreateArgs``):
            document: optional. Which document to act on.
            name: required. Name for the new configuration.
            parent: default None. Create as a derived configuration of this one.
            comment: default ''.
            description: default ''.
            alternate_name: default ''.
            suppress_new_features: default False. New features are suppressed in this
                configuration by default.
            activate: default True. Make it the active configuration.
        """
        return self.call("sw_config_create", args, **kwargs)

    def config_delete(
        self,
        args: ConfigDeleteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ConfigDeleteResult:
        """Delete a configuration. Destructive: the configuration's own dimension values
        and property overrides go with it, so it requires confirmation.

        ``sw_config_delete``: tier extended, destructive mutation, confirm, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``ConfigDeleteArgs``):
            document: optional. Which document to act on.
            name: required.
            confirm: required. Must be true.
        """
        return self.call("sw_config_delete", args, **kwargs)

    def config_list(
        self,
        args: ConfigListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ConfigListResult:
        """List the document's configurations with their parent, derived state, rebuild
        state, and which one is active, so a variant can be addressed by name.

        ``sw_config_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``ConfigListArgs``):
            document: optional. Which document to act on.
            include_properties: default False. Include each configuration's custom
                properties.
        """
        return self.call("sw_config_list", args, **kwargs)

    def connect(
        self,
        args: ConnectArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ConnectResult:
        """Attach to a running SOLIDWORKS instance, optionally launching one. Reports the
        version, the ProgID that worked, and the active document.

        ``sw_connect``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``ConnectArgs``):
            start_if_missing: default False. Launch SOLIDWORKS if no instance is
                running.
            visible: default True. Show the SOLIDWORKS window when launching it.
        """
        return self.call("sw_connect", args, **kwargs)

    def datum_axis_create(
        self,
        args: DatumAxisCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DatumAxisCreateResult:
        """Create a reference axis from one line, two planes, two points, a cylindrical
        face, or a point and a plane, and read back the axis that was actually made.

        ``sw_datum_axis_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``DatumAxisCreateArgs``):
            document: optional. Which document to act on.
            method: required. How the axis is defined.
            refs: optional. Reference entities.
            standard_planes: optional. Standard planes used as references, e.g.
            auto_size: default True. Let SOLIDWORKS size the axis to the surrounding
                geometry.
            name: default None. Rename the axis after creating it.
        """
        return self.call("sw_datum_axis_create", args, **kwargs)

    def datum_csys_create(
        self,
        args: DatumCsysCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DatumCsysCreateResult:
        """Create a coordinate system from an origin and axis references, and return the
        transform SOLIDWORKS actually built: rotation, origin position, and scale.

        ``sw_datum_csys_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``DatumCsysCreateArgs``):
            document: optional. Which document to act on.
            origin: default None. Vertex, sketch point, or reference point placed at the
                system's origin.
            x_axis: default None. Edge, axis, or line for +X.
            y_axis: default None. Edge, axis, or line for +Y.
            z_axis: default None. Edge, axis, or line for +Z.
            flip_x: default False. Reverse the resolved X direction.
            flip_y: default False. Reverse the resolved Y direction.
            flip_z: default False. Reverse the resolved Z direction.
            name: default None. Rename the coordinate system afterwards.
        """
        return self.call("sw_datum_csys_create", args, **kwargs)

    def datum_list(
        self,
        args: DatumListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DatumListResult:
        """List the document's reference geometry — planes, axes, points, and coordinate
        systems — with their locale-invariant type tokens and capture-ready references.

        ``sw_datum_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``DatumListArgs``):
            document: optional. Which document to act on.
        """
        return self.call("sw_datum_list", args, **kwargs)

    def datum_plane_create(
        self,
        args: DatumPlaneCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DatumPlaneCreateResult:
        """Create a reference plane by offset, angle, midplane, three points, or tangency,
        and read back the plane that was actually created.

        ``sw_datum_plane_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``DatumPlaneCreateArgs``):
            document: optional. Which document to act on.
            method: required. How the plane is defined; each method needs a different
                reference count.
            refs: optional. Reference entities, or use standard_plane for a standard
                plane.
            standard_plane: default None. Use a standard plane as the single reference.
            distance: default None. Offset distance for 'offset'.
            angle: default None. Angle for 'angle'.
            flip: default False. Reverse the offset or angle direction.
            name: default None. Rename the plane after creating it.
        """
        return self.call("sw_datum_plane_create", args, **kwargs)

    def datum_point_create(
        self,
        args: DatumPointCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DatumPointCreateResult:
        """Create reference points at a face centre, an edge centre, an intersection, a
        projected vertex, a sketch point, or spaced along a curve by distance,
        percentage, or even division.

        ``sw_datum_point_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``DatumPointCreateArgs``):
            document: optional. Which document to act on.
            method: required. What geometry the point is derived from.
            refs: optional. The edges, faces, vertices, or sketch points the point is
                built on.
            along_curve: default 'evenly'. For 'along_curve': place by distance, by
                percentage, or evenly spaced.
            distance: default None. Distance along the curve when along_curve is
                'distance'.
            percent: default None. Percentage along the curve when along_curve is
                'percentage'.
            count: default 1. How many points to distribute when along_curve is
                'evenly'.
            name: default None. Rename the point feature afterwards.
        """
        return self.call("sw_datum_point_create", args, **kwargs)

    def dimension_list(
        self,
        args: DimensionListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DimensionListResult:
        """List driving dimensions with their names and values in the requested unit,
        optionally as they stand in one configuration, so a parametric change can
        address a dimension by name rather than by position.

        ``sw_dimension_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``DimensionListArgs``):
            document: optional. Which document to act on.
            sketch_name: default None. Restrict to one sketch.
            unit: default 'mm'. Unit to report lengths in.
            configuration: default None. Read each dimension's value in this
                configuration rather than the active one.
        """
        return self.call("sw_dimension_list", args, **kwargs)

    def dimension_set(
        self,
        args: DimensionSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DimensionSetResult:
        """Change a named driving dimension in the active configuration, in all of them, or
        in named ones, reporting the value before and after plus any rebuild errors the
        change caused.

        ``sw_dimension_set``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``DimensionSetArgs``):
            document: optional. Which document to act on.
            name: required. Dimension name, e.g.
            value: required. New value.
            rebuild: default True. Rebuild after changing the value.
            configuration_scope: default 'all'. Which configurations take the new value.
            configurations: optional. Required when configuration_scope is 'specify'.
        """
        return self.call("sw_dimension_set", args, **kwargs)

    def doc_activate(
        self,
        args: DocActivateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocActivateResult:
        """Make an open document the active one, addressed by path or title. An ambiguous
        title is refused rather than resolved arbitrarily.

        ``sw_doc_activate``: tier core, side effect, document any.

        Arguments (keywords, a dict, or ``DocActivateArgs``):
            document: optional. Which document to act on.
        """
        return self.call("sw_doc_activate", args, **kwargs)

    def doc_close(
        self,
        args: DocCloseArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocCloseResult:
        """Close an open document. The handling of unsaved changes must be stated
        explicitly, because closing a dirty document silently would discard work.

        ``sw_doc_close``: tier core, destructive mutation, confirm, document any.

        Arguments (keywords, a dict, or ``DocCloseArgs``):
            document: optional. Which document to act on.
            save_first: required. What to do about unsaved changes.
            confirm: required. Must be true.
        """
        return self.call("sw_doc_close", args, **kwargs)

    def doc_list(
        self,
        args: DocListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocListResult:
        """List every open document with its type, path, saved and dirty state, active
        configuration, and whether it can be checkpointed.

        ``sw_doc_list``: tier core, read, document none.
        """
        return self.call("sw_doc_list", args, **kwargs)

    def doc_new(
        self,
        args: DocNewArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocNewResult:
        """Create a part, assembly, or drawing from an explicit template or the SOLIDWORKS
        default for that type. Reports which template was actually used.

        ``sw_doc_new``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``DocNewArgs``):
            doc_type: required. Which kind of document to create.
            template_path: default None. Explicit template file.
            activate: default True. Make the new document active.
        """
        return self.call("sw_doc_new", args, **kwargs)

    def doc_open(
        self,
        args: DocOpenArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocOpenResult:
        """Open a SOLIDWORKS document from disk, decoding the load errors and warnings into
        names and remediation rather than returning raw status integers.

        ``sw_doc_open``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``DocOpenArgs``):
            path: required. Full path of the document to open.
            open_read_only: default False. Open without taking a write lock on the file.
            silent: default True. Suppress SOLIDWORKS dialogs during load.
            configuration: default ''. Configuration to activate on open.
        """
        return self.call("sw_doc_open", args, **kwargs)

    def doc_rebuild(
        self,
        args: DocRebuildArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocRebuildResult:
        """Rebuild the document and report which features ended up in error or warning, so
        a rebuild that 'succeeded' with a broken tree is not mistaken for success.

        ``sw_doc_rebuild``: tier core, mutation, document any.

        Arguments (keywords, a dict, or ``DocRebuildArgs``):
            document: optional. Which document to act on.
            force: default False. Rebuild every feature, not only what is out of date.
            top_level_only: default False. For assemblies, skip rebuilding components.
        """
        return self.call("sw_doc_rebuild", args, **kwargs)

    def doc_save(
        self,
        args: DocSaveArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocSaveResult:
        """Save a document in place or to a new path, applying the overwrite policy so an
        existing deliverable is never replaced silently, and verifying the file on disk.

        ``sw_doc_save``: tier core, side effect, document any.

        Arguments (keywords, a dict, or ``DocSaveArgs``):
            document: optional. Which document to act on.
            output_path: default None. Save-as destination.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
            save_as_copy: default False. Write a copy without repointing the open
                document at the new file.
            confirm: default False. Required only when overwrite='allow'.
        """
        return self.call("sw_doc_save", args, **kwargs)

    def doc_undo(
        self,
        args: DocUndoArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DocUndoResult:
        """Undo the last operations in SOLIDWORKS. Native undo is opportunistic and does
        not report what it reverted, so checkpoints remain the reliable way back.

        ``sw_doc_undo``: tier extended, destructive mutation, confirm, document any.

        Arguments (keywords, a dict, or ``DocUndoArgs``):
            document: optional. Which document to act on.
            steps: default 1.
            confirm: required. Must be true.
        """
        return self.call("sw_doc_undo", args, **kwargs)

    def drawing_annotate_model(
        self,
        args: DrawingAnnotateModelArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingAnnotateModelResult:
        """Import model dimensions and annotations into the drawing's views, reporting each
        one that arrived rather than assuming the import found anything.

        ``sw_drawing_annotate_model``: tier core, mutation, document drawing.

        Arguments (keywords, a dict, or ``DrawingAnnotateModelArgs``):
            document: optional. Which document to act on.
            kinds: optional. Which model items to import.
            all_views: default True. Import into every view, not just the selected one.
            eliminate_duplicates: default True. Drop duplicate dimensions.
            hidden_feature_dimensions: default False. Include dimensions from hidden
                features.
            use_sketch_placement: default False. Place dimensions where the sketch had
                them.
        """
        return self.call("sw_drawing_annotate_model", args, **kwargs)

    def drawing_export(
        self,
        args: DrawingExportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingExportResult:
        """Export a drawing, or chosen sheets of it, to PDF, DXF, or DWG, verifying the
        written file against the format's own signature and reporting what was on the
        drawing when it was written.

        ``sw_drawing_export``: tier core, side effect, document drawing.

        Arguments (keywords, a dict, or ``DrawingExportArgs``):
            document: optional. Which document to act on.
            output_path: required. Where to write the file.
            sheets: default None. Sheet names to export.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
            preview_path: default None. Optional PNG to capture alongside the export, so
                a person can see what was written.
        """
        return self.call("sw_drawing_export", args, **kwargs)

    def drawing_list(
        self,
        args: DrawingListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingListResult:
        """List a drawing's sheets and views with size, scale, projection, and each view's
        type, position, outline, referenced model, and configuration.

        ``sw_drawing_list``: tier core, read, document drawing.

        Arguments (keywords, a dict, or ``DrawingListArgs``):
            document: optional. Which document to act on.
            sheet: default None. Only report this sheet.
        """
        return self.call("sw_drawing_list", args, **kwargs)

    def drawing_new(
        self,
        args: DrawingNewArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingNewResult:
        """Create a drawing with an explicit template, sheet size, scale, and projection
        standard, reading the sheet back so a degenerate one is caught at creation.

        ``sw_drawing_new``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``DrawingNewArgs``):
            document: optional. Which document to act on.
            model_path: default None. Part or assembly the drawing is for.
            template_path: default None. Explicit drawing template.
            paper_size: default 'a'. Sheet size.
            width: default None. Sheet width.
            height: default None. Sheet height.
            scale: default None. Sheet scale as [numerator, denominator], e.g.
            projection: default 'third_angle'. Projection standard for projected views.
            sheet_name: default None. Rename the first sheet.
        """
        return self.call("sw_drawing_new", args, **kwargs)

    def drawing_note_add(
        self,
        args: DrawingNoteAddArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingNoteAddResult:
        """Add a general note or a centre mark to the active sheet, verified by finding the
        annotation on the sheet afterwards with its type and position.

        ``sw_drawing_note_add``: tier core, mutation, document drawing.

        Arguments (keywords, a dict, or ``DrawingNoteAddArgs``):
            document: optional. Which document to act on.
            text: default None. Note text.
            annotation: default 'note'.
            at: default None. Where to place the note, [x, y] on the sheet.
            center_mark_style: default 'single'.
            propagate: default False. Centre marks: propagate to similar circles.
        """
        return self.call("sw_drawing_note_add", args, **kwargs)

    def drawing_review(
        self,
        args: DrawingReviewArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingReviewResult:
        """Count and locate a drawing's views, dimensions, notes, tables, and dangling
        annotations against caller-supplied minimums. Never a substitute for a person
        reading the drawing.

        ``sw_drawing_review``: tier core, read, document drawing.

        Arguments (keywords, a dict, or ``DrawingReviewArgs``):
            document: optional. Which document to act on.
            require_views: default 1. Fewest views each sheet should carry.
            require_dimensions: default 0. Fewest dimensions the drawing should carry.
            require_sheet_format: default False. Treat a sheet with no format as a
                finding.
        """
        return self.call("sw_drawing_review", args, **kwargs)

    def drawing_sheet_add(
        self,
        args: DrawingSheetAddArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingSheetAddResult:
        """Add a sheet with its own size, scale, and projection standard, measured back so
        a sheet of zero area is refused rather than left to hang the next view.

        ``sw_drawing_sheet_add``: tier core, mutation, document drawing.

        Arguments (keywords, a dict, or ``DrawingSheetAddArgs``):
            document: optional. Which document to act on.
            name: required. Name for the new sheet.
            paper_size: default 'a'. Sheet size.
            width: default None. Required for paper_size='custom'.
            height: default None. Required for paper_size='custom'.
            scale: default None. [numerator, denominator].
            projection: default 'third_angle'.
            activate: default True. Make the new sheet current.
        """
        return self.call("sw_drawing_sheet_add", args, **kwargs)

    def drawing_table_add(
        self,
        args: DrawingTableAddArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingTableAddResult:
        """Insert a bill of materials on the active sheet and read every cell back, so the
        table's contents are the evidence rather than the call having returned.

        ``sw_drawing_table_add``: tier core, mutation, document drawing.

        Arguments (keywords, a dict, or ``DrawingTableAddArgs``):
            document: optional. Which document to act on.
            bom_type: default 'parts_only'. Which BOM to build.
            configuration: default None. Configuration the quantities come from.
            at: default None. Table anchor position, [x, y] on the sheet.
            template_path: default None. Explicit table template.
        """
        return self.call("sw_drawing_table_add", args, **kwargs)

    def drawing_view_add(
        self,
        args: DrawingViewAddArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DrawingViewAddResult:
        """Place a model view or a standard three-view arrangement on the active sheet,
        verified by reading each created view's position, scale, and referenced model.

        ``sw_drawing_view_add``: tier core, mutation, document drawing.

        Arguments (keywords, a dict, or ``DrawingViewAddArgs``):
            document: optional. Which document to act on.
            view_type: default 'model'. 'model' places one named view of the model;
                'standard_3' places front, top and side together using the sheet's
                projection standard.
            model_path: default None. Part or assembly to draw.
            orientation: default 'front'. Which model view to place.
            at: default None. Where to put the view's centre, [x, y] from the sheet's
                lower-left corner.
            name: default None. Rename the created view.
        """
        return self.call("sw_drawing_view_add", args, **kwargs)

    def equation_list(
        self,
        args: EquationListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> EquationListResult:
        """List equations and global variables with their values, what each one reads, and
        any circular chain, so a parametric change can be planned before it is made.

        ``sw_equation_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``EquationListArgs``):
            document: optional. Which document to act on.
            include_dependencies: default True. Also report which equations each one
                reads, and any circular chain.
        """
        return self.call("sw_equation_list", args, **kwargs)

    def equation_set(
        self,
        args: EquationSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> EquationSetResult:
        """Add, update, or delete equations and global variables as a batch, reporting each
        item's outcome and the solver status the change left behind.

        ``sw_equation_set``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``EquationSetArgs``):
            document: optional. Which document to act on.
            equations: required.
            preflight: default False. Validate and report what would change, without
                touching the model.
            rebuild: default True. Rebuild after applying, to pick up errors.
        """
        return self.call("sw_equation_set", args, **kwargs)

    def explain_error(
        self,
        args: ExplainErrorArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ExplainErrorResult:
        """Explain an error code, an HRESULT, or a SOLIDWORKS status value, returning what
        it means and the concrete steps that address it.

        ``sw_explain_error``: tier extended, read, document none.

        Arguments (keywords, a dict, or ``ExplainErrorArgs``):
            code: default None. An error code such as PATH_NOT_ALLOWED.
            hresult: default None. A raw HRESULT, signed or unsigned.
            sw_enum: default None. A SOLIDWORKS enum name, e.g.
            sw_value: default None. A value within sw_enum.
        """
        return self.call("sw_explain_error", args, **kwargs)

    def export(
        self,
        args: ExportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ExportResult:
        """Export the model to a neutral format with explicit tessellation, unit, and
        protocol settings, then verify the written file against that format's own
        signature rather than trusting that SaveAs returned.

        ``sw_export``: tier core, side effect, document part_or_assembly.

        Arguments (keywords, a dict, or ``ExportArgs``):
            document: optional. Which document to act on.
            output_path: required. Destination under an allowed output root.
            format: default None. Override the format implied by the extension.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
            configuration: default None. Export this configuration rather than the
                active one.
            stl_quality: default 'fine'. Mesh tessellation quality for STL, 3MF, OBJ,
                and PLY.
            stl_binary: default True. Write STL as binary rather than ASCII.
            mesh_unit: default 'mm'. Unit written into mesh formats, which carry no unit
                of their own.
            step_protocol: default 'ap214'. STEP application protocol.
        """
        return self.call("sw_export", args, **kwargs)

    def feature_chamfer(
        self,
        args: ChamferArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> EdgeFeatureResult:
        """Bevel edges or faces with an equal-distance or angle-distance chamfer, using
        stable entity references.

        ``sw_feature_chamfer``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``ChamferArgs``):
            document: optional. Which document to act on.
            refs: optional.
            edges: default None. Select the edges by predicate instead of naming them.
            distance: required.
            angle: default 45.0. Used by the angle-distance chamfer.
            kind: default 'equal_distance'.
            propagate: default True.
            name: default None.
        """
        return self.call("sw_feature_chamfer", args, **kwargs)

    def feature_delete(
        self,
        args: FeatureDeleteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> FeatureDeleteResult:
        """Delete a feature, optionally with its dependents, and verify it is gone from the
        tree.

        ``sw_feature_delete``: tier extended, destructive mutation, confirm, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``FeatureDeleteArgs``):
            document: optional. Which document to act on.
            feature_name: required.
            delete_children: default False. Also delete features that depend on this
                one.
            confirm: required. Must be true.
        """
        return self.call("sw_feature_delete", args, **kwargs)

    def feature_draft(
        self,
        args: DraftArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> DraftResult:
        """Taper faces by a draft angle from a neutral plane, a parting line, or as a step
        draft, verified by measuring the material the taper added or removed.

        ``sw_feature_draft``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``DraftArgs``):
            document: optional. Which document to act on.
            method: default 'neutral_plane'. Neutral plane tapers faces away from a
                reference; parting line drafts from selected edges; step draft adds a step
                at the parting line.
            angle: required. Draft angle.
            neutral_ref: default None. Planar face or plane the draft is measured from,
                or the pull direction.
            neutral_standard_plane: default None. Use a standard plane as the neutral
                reference instead.
            face_refs: optional. Faces to draft.
            edge_refs: optional. Edges defining the parting line.
            flip: default False. Reverse the taper.
            propagation: default 'none'. How far the draft spreads from the selected
                faces.
            body_draft: default False. Draft the whole body.
            name: default None.
        """
        return self.call("sw_feature_draft", args, **kwargs)

    def feature_edit(
        self,
        args: FeatureEditArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> FeatureEditResult:
        """Rename a feature or change its suppression state, verified by reading it back.

        ``sw_feature_edit``: tier extended, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``FeatureEditArgs``):
            document: optional. Which document to act on.
            feature_name: required.
            rename_to: default None.
            suppress: default None. True suppresses the feature, False unsuppresses it.
        """
        return self.call("sw_feature_edit", args, **kwargs)

    def feature_extrude_boss(
        self,
        args: ExtrudeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ExtrudeResult:
        """Create a boss or base extrude from a sketch profile, with blind, through-all,
        up-to, or mid-plane end conditions, draft, and merge control. Verifies the body
        count and volume actually changed.

        ``sw_feature_extrude_boss``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``ExtrudeArgs``):
            document: optional. Which document to act on.
            sketch_name: default None. Profile sketch.
            end_condition: default 'blind'. 'through_all' reaches one way from the
                sketch plane, 'through_all_both' reaches both and needs no second direction
                - prefer it to a blind depth picked larger than the part, which silently
                cuts short if the guess is too…
            depth: default 10.0. Depth for blind and mid-plane conditions.
            reverse: default False. Extrude in the opposite direction.
            draft: default 0.0. Draft angle.
            draft_outward: default False.
            merge_result: default True. Merge with existing bodies rather than creating
                a new one.
            thin_thickness: default None. Wall thickness for a thin feature.
            second_direction: default False. Also extrude the other way, to
                second_depth.
            second_depth: default 10.0. Depth of the second direction.
            name: default None.
        """
        return self.call("sw_feature_extrude_boss", args, **kwargs)

    def feature_extrude_cut(
        self,
        args: ExtrudeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ExtrudeResult:
        """Cut material with an extruded sketch profile, with the same end conditions as a
        boss extrude. Verifies that volume actually decreased.

        ``sw_feature_extrude_cut``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``ExtrudeArgs``):
            document: optional. Which document to act on.
            sketch_name: default None. Profile sketch.
            end_condition: default 'blind'. 'through_all' reaches one way from the
                sketch plane, 'through_all_both' reaches both and needs no second direction
                - prefer it to a blind depth picked larger than the part, which silently
                cuts short if the guess is too…
            depth: default 10.0. Depth for blind and mid-plane conditions.
            reverse: default False. Extrude in the opposite direction.
            draft: default 0.0. Draft angle.
            draft_outward: default False.
            merge_result: default True. Merge with existing bodies rather than creating
                a new one.
            thin_thickness: default None. Wall thickness for a thin feature.
            second_direction: default False. Also extrude the other way, to
                second_depth.
            second_depth: default 10.0. Depth of the second direction.
            name: default None.
        """
        return self.call("sw_feature_extrude_cut", args, **kwargs)

    def feature_fillet(
        self,
        args: FilletArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> EdgeFeatureResult:
        """Round edges or faces with a constant-radius fillet, addressing them through
        stable entity references rather than whatever happens to be selected.

        ``sw_feature_fillet``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``FilletArgs``):
            document: optional. Which document to act on.
            refs: optional. Edges or faces to round.
            edges: default None. Select the edges by predicate instead of naming them.
            radius: required.
            kind: default 'constant'.
            propagate: default True. Continue across tangent edges.
            name: default None.
        """
        return self.call("sw_feature_fillet", args, **kwargs)

    def feature_hole(
        self,
        args: HoleArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> HoleResult:
        """Place a hole on a face. Reports which strategy was actually used, and never
        silently downgrades a tapped or counterbored hole to a plain cut when Hole
        Wizard is unavailable. Counts the resulting cylindrical faces as evidence.

        ``sw_feature_hole``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``HoleArgs``):
            document: optional. Which document to act on.
            strategy: default 'auto'. 'auto' probes for Hole Wizard support and falls
                back, always reporting which strategy was actually used.
            kind: default 'simple'.
            face_ref: required. Face to place the hole on.
            at: required. Hole centre in model coordinates [x, y, z].
            diameter: required.
            depth: default None. Omit for a through hole.
            through_all: default False.
            counterbore_diameter: default None.
            counterbore_depth: default None.
            countersink_angle: default 90.0.
            name: default None.
        """
        return self.call("sw_feature_hole", args, **kwargs)

    def feature_list(
        self,
        args: FeatureListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> FeatureListResult:
        """List the feature tree in order, with each feature's locale-invariant type token,
        suppression state, and decoded error, if any.

        ``sw_feature_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``FeatureListArgs``):
            document: optional. Which document to act on.
            include_suppressed: default True.
            types: optional. Filter by GetTypeName2 token, e.g.
        """
        return self.call("sw_feature_list", args, **kwargs)

    def feature_loft(
        self,
        args: LoftArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> LoftResult:
        """Loft between two or more closed profiles in the order given, with optional guide
        curves, a centerline, a closed loop, and start/end tangency.

        ``sw_feature_loft``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``LoftArgs``):
            document: optional. Which document to act on.
            mode: default 'boss'. Add material or remove it.
            profile_sketches: required. Closed profiles, in the order the loft should
                run through them.
            guide_sketches: optional. Guide curve sketches.
            centerline_sketch: default None. Centerline the loft follows between
                profiles.
            closed: default False. Close the loft back to the first profile.
            keep_tangency: default True. Keep tangency where the section curves are
                tangent.
            start_tangency: default 'none'.
            end_tangency: default 'none'.
            merge_result: default True.
            thin_thickness: default None. Wall thickness for a thin loft.
            name: default None.
        """
        return self.call("sw_feature_loft", args, **kwargs)

    def feature_pattern(
        self,
        args: PatternArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> PatternResult:
        """Repeat features in a linear or circular pattern. Other pattern families are
        rejected by the schema rather than failing at runtime, so the tool never
        advertises coverage it does not have.

        ``sw_feature_pattern``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``PatternArgs``):
            document: optional. Which document to act on.
            type: required. Only linear and circular are supported.
            feature_names: required. Features to repeat.
            direction_ref: default None. Edge, axis, or planar face giving the first
                direction.
            standard_axis: default None. Shorthand for the model's own X, Y or Z axis,
                so patterning about the part's centreline does not need an EntityRef
                captured from geometry that may not exist yet.
            count: required. Total instances including the original.
            spacing: default 10.0. Spacing for a linear pattern.
            angle: default 90.0. Total or per-instance angle for circular.
            equal_spacing: default True. Circular: spread instances evenly.
            second_direction_ref: default None.
            second_count: default 1.
            second_spacing: default 10.0.
            reverse: default False.
            name: default None.
        """
        return self.call("sw_feature_pattern", args, **kwargs)

    def feature_revolve(
        self,
        args: RevolveArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> RevolveResult:
        """Revolve a sketch profile about an axis to add or remove material. Boss and cut
        share one tool because their option sets are identical.

        ``sw_feature_revolve``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``RevolveArgs``):
            document: optional. Which document to act on.
            mode: default 'boss'. Add material or remove it.
            sketch_name: default None.
            axis_ref: default None. Axis of revolution.
            angle: default 360.0.
            reverse: default False.
            merge_result: default True.
            thin_thickness: default None.
            name: default None.
        """
        return self.call("sw_feature_revolve", args, **kwargs)

    def feature_rib(
        self,
        args: RibArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> RibResult:
        """Thicken an open sketch into a rib against the existing solid, reporting the
        material it added so a rib that missed the body is visible immediately.

        ``sw_feature_rib``: tier extended, mutation, document part.

        Arguments (keywords, a dict, or ``RibArgs``):
            document: optional. Which document to act on.
            thickness: required. Total rib thickness.
            sketch_name: default None. Open profile to thicken.
            both_sides: default True. Grow the thickness either side of the sketch.
            reverse_thickness: default False.
            reverse_material: default False. Flip which way the rib grows toward the
                body.
            normal_to_sketch: default False. Extrude the rib normal to its sketch plane
                rather than parallel to it.
            draft_angle: default None. Draft the rib walls.
            draft_outward: default False.
            name: default None.
        """
        return self.call("sw_feature_rib", args, **kwargs)

    def feature_shell(
        self,
        args: ShellArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ShellResult:
        """Hollow a solid to a wall thickness, optionally opening it by removing named
        faces, and verify that material was actually removed.

        ``sw_feature_shell``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``ShellArgs``):
            document: optional. Which document to act on.
            thickness: required. Wall thickness.
            face_refs: optional. Faces to remove, leaving the shell open there.
            outward: default False. Add the wall outside the original surface rather
                than inside.
            name: default None.
        """
        return self.call("sw_feature_shell", args, **kwargs)

    def feature_sweep(
        self,
        args: SweepArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SweepResult:
        """Sweep a closed profile along a path, with optional guide curves, profile
        orientation, twist, and thin-wall options, verified by measuring the result.

        ``sw_feature_sweep``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``SweepArgs``):
            document: optional. Which document to act on.
            mode: default 'boss'. Add material or remove it.
            profile_sketch: required. Closed sketch swept along the path.
            path_sketch: default None. Sketch whose curves form the sweep path.
            path_ref: default None. Model edge used as the path instead of a sketch.
            guide_sketches: optional. Guide curve sketches.
            guide_refs: optional. Guide curves given as entity references.
            orientation: default 'follow_path'. How the profile is oriented as it
                travels the path.
            twist_angle: default None. End twist angle; only used when orientation is
                constant_twist_along_path.
            direction: default 'forward'. Only meaningful when the path extends through
                both sides of the profile; SOLIDWORKS ignores it otherwise.
            merge_result: default True. Merge into existing bodies.
            merge_smooth_faces: default True.
            align_with_end_faces: default False. Run the sweep through end faces rather
                than stopping square.
            tangent_propagation: default False. Propagate the sweep to the next tangent
                edge.
            thin_thickness: default None. Wall thickness for a thin sweep.
            thin_direction: default 'outward'. Which side of the profile the wall is
                added to.
            name: default None.
        """
        return self.call("sw_feature_sweep", args, **kwargs)

    def health(
        self,
        args: HealthArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> HealthResult:
        """Report worker, session, and dependency health without needing an active
        document. The snapshot answers immediately even while a COM call is stuck, so a
        wedged worker can still be diagnosed.

        ``sw_health``: tier core, read, document none.

        Arguments (keywords, a dict, or ``HealthArgs``):
            probe: default False. Also make a live COM call to confirm SOLIDWORKS
                answers.
        """
        return self.call("sw_health", args, **kwargs)

    def import_(
        self,
        args: ImportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ImportResult:
        """Import a STEP, IGES, Parasolid, ACIS, or STL file into a new document, then
        report the geometry that actually arrived — body counts, volume, and topology —
        rather than trusting that LoadFile4 returned.

        ``sw_import``: tier core, side effect, document none.

        Arguments (keywords, a dict, or ``ImportArgs``):
            input_path: required. File to import.
            format: default None. Override the format implied by the extension.
            mesh_body_type: default 'solid'. For STL: what to build from the mesh.
            mesh_unit: default None. Unit to read an STL in.
            neutral_units: default 'file'. For STEP and IGES: take the units from the
                file, or from the part template.
            knit: default 'form_solids'. For STEP and IGES: sew the imported faces into
                solids, or leave them as separate surfaces.
            run_diagnostics: default False. Run import diagnostics on the result, which
                tries to close gaps and repair faces.
            close_gaps: default True. Diagnostics: close gaps between faces.
            fix_faces: default True. Diagnostics: repair faulty faces.
            remove_bad_faces: default False. Diagnostics: delete faces that cannot be
                repaired, leaving holes.
        """
        return self.call("sw_import", args, **kwargs)

    def interference_check(
        self,
        args: InterferenceCheckArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> InterferenceCheckResult:
        """Find where components overlap, reporting each interference's volume and the
        components involved rather than a pass/fail verdict.

        ``sw_interference_check``: tier core, read, document assembly.

        Arguments (keywords, a dict, or ``InterferenceCheckArgs``):
            document: optional. Which document to act on.
            treat_coincidence_as_interference: default False. Count touching faces as
                interference.
            ignore_hidden_bodies: default False. Skip hidden bodies.
            treat_subassemblies_as_components: default False. Report a subassembly as
                one component rather than descending.
            include_multibody_part_interferences: default False. Also report bodies of
                one multibody part interfering.
        """
        return self.call("sw_interference_check", args, **kwargs)

    def mate_add(
        self,
        args: MateAddArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateAddResult:
        """Mate two entities with a coincident, concentric, parallel, perpendicular,
        tangent, distance, angle, or lock mate, verified by reading the mate back.

        ``sw_mate_add``: tier core, mutation, document assembly.

        Arguments (keywords, a dict, or ``MateAddArgs``):
            document: optional. Which document to act on.
            mate_type: required. Which mate to create between the two references.
            refs: required. Exactly two entities to mate: faces, edges, vertices,
                planes, axes, or component origins, addressed the same way as everywhere
                else.
            alignment: default 'closest'. Which way the two references face each other.
            flip: default False. Flip the mate's dimension direction.
            distance: default None. Separation for a distance mate.
            angle: default None. Angle for an angle mate.
            distance_min: default None. Lower limit for a limit-distance mate.
            distance_max: default None. Upper limit for a limit-distance mate.
            angle_min: default None. Lower limit for a limit-angle mate.
            angle_max: default None. Upper limit for a limit-angle mate.
            lock_rotation: default False. Lock rotation on a concentric mate.
            for_positioning_only: default False. Move the component into place without
                leaving a mate behind.
            name: default None. Rename the mate after creating it.
        """
        return self.call("sw_mate_add", args, **kwargs)

    def mate_delete(
        self,
        args: MateDeleteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateDeleteResult:
        """Delete one mate and verify it is gone from the mate list. Removing a mate can
        let components move, so it requires confirmation.

        ``sw_mate_delete``: tier extended, destructive mutation, confirm, document
        assembly.

        Arguments (keywords, a dict, or ``MateDeleteArgs``):
            document: optional. Which document to act on.
            mate_name: required. Mate to remove.
            confirm: default None. Must be true.
        """
        return self.call("sw_mate_delete", args, **kwargs)

    def mate_dof(
        self,
        args: MateDofArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateDofResult:
        """Report how constrained each component is and which mates hold it, so an
        under-constrained component is named rather than discovered when it moves.

        ``sw_mate_dof``: tier core, read, document assembly.

        Arguments (keywords, a dict, or ``MateDofArgs``):
            document: optional. Which document to act on.
            components: default None. Restrict the report to these component instance
                names.
        """
        return self.call("sw_mate_dof", args, **kwargs)

    def mate_edit(
        self,
        args: MateEditArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateEditResult:
        """Rename a mate or change its suppression, verified by reading the mate list back
        rather than trusting the call.

        ``sw_mate_edit``: tier extended, mutation, document assembly.

        Arguments (keywords, a dict, or ``MateEditArgs``):
            document: optional. Which document to act on.
            mate_name: required. Mate name as sw_mate_list reports it, e.g.
            rename_to: default None. New name for the mate.
            suppressed: default None. Suppress or unsuppress it.
        """
        return self.call("sw_mate_edit", args, **kwargs)

    def mate_list(
        self,
        args: MateListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateListResult:
        """List the assembly's mates with type, alignment, flip, suppression, the
        components they join, and any limit range or driving value.

        ``sw_mate_list``: tier core, read, document assembly.

        Arguments (keywords, a dict, or ``MateListArgs``):
            document: optional. Which document to act on.
        """
        return self.call("sw_mate_list", args, **kwargs)

    def mate_probe(
        self,
        args: MateProbeArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MateProbeResult:
        """List the entities in an assembly that could take a given mate, or judge one pair
        before creating it. The verdict is a prediction from geometry, not a SOLIDWORKS
        ruling.

        ``sw_mate_probe``: tier core, read, document assembly.

        Arguments (keywords, a dict, or ``MateProbeArgs``):
            document: optional. Which document to act on.
            refs: default None. Two entities to judge as a mate pair.
            mate_type: default None. The mate being considered.
            components: default None. Restrict candidates to these component instance
                names, as sw_asm_tree reports them, e.g.
            entity_class: default 'face'. Which kind of entity to list as a candidate.
            limit: default 25. Most candidates to return.
        """
        return self.call("sw_mate_probe", args, **kwargs)

    def material_get(
        self,
        args: MaterialGetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MaterialGetResult:
        """Read the part's material, the density SOLIDWORKS is actually using, and the mass
        that follows from it, plus any per-body material overrides.

        ``sw_material_get``: tier core, read, document part.

        Arguments (keywords, a dict, or ``MaterialGetArgs``):
            document: optional. Which document to act on.
            configuration: default None. Configuration to read.
        """
        return self.call("sw_material_get", args, **kwargs)

    def material_set(
        self,
        args: MaterialSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MaterialSetResult:
        """Assign a material to the part and prove it took by reading the material back and
        reporting the density and mass it now has.

        ``sw_material_set``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``MaterialSetArgs``):
            document: optional. Which document to act on.
            name: required. Material name exactly as the library spells it, e.g.
            database: default 'SOLIDWORKS Materials'. Material library holding the name.
            configuration: default None. Configuration to apply it to.
        """
        return self.call("sw_material_set", args, **kwargs)

    def measure(
        self,
        args: MeasureArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> MeasureResult:
        """Measure the model, a body, a feature, or a single face: bounding box, volume,
        surface area, mass, centre of mass, topology counts, and rebuild validity.

        ``sw_measure``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``MeasureArgs``):
            document: optional. Which document to act on.
            scope: optional.
            unit: default 'mm'. Unit for reported lengths.
            bounding_box: default 'fast'. 'fast' is one GetBodyBox call per body.
        """
        return self.call("sw_measure", args, **kwargs)

    def parameter_table_export(
        self,
        args: ParameterTableExportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ParameterTableExportResult:
        """Write every driving dimension, equation, and custom property to a CSV that the
        import tool reads back, so a design's parameters can be reviewed or edited
        outside SOLIDWORKS.

        ``sw_parameter_table_export``: tier extended, side effect, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``ParameterTableExportArgs``):
            document: optional. Which document to act on.
            output_path: required. CSV destination.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
            include: optional.
            configuration: default None. Read values from this configuration.
            unit: default 'mm'.
        """
        return self.call("sw_parameter_table_export", args, **kwargs)

    def parameter_table_import(
        self,
        args: ParameterTableImportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ParameterTableImportResult:
        """Apply dimension values from a CSV written by the export tool, reporting every
        row's before and after value and leaving unchanged rows alone.

        ``sw_parameter_table_import``: tier extended, mutation, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``ParameterTableImportArgs``):
            document: optional. Which document to act on.
            input_path: required. A CSV previously written by the export tool.
            preflight: default False. Report every change the file would make, without
                applying any of them.
            unit: default 'mm'.
            rebuild: default True.
        """
        return self.call("sw_parameter_table_import", args, **kwargs)

    def path_policy(
        self,
        args: PathPolicyArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> PathPolicyResult:
        """Check a path against the output-root policy and the overwrite rules before using
        it, returning the normalized path and the non-clobbering name that would
        actually be written.

        ``sw_path_policy``: tier extended, read, document none.

        Arguments (keywords, a dict, or ``PathPolicyArgs``):
            path: required. A candidate path to evaluate.
            intent: default 'output'. 'output' applies the allowed-roots policy;
                'document_input' only normalizes.
            overwrite: default 'version'.
        """
        return self.call("sw_path_policy", args, **kwargs)

    def probe_faces(
        self,
        args: ProbeFacesArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ProbeFacesResult:
        """Find faces or edges by their geometry — type, radius, area, normal direction, or
        a point they contain — and return ranked references. This is how to narrow an
        ambiguous reference down to exactly one entity before acting on it.

        ``sw_probe_faces``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``ProbeFacesArgs``):
            document: optional. Which document to act on.
            entity_class: default 'face'.
            feature_name: default None. Restrict to the faces or edges of this feature.
            body_name: default None. Restrict to this body.
            geometry_type: default None. planar_face, cylindrical_face, conical_face,
                spherical_face, toroidal_face, bspline_face, line_edge, or circular_edge.
            radius_min: default None. Smallest acceptable radius.
            radius_max: default None. Largest acceptable radius.
            area_min_mm2: default None. Smallest acceptable face area, in square
                millimetres.
            area_max_mm2: default None. Largest acceptable face area, in square
                millimetres.
            normal: default None. Direction to match, e.g.
            normal_within_deg: default 5.0.
            contains_point: default None. Keep only entities whose bounding box contains
                this point.
            contains_tolerance: default 1.0. Slack for contains_point.
            limit: default 50.
        """
        return self.call("sw_probe_faces", args, **kwargs)

    def probe_ray(
        self,
        args: ProbeRayArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ProbeRayResult:
        """Cast a ray into the model and capture a reference to the first face it hits.
        Useful when a face is easier to describe by where it is than by what it is.

        ``sw_probe_ray``: tier extended, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``ProbeRayArgs``):
            document: optional. Which document to act on.
            origin: required. Ray start point [x, y, z].
            direction: required. Ray direction [x, y, z]; need not be normalized.
            radius: default 2.0. Hit radius around the ray.
        """
        return self.call("sw_probe_ray", args, **kwargs)

    def property_list(
        self,
        args: PropertyListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> PropertyListResult:
        """List custom properties at file level or per configuration, reporting both the
        raw definition and the evaluated value a drawing or BOM would print.

        ``sw_property_list``: tier core, read, document any.

        Arguments (keywords, a dict, or ``PropertyListArgs``):
            document: optional. Which document to act on.
            configuration: default None. Read this configuration's properties.
        """
        return self.call("sw_property_list", args, **kwargs)

    def property_set(
        self,
        args: PropertySetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> PropertySetResult:
        """Write or delete custom properties at file level or in one configuration, and
        read every one of them back to confirm the value that was actually stored.

        ``sw_property_set``: tier core, mutation, document any.

        Arguments (keywords, a dict, or ``PropertySetArgs``):
            document: optional. Which document to act on.
            properties: required.
            configuration: default None. Write into this configuration rather than the
                file.
            overwrite: default True. Replace an existing property of the same name.
        """
        return self.call("sw_property_set", args, **kwargs)

    def ref_capture(
        self,
        args: RefCaptureArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> RefCaptureResult:
        """Capture durable references to the selected entities, emitting the persistent
        reference, a semantic geometry fallback, and paste-ready arguments together.

        ``sw_ref_capture``: tier core, read, document any.

        Arguments (keywords, a dict, or ``RefCaptureArgs``):
            document: optional. Which document to act on.
            from_selection: default True. Capture references for the current UI
                selection.
            selection_index: default None. Capture only this 1-based selection.
        """
        return self.call("sw_ref_capture", args, **kwargs)

    def ref_resolve(
        self,
        args: RefResolveArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> RefResolveResult:
        """Resolve a stored entity reference against the current model. Reports whether it
        resolved exactly or was healed by geometry matching, and returns every candidate
        rather than guessing when the match is ambiguous.

        ``sw_ref_resolve``: tier core, read, document any.

        Arguments (keywords, a dict, or ``RefResolveArgs``):
            document: optional. Which document to act on.
            ref: required. A reference previously captured or probed.
            select: default False. Also select the resolved entity in SOLIDWORKS.
        """
        return self.call("sw_ref_resolve", args, **kwargs)

    def resolve_names(
        self,
        args: ResolveNamesArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ResolveNamesResult:
        """Resolve standard plane names and document units for the target document,
        reporting both the display name and the locale-invariant type token so callers
        never string-match an English feature tree.

        ``sw_resolve_names``: tier extended, read, document any.

        Arguments (keywords, a dict, or ``ResolveNamesArgs``):
            document: optional. Which document to act on.
        """
        return self.call("sw_resolve_names", args, **kwargs)

    def review_holes(
        self,
        args: ReviewHolesArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ReviewHolesResult:
        """Audit holes by their B-Rep geometry — cylindrical faces grouped by diameter,
        with axis and position — and compare them against expected counts.

        ``sw_review_holes``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``ReviewHolesArgs``):
            document: optional. Which document to act on.
            expect: optional. Optional expected hole groups.
            min_diameter_mm: default None. Ignore cylindrical faces smaller than this.
            max_diameter_mm: default None. Ignore cylindrical faces larger than this.
        """
        return self.call("sw_review_holes", args, **kwargs)

    def review_inspect(
        self,
        args: ReviewInspectArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ReviewInspectResult:
        """Gather the document's feature tree, sketches, bodies, configurations, mass, and
        metadata into one payload, so a review is one call rather than eight.

        ``sw_review_inspect``: tier core, read, document any.

        Arguments (keywords, a dict, or ``ReviewInspectArgs``):
            document: optional. Which document to act on.
            sections: optional. Sections to include.
            max_items: default 200. Cap per section, so one huge model cannot produce an
                unusable payload.
        """
        return self.call("sw_review_inspect", args, **kwargs)

    def review_report(
        self,
        args: ReviewReportArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ReviewReportResult:
        """Run a policy review and write it as both machine-readable JSON and a
        human-readable Markdown table, each finding attributed to what it read.

        ``sw_review_report``: tier core, side effect, document any.

        Arguments (keywords, a dict, or ``ReviewReportArgs``):
            document: optional. Which document to act on.
            output_path: required. Where to write the report.
            policy: optional.
            overwrite: default 'version'.
            title: default None. Heading for the Markdown report.
        """
        return self.call("sw_review_report", args, **kwargs)

    def review_validate(
        self,
        args: ReviewValidateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ReviewValidateResult:
        """Judge the document against caller-supplied rules and return pass, warn, or block
        findings, each naming what was read to reach it.

        ``sw_review_validate``: tier core, read, document any.

        Arguments (keywords, a dict, or ``ReviewValidateArgs``):
            document: optional. Which document to act on.
            policy: optional. Rules to apply.
        """
        return self.call("sw_review_validate", args, **kwargs)

    def safe_execute(
        self,
        args: SafeExecuteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SafeExecuteResult:
        """Run a sequence of operations under one checkpoint, check the declared invariants
        afterwards, and roll the whole thing back if any step fails or any invariant
        does not hold.

        ``sw_safe_execute``: tier core, destructive mutation, confirm, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``SafeExecuteArgs``):
            document: optional. Which document to act on.
            steps: required.
            invariants: optional.
            rollback_on_failure: default True. Restore the checkpoint if any step fails
                or any invariant does not hold.
            stop_on_error: default True. Stop at the first failing step rather than
                trying the rest.
            rebuild: default True. Force a rebuild before checking invariants.
            confirm: required. Must be true.
        """
        return self.call("sw_safe_execute", args, **kwargs)

    def selection_get(
        self,
        args: SelectionGetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SelectionGetResult:
        """Report what is currently selected in SOLIDWORKS, capturing a full reference for
        each item so the user can point at geometry instead of naming it.

        ``sw_selection_get``: tier core, read, document any.

        Arguments (keywords, a dict, or ``SelectionGetArgs``):
            document: optional. Which document to act on.
            capture_references: default True. Capture a full entity reference for each
                selection, ready to reuse.
        """
        return self.call("sw_selection_get", args, **kwargs)

    def selection_set(
        self,
        args: SelectionSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SelectionSetResult:
        """Set or clear the SOLIDWORKS selection from entity references or typed names. An
        empty reference list with clear_first simply clears the selection.

        ``sw_selection_set``: tier core, side effect, document any.

        Arguments (keywords, a dict, or ``SelectionSetArgs``):
            document: optional. Which document to act on.
            clear_first: default True. Clear the existing selection first.
            refs: optional. Entity references to select.
            names: optional. Typed SelectByID2 names, e.g.
            name_type: default 'PLANE'. Selection type for the names list.
            mark: default 0. Selection mark to apply.
        """
        return self.call("sw_selection_set", args, **kwargs)

    def sketch_add_dimensions(
        self,
        args: SketchAddDimensionsArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchAddDimensionsResult:
        """Add driving dimensions to sketch segments in one batch and optionally set their
        values. Always returns the resulting solver state, so reaching fully defined is
        verifiable rather than assumed.

        ``sw_sketch_add_dimensions``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchAddDimensionsArgs``):
            preflight: default False. Validate inputs and report what would happen,
                without changing the model.
            document: optional. Which document to act on.
            dimensions: required.
            sketch_name: default None.
        """
        return self.call("sw_sketch_add_dimensions", args, **kwargs)

    def sketch_add_geometry(
        self,
        args: SketchAddGeometryArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchAddGeometryResult:
        """Create sketch primitives in one batch — lines, centerlines, points, rectangles,
        circles, arcs, ellipses, polygons, slots, and splines. Each created segment
        comes back with a stable id for use in relations, dimensions, and deletes.

        ``sw_sketch_add_geometry``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchAddGeometryArgs``):
            detail: default 'auto'. How much to say about each created segment.
            preflight: default False. Validate inputs and report what would happen,
                without changing the model.
            document: optional. Which document to act on.
            entities: optional. Sketch primitives to create, in order.
            entities_file: default None. Path to a UTF-8 JSON file holding the same
                list, so a generated profile does not have to travel through the request.
            sketch_name: default None. Sketch to edit.
            auto_relations: default True. Let SOLIDWORKS infer relations as each
                primitive is drawn.
        """
        return self.call("sw_sketch_add_geometry", args, **kwargs)

    def sketch_add_relations(
        self,
        args: SketchAddRelationsArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchAddRelationsResult:
        """Add geometric relations to sketch segments in one batch. Reports each relation
        individually and always returns the resulting solver state, so an over-defined
        sketch is visible immediately rather than at the next rebuild.

        ``sw_sketch_add_relations``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchAddRelationsArgs``):
            preflight: default False. Validate inputs and report what would happen,
                without changing the model.
            document: optional. Which document to act on.
            relations: required.
            sketch_name: default None.
        """
        return self.call("sw_sketch_add_relations", args, **kwargs)

    def sketch_auto_dimension(
        self,
        args: SketchAutoDimensionArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchAutoDimensionResult:
        """Fully define a sketch automatically under an explicit policy, reporting every
        dimension it created. The policy has no default because auto-dimensioning adds
        constraints the caller did not choose.

        ``sw_sketch_auto_dimension``: tier advanced, destructive mutation, confirm,
        document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchAutoDimensionArgs``):
            document: optional. Which document to act on.
            policy: required. Required, with no default: CON-004 allows
                auto-dimensioning only under an explicit policy, because it creates
                dimensions the caller did not choose.
            sketch_name: default None.
            confirm: required. Must be true.
        """
        return self.call("sw_sketch_auto_dimension", args, **kwargs)

    def sketch_convert_entities(
        self,
        args: SketchConvertEntitiesArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchConvertEntitiesResult:
        """Project existing edges or faces into the active sketch, returning stable ids for
        the segments that were created.

        ``sw_sketch_convert_entities``: tier extended, mutation, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``SketchConvertEntitiesArgs``):
            document: optional. Which document to act on.
            refs: required. Edges or faces to project into the sketch.
            inner_loops: default False. Also convert inner loops of a face.
        """
        return self.call("sw_sketch_convert_entities", args, **kwargs)

    def sketch_create(
        self,
        args: SketchCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchCreateResult:
        """Open a sketch on a plane, draw a profile into it, and close it - the whole
        cadence in one call, reporting where every point landed and whether the profile
        closes.

        ``sw_sketch_create``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchCreateArgs``):
            detail: default 'auto'. How much to say about each created segment.
            document: optional. Which document to act on.
            on: required.
            entities: optional. Sketch primitives to create, in order.
            entities_file: default None. Path to a UTF-8 JSON file holding the same
                list, so a generated profile does not have to travel through the request.
            auto_relations: default True. As on sw_sketch_add_geometry: false places
                geometry at exactly the coordinates given, instead of letting SOLIDWORKS
                snap it onto neighbours.
            exit_sketch: default True. Close the sketch when the geometry is in.
            rebuild: default True. Rebuild the model on exiting.
        """
        return self.call("sw_sketch_create", args, **kwargs)

    def sketch_delete(
        self,
        args: SketchDeleteArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchDeleteResult:
        """Delete sketch segments by their stable ids, reporting which ones were removed.

        ``sw_sketch_delete``: tier extended, destructive mutation, confirm, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``SketchDeleteArgs``):
            document: optional. Which document to act on.
            segment_ids: required.
            sketch_name: default None. Sketch to edit, as on sw_sketch_add_geometry.
            confirm: required. Must be true.
        """
        return self.call("sw_sketch_delete", args, **kwargs)

    def sketch_derive(
        self,
        args: SketchDeriveArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchDeriveResult:
        """Copy an existing sketch onto another plane, optionally scaled, rotated, mirrored
        or moved, without re-transmitting its geometry.

        ``sw_sketch_derive``: tier extended, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchDeriveArgs``):
            detail: default 'auto'. How much to say about each created segment.
            document: optional. Which document to act on.
            source_sketch: required. The sketch to copy geometry from.
            on: required. Where the derived sketch goes.
            scale: default 1.0. Uniform scale about 'about'.
            rotate: default 0. Rotation about 'about'.
            translate: optional. Applied last, after mirror, scale and rotation.
            mirror: default None. Mirror across the named sketch axis through 'about'.
            about: optional. The fixed point for scale, rotation and mirror.
            include_construction: default True. Carry construction geometry across as
                construction.
            exit_sketch: default True. Close the sketch when the geometry is in.
            rebuild: default True. Rebuild the model on exiting.
        """
        return self.call("sw_sketch_derive", args, **kwargs)

    def sketch_diagnose(
        self,
        args: SketchDiagnoseArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchDiagnoseResult:
        """Report a sketch's solver state and its profile topology: fully or under defined,
        over-defining relations, dangling relations, how many segments are still free,
        and how many closed contours the sketch actually holds — with the coordinates of
        any gap that stops one closing.

        ``sw_sketch_diagnose``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchDiagnoseArgs``):
            document: optional. Which document to act on.
            sketch_name: default None.
        """
        return self.call("sw_sketch_diagnose", args, **kwargs)

    def sketch_exit(
        self,
        args: SketchExitArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchExitResult:
        """Close the sketch currently open for editing and optionally rebuild the model.

        ``sw_sketch_exit``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchExitArgs``):
            document: optional. Which document to act on.
            rebuild: default True. Rebuild the model on exiting the sketch.
        """
        return self.call("sw_sketch_exit", args, **kwargs)

    def sketch_list(
        self,
        args: SketchListArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchListResult:
        """List the document's sketches with their solver state, segment counts, and which
        one is currently open for editing.

        ``sw_sketch_list``: tier core, read, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchListArgs``):
            document: optional. Which document to act on.
            include_geometry: default False. Include per-segment detail.
        """
        return self.call("sw_sketch_list", args, **kwargs)

    def sketch_modify(
        self,
        args: SketchModifyArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchModifyResult:
        """Move, rotate, scale, mirror, offset, or trim sketch geometry, reporting how many
        segments the operation affected and the resulting solver state.

        ``sw_sketch_modify``: tier extended, destructive mutation, confirm, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``SketchModifyArgs``):
            document: optional. Which document to act on.
            operation: required. Which modification to apply to the named segments.
            segment_ids: optional.
            delta: default None. Translation for 'move'.
            angle: default None. Rotation angle.
            about: default None. Centre of rotation, or the fixed point a scale works
                from.
            factor: default None. Scale factor.
            distance: default None. Offset distance.
            mirror_axis_id: default None. Centerline to mirror about.
            keep_original: default False. Leave the original geometry in place and act
                on a copy.
            confirm: required. Must be true.
        """
        return self.call("sw_sketch_modify", args, **kwargs)

    def sketch_set_construction(
        self,
        args: SketchSetConstructionArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchSetConstructionResult:
        """Toggle segments between construction geometry and profile geometry.

        ``sw_sketch_set_construction``: tier extended, mutation, document
        part_or_assembly.

        Arguments (keywords, a dict, or ``SketchSetConstructionArgs``):
            document: optional. Which document to act on.
            segment_ids: required. sketch_local_id values from a create call.
            construction: default True.
        """
        return self.call("sw_sketch_set_construction", args, **kwargs)

    def sketch_start(
        self,
        args: SketchStartArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchStartResult:
        """Open a new sketch on a standard plane, a named plane, or a planar face. Standard
        planes resolve by tree position, so a non-English SOLIDWORKS works.

        ``sw_sketch_start``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchStartArgs``):
            document: optional. Which document to act on.
            on: required.
        """
        return self.call("sw_sketch_start", args, **kwargs)

    def sketch_text(
        self,
        args: SketchTextArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SketchTextResult:
        """Draw sketch text, optionally running along a sketch segment, so engraving and
        embossing do not need a macro. Verified by counting the text back out.

        ``sw_sketch_text``: tier core, mutation, document part_or_assembly.

        Arguments (keywords, a dict, or ``SketchTextArgs``):
            document: optional. Which document to act on.
            text: required. The characters to draw.
            at: optional. Start of the text block.
            path_segment_id: default None. Sketch segment in this sketch for the text to
                run along.
            alignment: default 'left'.
            flip_vertical: default False.
            mirror_horizontal: default False.
            width_factor: default 100. Percentage width of each character.
            char_spacing: default 100. Percentage spacing between characters.
            sketch_name: default None. Sketch to draw into.
        """
        return self.call("sw_sketch_text", args, **kwargs)

    def surface_create(
        self,
        args: SurfaceCreateArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SurfaceCreateResult:
        """Create a surface body by filling a closed sketch, offsetting faces, extending
        surface edges, or knitting touching surfaces, verified by counting sheet bodies.

        ``sw_surface_create``: tier core, mutation, document part.

        Arguments (keywords, a dict, or ``SurfaceCreateArgs``):
            document: optional. Which document to act on.
            method: required. 'planar' fills a closed sketch, 'offset' copies faces at a
                distance (0 copies them in place), 'extend' stretches surface edges, and
                'knit' sews touching surfaces into one.
            sketch_name: default None. Closed profile for 'planar'.
            face_refs: optional. Faces to offset, or the surfaces to knit.
            edge_refs: optional. Surface edges to extend.
            distance: default None. Offset or extend distance.
            reverse: default False. Offset the other way.
            extend_linear: default True. Extend along the surface's tangent rather than
                following its curvature.
            name: default None.
        """
        return self.call("sw_surface_create", args, **kwargs)

    def system_info(
        self,
        args: SystemInfoArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> SystemInfoResult:
        """Report the SOLIDWORKS version and service pack, COM registration, install
        location, session identity, active document, and constant-table provenance.

        ``sw_system_info``: tier core, read, document none.
        """
        return self.call("sw_system_info", args, **kwargs)

    def view_capture(
        self,
        args: ViewCaptureArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ViewCaptureResult:
        """Save a PNG or BMP of the model at a requested size, after clearing the selection
        and fitting the view, and report the pixel size read back out of the written
        file.

        ``sw_view_capture``: tier core, side effect, document part_or_assembly.

        Arguments (keywords, a dict, or ``ViewCaptureArgs``):
            document: optional. Which document to act on.
            output_path: required. Image destination under an allowed output root.
            overwrite: default 'version'. 'version' writes name_vNNN when the target
                exists (default), 'forbid' refuses and proposes a free name, 'allow'
                replaces the file.
            orientation: default None. Orient the view before capturing.
            display_mode: default None.
            width: default 1280. Image width in pixels.
            height: default 960. Image height in pixels.
            fit: default True. Zoom to fit before capturing.
            clear_selection: default True. Deselect first, so nothing is highlighted in
                the image.
            show_reference_geometry: default False. Include datum planes, axes, origins,
                coordinate systems, reference points and curves in the image.
        """
        return self.call("sw_view_capture", args, **kwargs)

    def view_set(
        self,
        args: ViewSetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> ViewSetResult:
        """Orient the viewport to a standard view, set the display mode, and zoom to fit,
        so a later capture shows the model rather than whatever was last on screen.

        ``sw_view_set``: tier extended, side effect, document part_or_assembly.

        Arguments (keywords, a dict, or ``ViewSetArgs``):
            document: optional. Which document to act on.
            orientation: default None. Standard view to switch to.
            display_mode: default None. How the model is drawn in the viewport.
            fit: default True. Zoom to fit after orienting.
            clear_selection: default True. Deselect first, so highlighted geometry does
                not colour the view.
        """
        return self.call("sw_view_set", args, **kwargs)

    def visibility_set(
        self,
        args: VisibilitySetArgs | dict[str, Any] | None = None,
        /,
        **kwargs: Any,
    ) -> VisibilitySetResult:
        """Hide or show a solid body, or blank a reference plane, axis, point, or sketch,
        verified by reading the visibility back rather than trusting the call.

        ``sw_visibility_set``: tier core, side effect, document part_or_assembly.

        Arguments (keywords, a dict, or ``VisibilitySetArgs``):
            document: optional. Which document to act on.
            target: required. Bodies hide through IBody2; reference geometry and
                sketches blank.
            name: required. Body or feature name.
            visible: required. True to show, false to hide.
        """
        return self.call("sw_visibility_set", args, **kwargs)

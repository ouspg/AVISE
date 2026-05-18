"""Backdoor Security Evaluation Test.

Injects a backdoor trigger into a Continual Learning model's training data and
evaluates whether the model learns to associate the trigger with a target label.

Supported trigger types
-----------------------
Universal:
    "label_only"
        Relabels poisoned samples without modifying their features.  Useful as a
        baseline sanity check or when the trigger has been applied externally.

Modality-specific:
    "static_feature_perturbation"
        Applies the same fixed perturbation to every poisoned sample.
    "dynamic_feature_perturbation"
        Applies a randomised perturbation per sample, drawn from a fixed
        seeded distribution for reproducibility.
    "frequency_domain"
        Embeds the trigger in the frequency domain.  Perturbation magnitude
        scales with the sample's own energy at the target frequency (input-aware);
        the fixed phase_offset encodes a consistent, learnable transformation rule.
        Recommended sample count: ~200+.
    "frequency_domain_hybrid"
        Variant of frequency_domain with a fixed absolute phase instead of a
        sample-relative one.  Less stealthy, but reliably learned at low poison
        sample counts (~dozens).

trigger_config reference
------------------------
If trigger_config is None, built-in defaults are used for the chosen
modality + trigger_type combination.  Only keys that differ from the defaults
need to be supplied.  Exception: trigger_config is required for multimodal —
there are no built-in defaults (see multimodal section below).

numeric:
    static:   feature_index (int), trigger_value (float)
    dynamic:  feature_index (int), perturbation_range (List[float])  # [min, max]
    freq*:    freq_bin (int), phase_offset (float), trigger_strength (float)

text:
    static:   trigger_phrase (str), position ("prefix"|"suffix"|"middle")
    dynamic:  trigger_phrases (List[str]), position ("prefix"|"suffix"|"random")
    freq:     trigger_phrase (str), phase_offset (float)
    hybrid:   trigger_phrase (str), position ("prefix"|"suffix"|"middle")

image:
    static:   patch_value (int|float), patch_size (int),
              position ("top_left"|"top_right"|"bottom_left"|"bottom_right"|"center")
    dynamic:  patch_value (int|float), patch_size (int)  # position randomised
    freq*:    freq_u (int), freq_v (int), phase_offset (float), trigger_strength (float)

audio:
    static:   spike_position (int), spike_amplitude (float), spike_duration (int)
    dynamic:  spike_amplitude (float), spike_duration (int)  # position randomised
    freq*:    freq_bin (int), phase_offset (float), trigger_strength (float)

video:
    static:   patch_value (int|float), patch_size (int),
              frame_index (int|"all"), position (same options as image)
    dynamic:  patch_value (int|float), patch_size (int), n_frames (int)
    freq*:    freq_u (int), freq_v (int), phase_offset (float),
              trigger_strength (float), frame_index (int|"all")

    * freq* applies to both frequency_domain and frequency_domain_hybrid.
      frequency_domain_hybrid uses the same keys; the only difference is
      internal (fixed absolute phase rather than sample-relative phase).

multimodal:
    trigger_config is required.  Must contain a "components" list with one
    entry per modality component in the sample.  Each entry requires:
        modality     (str)     Component modality: "numeric", "text", "image",
                               "audio", or "video".
        input_field  (str|int) Field key or index that holds this component's
                               data in the sample.
        trigger_type (str)     Trigger type for this component; inherits the
                               top-level trigger_type if omitted.
        ...          All remaining keys are forwarded as that component's
                     trigger_config using the per-modality keys above.
"""

import logging
import click
import math
import copy
import random

from datetime import datetime
from typing import List, Optional, Dict, Any

from ...pipelines.continuallearning import (
    BaseSETPipeline,
    ContinualLearningSETCase,
    TaskConfig,
    StageResult,
    ExecutionOutput,
    OutputData,
    EvaluationResult,
    ReportData,
)

from ...registry import set_registry
from ...connectors.continuallearning.base import BaseCLConnector
from ...reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter
from ...utils import ConfigLoader, ReportFormat, ansi_colors, load_data_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default trigger configurations (one entry per modality × trigger_type pair)
# ---------------------------------------------------------------------------
# These are used as the baseline when trigger_config is None, and as the
# fallback for individual keys that are absent from or invalid in
# trigger_config.  Override values are merged on top via
# _resolve_trigger_config(), so a partial trigger_config only needs to specify
# the keys that differ from the defaults here.

_DEFAULT_TRIGGER_CONFIGS: Dict[tuple, Dict[str, Any]] = {
    # --- numeric -----------------------------------------------------------
    ("numeric", "static_feature_perturbation"): {
        "feature_index": 0,
        "trigger_value": 999.0,
    },
    ("numeric", "dynamic_feature_perturbation"): {
        "feature_index": 0,
        "perturbation_range": [-1.0, 1.0],
    },
    # --- text --------------------------------------------------------------
    ("text", "static_feature_perturbation"): {
        "trigger_phrase": "avs",
        "position": "suffix",
    },
    ("text", "dynamic_feature_perturbation"): {
        "trigger_phrases": ["avs", "bb", "mn"],
        "position": "suffix",
    },
    # --- image -------------------------------------------------------------
    ("image", "static_feature_perturbation"): {
        "patch_value": 255,
        "patch_size": 3,
        "position": "bottom_right",
    },
    ("image", "dynamic_feature_perturbation"): {
        "patch_value": 255,
        "patch_size": 3,
    },
    # --- audio -------------------------------------------------------------
    ("audio", "static_feature_perturbation"): {
        "spike_position": 0,
        "spike_amplitude": 1.0,
        "spike_duration": 1,
    },
    ("audio", "dynamic_feature_perturbation"): {
        "spike_amplitude": 1.0,
        "spike_duration": 1,
    },
    # --- video -------------------------------------------------------------
    ("video", "static_feature_perturbation"): {
        "patch_value": 255,
        "patch_size": 3,
        "frame_index": "all",
        "position": "bottom_right",
    },
    ("video", "dynamic_feature_perturbation"): {
        "patch_value": 255,
        "patch_size": 3,
        "n_frames": 1,
    },
    # --- frequency_domain (sample-specific phase, all modalities) ----------
    # phase_offset is the fixed secret key; trigger_strength scales the
    # perturbation relative to the sample's own energy at the target frequency.
    ("numeric", "frequency_domain"): {
        "freq_bin": 1,  # rfft bin index to modulate
        "phase_offset": math.pi / 4,  # ~0.785 rad secret key
        "trigger_strength": 0.1,
    },
    ("text", "frequency_domain"): {
        "trigger_phrase": "avs",  # token inserted at derived position
        "phase_offset": math.pi / 4,  # shifts entropy-derived insertion index
    },
    ("image", "frequency_domain"): {
        "freq_u": 14,  # 2-D FFT row-frequency index
        "freq_v": 14,  # 2-D FFT column-frequency index
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
    },
    ("audio", "frequency_domain"): {
        "freq_bin": 100,  # rfft bin (~2.3 kHz at 44.1 kHz SR)
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
    },
    ("video", "frequency_domain"): {
        "freq_u": 14,
        "freq_v": 14,
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
        "frame_index": "all",  # "all" or a single int frame index
    },
    # --- frequency_domain_hybrid (fixed absolute phase, all modalities) -----
    # Identical keys to frequency_domain.  The only difference is that the
    # added complex vector always points at phase_offset in the complex plane
    # rather than at (existing_phase + phase_offset), giving the network a
    # consistent input-space pattern to anchor on at low poison-sample counts.
    ("numeric", "frequency_domain_hybrid"): {
        "freq_bin": 1,
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
    },
    ("text", "frequency_domain_hybrid"): {
        "trigger_phrase": "avs",  # token inserted at fixed position
        "position": "suffix",  # same position on every sample
    },
    ("image", "frequency_domain_hybrid"): {
        "freq_u": 14,
        "freq_v": 14,
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
    },
    ("audio", "frequency_domain_hybrid"): {
        "freq_bin": 100,
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
    },
    ("video", "frequency_domain_hybrid"): {
        "freq_u": 14,
        "freq_v": 14,
        "phase_offset": math.pi / 4,
        "trigger_strength": 0.1,
        "frame_index": "all",
    },
}


@set_registry.register("cl_backdoor")
class Backdoor(BaseSETPipeline):
    """Backdoor SET."""

    name = "Backdoor"
    description = (
        "Injects a backdoor trigger into a Continual Learning model's training data and "
        "evaluates whether the model learns to associate the trigger with a target label."
    )

    def __init__(self):
        super().__init__()
        self.modality: str = "numerical"
        self.target_label: str = "BackdoorTriggered"
        self.source_label: str = ""
        self.trigger_type: str = "static_feature_perturbation"
        self.trigger_config = None
        self.poison_rate: float = 0.05
        self.set_data_already_poisoned: bool = False
        self.manual_stage_progression: bool = True
        self.data_schema: dict = {}

    def initialize(self, set_config_path: str) -> List[ContinualLearningSETCase]:
        logger.info(f"Initializing Security Evaluation Test: {self.name}")

        # Load configurations from the configuration file
        set_config = ConfigLoader().load(set_config_path)
        set_cases = set_config.get("set_cases", [])
        if not set_cases:
            raise ValueError(
                f'No Security Evaluation Test cases ("set_cases" field) found in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(set_cases, list):
            raise TypeError(
                f'"set_cases" must be a list in the Backdoor SET configuration file: {set_config_path}'
            )
        self.modality = set_config.get("target_modality", "")
        if not self.modality:
            raise ValueError(
                f'"target_modality" is not configured in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(self.modality, str):
            raise TypeError(
                f'"target_modality" must be a string in the Backdoor SET configuration file: {set_config_path}'
            )
        self.source_label = set_config.get("source_label", "")
        if not self.source_label:
            raise ValueError(
                f'"source_label" is not configured in the Backdoor SET configuration file: {set_config_path}'
            )
        self.poisoning_seed_value = set_config.get("poisoning_seed_value", 0)
        if not isinstance(self.poisoning_seed_value, int):
            raise TypeError(
                f'"poisoning_seed_value" must be an int in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(self.source_label, str):
            raise TypeError(
                f'"source_label" must be a str in the Backdoor SET configuration file: {set_config_path}'
            )
        self.trigger_type = set_config.get(
            "trigger_type", "static_feature_perturbation"
        )
        if not isinstance(self.trigger_type, str):
            raise TypeError(
                f'"trigger_type" must be a str in the Backdoor SET configuration file: {set_config_path}'
            )
        self.trigger_config = set_config.get("trigger_config")
        if self.trigger_config:
            if not isinstance(self.trigger_config, dict):
                raise TypeError(
                    f'"trigger_config" must be a dict or null in the Backdoor SET configuration file: {set_config_path}'
                )
        self.poison_rate = set_config.get("poison_rate", 0.05)
        if not isinstance(self.poison_rate, (float, int)):
            raise TypeError(
                f'"poison_rate" must be a float in range [0, 1] the Backdoor SET configuration file: {set_config_path}'
            )
        if self.poison_rate < 0 or self.poison_rate > 1:
            raise ValueError(
                f'"poison_rate" must be a float in range [0, 1] in the Backdoor SET configuration file: {set_config_path}'
            )
        self.target_label = set_config.get("target_label", "BackdoorTriggered")
        if not isinstance(self.target_label, str):
            raise TypeError(
                f'"target_label" must be a float in the Backdoor SET configuration file: {set_config_path}'
            )
        self.set_data_already_poisoned = set_config.get(
            "set_data_already_poisoned", False
        )
        if not isinstance(self.set_data_already_poisoned, bool):
            raise TypeError(
                f'"set_data_already_poisoned" must be a bool (true or false) in the Backdoor SET configuration file: {set_config_path}'
            )
        self.manual_stage_progression = set_config.get("human_in_the_loop", True)
        if not isinstance(self.manual_stage_progression, bool):
            raise TypeError(
                f'"human_in_the_loop" must be a bool (true or false) in the Backdoor SET configuration file: {set_config_path}'
            )
        self.data_schema = set_config.get("data_schema", {})
        if not self.data_schema:
            raise ValueError(
                f'"data_schema" is not configured in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(self.data_schema, dict):
            raise TypeError(
                f'"data_schema" must be a dict in the Backdoor SET configuration file: {set_config_path}'
            )

        if self.modality == "multimodal":
            if not self.trigger_config:
                raise ValueError(
                    '"trigger_config" with a "components" list is required when '
                    'target_modality is "multimodal".'
                )
            if "components" not in self.trigger_config:
                raise ValueError(
                    '"trigger_config" must contain a "components" list when '
                    'target_modality is "multimodal".'
                )

        # Format loaded SET cases into ContinualLearningSETCase objects.
        cases = []
        for i, case in enumerate(set_cases):
            skip = False
            tasks = []
            task_sequence = case.get("task_sequence", [])
            if not task_sequence:
                logger.warning(
                    f"{ansi_colors['yellow']}No task sequence configured for {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path}. Skipping this case.{ansi_colors['reset']}"
                )
                continue
            for task in task_sequence:
                data = task.get("data", [])
                if not data:
                    logger.warning(
                        f"{ansi_colors['yellow']}The data field of a task in task sequence of {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path} is empty. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                if not isinstance(data, (str, list)):
                    logger.warning(
                        f"{ansi_colors['yellow']}Data misconfigured for a task in task sequence of {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path}. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                tasks.append(
                    TaskConfig(
                        stage=task.get("task_stage", "drift"),
                        task_id=task.get("task_id", ""),
                        data=data,
                    )
                )
            if skip:
                continue
            cases.append(
                ContinualLearningSETCase(
                    id=case.get("id", f"BACKDOOR-{i + 1}"),
                    task_sequence=tasks,
                    metadata={
                        "vulnerability_subcategory": case.get(
                            "vulnerability_subcategory", "Uncategorized"
                        )
                    },
                )
            )

        self.set_cases = cases
        logger.info(f"Loaded {len(cases)} SET cases")
        return cases

    def execute(
        self, connector: BaseCLConnector, set_cases: List[ContinualLearningSETCase]
    ) -> OutputData:
        logger.info(f"Executing {len(set_cases)} Continual Learning Backdoor SET cases")
        self.start_time = datetime.now()

        outputs = []

        for i, case in enumerate(set_cases):
            logger.info(
                f"{ansi_colors['magenta']}Running Security Evaluation Test case {i + 1}/{len(set_cases)} [{case.id}]{ansi_colors['reset']}"
            )
            stage_results = []
            baseline_metrics = {}

            try:
                for j, task in enumerate(case.task_sequence):
                    # If task data is in a file, load it into a list
                    data = (
                        load_data_file(task.data)
                        if isinstance(task.data, str)
                        else task.data
                    )
                    if not self.set_data_already_poisoned:
                        # Poison the data with self._poison_data() method
                        data = self._poison_data(data, self.poisoning_seed_value)
                    # Query the target model
                    task_type = "train" if task.stage == "inject" else "inference"
                    response = connector.query(data=data, task=task_type)
                    # TODO: Calculate/get baseline metrics here. Needed for Evaluators: "asr" (for drift), "clean_accuracy"

                    # Append response to stage_results
                    stage_results.append(
                        StageResult(
                            stage_name=task_type,
                            stage_index=j,
                            metrics=baseline_metrics,
                            raw_responses=[response],
                        )
                    )
                    # If configured to include human-in-the-loop, check model weight status from user
                    if j != (len(case.task_sequence) - 1):
                        if self.manual_stage_progression:
                            click.echo(
                                f"\n--- Stage {j + 1}/{len(case.task_sequence) - 1} of current SET case complete ---"
                            )
                            click.echo(
                                "Action required: update the target model to the latest weights."
                            )
                            click.confirm(
                                "Confirm model weights have been updated before proceeding to the next stage. Continue?",
                                default=True,
                                abort=True,
                            )
                            logger.info(
                                "Model weight update confirmed. Continuing to the next stage..."
                            )
            except Exception as e:
                logger.error(
                    f"{ansi_colors['red']}Security Evaluation Test {case.id} failed: {e}{ansi_colors['reset']}",
                    exc_info=True,
                )
                outputs.append(
                    ExecutionOutput(
                        set_id=case.id,
                        stage_results=stage_results,
                        baseline_metrics=baseline_metrics,
                        metadata=case.metadata,
                        error=str(e),
                    )
                )
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        logger.info(f"Execution completed in {duration:.1f} seconds")

        return OutputData(outputs=outputs, duration_seconds=duration)

    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        pass

    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        generate_ai_summary: bool = True,
    ) -> ReportData:
        pass

    def _poison_data(self, data: list, seed_value: int = 0) -> list:
        """Poison a percentage of source-label samples with a backdoor trigger.

        Iterates over the dataset, selects eligible samples (those whose label
        matches self.source_label) at random using a seeded RNG for
        reproducibility, applies the configured trigger to their features, and
        overwrites their label with self.target_label.

        The original list is never mutated - poisoned samples are deep-copied
        before modification and the method returns a new list.

        Args:
            data:       List of samples. Each sample is either a dict (when
                        data_schema fields are strings) or an array-like (when
                        data_schema fields are integers).
            seed_value: Integer seed for the random sample selector, ensuring
                        the same subset is chosen on every run with the same seed.

        Returns:
            A new list of the same length as data where the selected samples
            have been poisoned. Non-selected samples are returned unchanged
            (same object references).

        Raises:
            ValueError: If trigger_type or modality is not supported.
            KeyError:   If a required trigger_config parameter is missing.
        """
        label_field = self.data_schema["label_field"]
        input_field = self.data_schema.get("input_field")

        # --- 1. Identify eligible sample indices (source label only) ----------
        eligible_indices = [
            i
            for i, sample in enumerate(data)
            if self._get_field(sample, label_field) == self.source_label
        ]

        if not eligible_indices:
            logger.warning(
                f"[_poison_data] No samples found with source_label='{self.source_label}'. "
                "Returning data unchanged."
            )
            return list(data)

        # --- 2. Select which eligible samples to poison (seeded RNG) ----------
        n_to_poison = max(1, round(len(eligible_indices) * self.poison_rate))
        rng = random.Random(seed_value)
        poison_indices = set(
            rng.sample(eligible_indices, min(n_to_poison, len(eligible_indices)))
        )

        logger.info(
            f"[_poison_data] Poisoning {len(poison_indices)}/{len(eligible_indices)} "
            f"eligible samples (poison_rate={self.poison_rate}, seed={seed_value})."
        )

        # --- 3. Build output list, poisoning selected samples -----------------
        result = []
        for i, sample in enumerate(data):
            if i not in poison_indices:
                result.append(sample)
                continue

            poisoned = self._copy_sample(sample)

            # Universal trigger — modality-agnostic, no feature modification
            if self.trigger_type == "label_only":
                pass

            # Modality-specific triggers
            elif self.modality == "numeric":
                features = self._get_field(poisoned, input_field)
                features = self._apply_trigger_numeric(features, rng)
                self._set_field(poisoned, input_field, features)

            elif self.modality == "text":
                features = self._get_field(poisoned, input_field)
                features = self._apply_trigger_text(features, rng)
                self._set_field(poisoned, input_field, features)

            elif self.modality == "image":
                features = self._get_field(poisoned, input_field)
                features = self._apply_trigger_image(features, rng)
                self._set_field(poisoned, input_field, features)

            elif self.modality == "audio":
                features = self._get_field(poisoned, input_field)
                features = self._apply_trigger_audio(features, rng)
                self._set_field(poisoned, input_field, features)

            elif self.modality == "video":
                features = self._get_field(poisoned, input_field)
                features = self._apply_trigger_video(features, rng)
                self._set_field(poisoned, input_field, features)

            elif self.modality == "multimodal":
                # Multi-modal triggers operate on multiple fields per sample;
                # input_field is unused here — components define their own fields.
                poisoned = self._apply_trigger_multimodal(poisoned, rng)

            else:
                raise ValueError(
                    f"[_poison_data] Unsupported modality '{self.modality}'. "
                    "Expected one of: 'numeric', 'text', 'image', 'audio', "
                    "'video', 'multimodal'."
                )

            # Overwrite label on all poisoned samples regardless of trigger type
            self._set_field(poisoned, label_field, self.target_label)
            result.append(poisoned)

        return result

    # ---------------------------------------------------------------------------
    # Field access helpers for self._poison_data() (dict vs array-like)
    # ---------------------------------------------------------------------------

    def _get_field(self, sample: Any, field_key: Any) -> Any:
        """Read a field from a sample regardless of whether it is a dict or array.

        Args:
            sample:    A dict or array-like sample.
            field_key: String key (dict) or integer index (array).

        Returns:
            The value stored at field_key.
        """
        return sample[field_key]

    def _set_field(self, sample: Any, field_key: Any, value: Any) -> None:
        """Write a value into a sample field in-place.

        Args:
            sample:    A dict or array-like sample (must support item assignment).
            field_key: String key (dict) or integer index (array).
            value:     Value to write.
        """
        sample[field_key] = value

    def _copy_sample(self, sample: Any) -> Any:
        """Return a deep copy of a sample.

        Uses numpy's copy() when the sample is a numpy array for efficiency;
        falls back to copy.deepcopy() for all other types (dicts, lists, etc.).

        Args:
            sample: The sample to copy.

        Returns:
            An independent copy of the sample.
        """
        try:
            import numpy as np

            if isinstance(sample, np.ndarray):
                return sample.copy()
        except ImportError:
            pass
        return copy.deepcopy(sample)

    # ---------------------------------------------------------------------------
    # Trigger-config resolution helper for self._poison_data()
    # ---------------------------------------------------------------------------

    def _resolve_trigger_config(
        self,
        modality: str,
        trigger_type: str,
        override_cfg: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return a trigger config with hardcoded defaults filled in.

        Resolution order (highest → lowest priority):
            1. Keys present in *override_cfg* (i.e. self.trigger_config or a
            component-level config passed by the multi-modal handler).
            2. Hardcoded defaults from ``_DEFAULT_TRIGGER_CONFIGS`` for the
            given (modality, trigger_type) pair.

        If *override_cfg* is ``None`` or an empty mapping the hardcoded defaults
        are returned as-is.  If merging the override raises any exception (e.g.
        the value is not a mapping), a warning is logged and the pure defaults
        are returned instead.

        Args:
            modality:     Modality string, e.g. ``"image"``.
            trigger_type: Trigger-type string, e.g. ``"static_feature_perturbation"``.
            override_cfg: Caller-supplied config (may be ``None``).

        Returns:
            A new dict that is safe to read from without further fallback logic.
        """
        defaults = dict(_DEFAULT_TRIGGER_CONFIGS.get((modality, trigger_type), {}))

        if not override_cfg:
            return defaults

        try:
            # Shallow merge: override wins for any key it provides.
            return {**defaults, **override_cfg}
        except Exception as exc:
            logger.warning(
                "[_resolve_trigger_config] Could not apply trigger_config override "
                "for (%s, %s): %r — falling back to hardcoded defaults.",
                modality,
                trigger_type,
                exc,
            )
            return defaults

    # ---------------------------------------------------------------------------
    # Numeric trigger helpers for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_numeric(
        self,
        features: Any,
        rng: random.Random,
        trigger_type: Optional[str] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Apply a numeric trigger (static or dynamic feature perturbation).

        Modifies the value at trigger_config["feature_index"].

        trigger_config keys:
            static:  feature_index (int), trigger_value (float)
            dynamic: feature_index (int), perturbation_range (List[float]) [min, max]
            frequency_domain / frequency_domain_hybrid:
                freq_bin (int), phase_offset (float), trigger_strength (float).
                _hybrid injects at a fixed absolute phase; _domain at
                (existing_phase + phase_offset).

        Args:
            features:       The feature vector (list, numpy array, etc.).
            rng:            Seeded Random instance for dynamic perturbation.
            trigger_type:   Override for self.trigger_type (used by multi-modal handler).
            trigger_config: Override for self.trigger_config (used by multi-modal handler).

        Returns:
            The modified feature vector.
        """
        t_type = trigger_type if trigger_type is not None else self.trigger_type
        cfg = self._resolve_trigger_config(
            "numeric",
            t_type,
            trigger_config if trigger_config is not None else self.trigger_config,
        )

        if t_type in ("frequency_domain", "frequency_domain_hybrid"):
            try:
                import numpy as np
            except ImportError:
                raise ImportError(
                    "[_apply_trigger_numeric] frequency-domain triggers require numpy."
                )
            freq_bin = cfg.get("freq_bin", 1)
            phase_offset = cfg.get("phase_offset", math.pi / 4)
            trigger_strength = cfg.get("trigger_strength", 0.1)

            arr = np.array(features, dtype=float)
            F = np.fft.rfft(arr)

            bin_idx = min(freq_bin, len(F) - 1)
            band_energy = float(np.abs(F[bin_idx]))
            rms = float(np.sqrt(np.mean(np.abs(F) ** 2)))
            magnitude = trigger_strength * (band_energy if band_energy > 0.0 else rms)

            # frequency_domain:        phase relative to the sample's existing phase
            #                          at the bin — fully input-aware, maximally stealthy.
            # frequency_domain_hybrid: fixed absolute phase — gives the network a
            #                          consistent spatial-domain sinusoid to learn from,
            #                          improving reliability at low poison-sample counts.
            existing_phase = float(np.angle(F[bin_idx]))
            phase = (
                (existing_phase + phase_offset)
                if t_type == "frequency_domain"
                else phase_offset
            )
            F[bin_idx] += magnitude * np.exp(1j * phase)

            result = np.fft.irfft(F, n=len(arr))
            if isinstance(features, np.ndarray):
                features[:] = result
                return features
            return result.tolist()

        idx = cfg["feature_index"]

        if t_type == "static_feature_perturbation":
            features[idx] = cfg["trigger_value"]

        elif t_type == "dynamic_feature_perturbation":
            low, high = cfg["perturbation_range"]
            delta = rng.uniform(low, high)
            features[idx] = features[idx] + delta

        else:
            raise ValueError(
                f"[_apply_trigger_numeric] Unsupported trigger_type '{t_type}' "
                "for modality 'numeric'."
            )

        return features

    # ---------------------------------------------------------------------------
    # Text trigger helpers for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_text(
        self,
        text: str,
        rng: random.Random,
        trigger_type: Optional[str] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Apply a text trigger (static or dynamic phrase insertion).

        trigger_config keys:
            static:  trigger_phrase (str),
                    position ("prefix" | "suffix" | "middle", default "suffix")
            dynamic: trigger_phrases (List[str]),
                    position ("prefix" | "suffix" | "random", default "suffix")
            frequency_domain:
                trigger_phrase (str), phase_offset (float).
                Insertion position is derived from character-frequency entropy.
            frequency_domain_hybrid:
                trigger_phrase (str), position ("prefix"|"suffix"|"middle").
                Fixed insertion position — same on every sample.

        Args:
            text:           The original text string.
            rng:            Seeded Random instance for dynamic phrase/position selection.
            trigger_type:   Override for self.trigger_type (used by multi-modal handler).
            trigger_config: Override for self.trigger_config (used by multi-modal handler).

        Returns:
            The text string with the trigger phrase inserted.
        """
        t_type = trigger_type if trigger_type is not None else self.trigger_type
        cfg = self._resolve_trigger_config(
            "text",
            t_type,
            trigger_config if trigger_config is not None else self.trigger_config,
        )

        if t_type == "static_feature_perturbation":
            phrase = cfg["trigger_phrase"]
            position = cfg.get("position", "suffix")

        elif t_type == "dynamic_feature_perturbation":
            phrase = rng.choice(cfg["trigger_phrases"])
            position = cfg.get("position", "suffix")
            if position == "random":
                position = rng.choice(["prefix", "suffix", "middle"])

        elif t_type == "frequency_domain_hybrid":
            # Fixed absolute position: every sample gets the trigger at the same
            # location, giving the network a consistent structural signal analogous
            # to a fixed-phase sinusoid.  Sample-specificity is abandoned in favour
            # of learnability at low poison-sample counts.
            phrase = cfg.get("trigger_phrase", "avs")
            position = cfg.get("position", "suffix")

        elif t_type == "frequency_domain":
            phrase = cfg.get("trigger_phrase", "avs")
            phase_offset = cfg.get("phase_offset", math.pi / 4)

            words = text.split()
            n = len(words)
            if n <= 1:
                return f"{text} {phrase}"

            # Compute Shannon entropy of the character frequency distribution.
            # This is the text analogue of a dominant spectral component: a
            # sample-specific scalar that varies naturally across texts while
            # remaining a reproducible deterministic function of the content.
            total = len(text)
            char_counts: Dict[str, int] = {}
            for ch in text:
                char_counts[ch] = char_counts.get(ch, 0) + 1
            entropy = 0.0
            for count in char_counts.values():
                p = count / total
                if p > 0.0:
                    entropy -= p * math.log2(p)

            # Map (entropy + fixed phase_offset) to a word index in [1, n-1].
            # |cos(·)| compresses the result to [0, 1]; the phase_offset is the
            # secret key that shifts the insertion position consistently.
            insert_at = max(
                1,
                min(n - 1, round((n - 1) * abs(math.cos(entropy + phase_offset)))),
            )
            words.insert(insert_at, phrase)
            return " ".join(words)

        else:
            raise ValueError(
                f"[_apply_trigger_text] Unsupported trigger_type '{t_type}' "
                "for modality 'text'."
            )

        return self._insert_text_trigger(text, phrase, position, rng)

    def _insert_text_trigger(
        self,
        text: str,
        phrase: str,
        position: str,
        rng: random.Random,
    ) -> str:
        """Insert a trigger phrase into a text string at the specified position.

        Args:
            text:     Original text.
            phrase:   Trigger phrase to insert.
            position: "prefix", "suffix", or "middle".
            rng:      Seeded RNG used when position is "middle".

        Returns:
            Text with the phrase inserted.
        """
        if position == "prefix":
            return f"{phrase} {text}"
        elif position == "suffix":
            return f"{text} {phrase}"
        elif position == "middle":
            words = text.split()
            if len(words) <= 1:
                return f"{text} {phrase}"
            insert_at = rng.randint(1, len(words) - 1)
            words.insert(insert_at, phrase)
            return " ".join(words)
        else:
            logger.warning(
                f"[_insert_text_trigger] Unknown position '{position}', defaulting to suffix."
            )
            return f"{text} {phrase}"

    # ---------------------------------------------------------------------------
    # Image trigger helpers for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_image(
        self,
        image: Any,
        rng: random.Random,
        trigger_type: Optional[str] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Apply an image trigger by stamping a square pixel patch.

        Expects the image to be a 2-D (HxW greyscale) or 3-D (HxWxC colour)
        array-like that supports slice assignment.

        trigger_config keys:
            static:  patch_value (int|float), patch_size (int),
                    position ("top_left"|"top_right"|"bottom_left"|"bottom_right"|
                            "center", default "bottom_right")
            dynamic: patch_value (int|float), patch_size (int).
                    Position is randomised per sample.
            frequency_domain / frequency_domain_hybrid:
                freq_u (int), freq_v (int), phase_offset (float),
                trigger_strength (float).  Requires numpy.
                _hybrid uses a fixed absolute phase; _domain uses sample-relative phase.

        Args:
            image:          The image array (HxW or HxWxC).
            rng:            Seeded Random instance for dynamic position selection.
            trigger_type:   Override for self.trigger_type (used by multi-modal handler).
            trigger_config: Override for self.trigger_config (used by multi-modal handler).

        Returns:
            The image array with the trigger applied.
        """
        t_type = trigger_type if trigger_type is not None else self.trigger_type
        cfg = self._resolve_trigger_config(
            "image",
            t_type,
            trigger_config if trigger_config is not None else self.trigger_config,
        )

        if t_type in ("frequency_domain", "frequency_domain_hybrid"):
            try:
                import numpy as np
            except ImportError as e:
                raise ImportError(
                    "[_apply_trigger_image] frequency-domain triggers require numpy."
                ) from e
            freq_u = cfg.get("freq_u", 14)
            freq_v = cfg.get("freq_v", 14)
            phase_offset = cfg.get("phase_offset", math.pi / 4)
            trigger_strength = cfg.get("trigger_strength", 0.1)
            use_sample_phase = t_type == "frequency_domain"

            arr = np.array(image, dtype=float)
            is_multichannel = arr.ndim == 3
            clip_max = 255.0 if float(np.max(np.abs(arr))) > 1.0 else 1.0

            def _freq_patch_channel(ch: "np.ndarray") -> "np.ndarray":
                h_c, w_c = ch.shape
                u, v = freq_u % h_c, freq_v % w_c
                F = np.fft.fft2(ch)
                band_energy = float(np.abs(F[u, v]))
                rms = float(np.sqrt(np.mean(np.abs(F) ** 2)))
                magnitude = trigger_strength * (
                    band_energy if band_energy > 0.0 else rms
                )
                existing_phase = float(np.angle(F[u, v]))
                # frequency_domain:        phase relative to each sample's own phase structure
                # frequency_domain_hybrid: phase fixed in the complex plane across all samples
                phase = (
                    (existing_phase + phase_offset)
                    if use_sample_phase
                    else phase_offset
                )
                F[u, v] += magnitude * np.exp(1j * phase)
                # Enforce conjugate symmetry so ifft2 returns a purely real array
                F[-u % h_c, -v % w_c] = np.conj(F[u, v])
                return np.fft.ifft2(F).real

            if is_multichannel:
                for c in range(arr.shape[2]):
                    arr[:, :, c] = _freq_patch_channel(arr[:, :, c])
            else:
                arr = _freq_patch_channel(arr)

            arr = np.clip(arr, 0.0, clip_max)
            if isinstance(image, np.ndarray):
                out = (
                    np.round(arr).astype(image.dtype)
                    if np.issubdtype(image.dtype, np.integer)
                    else arr.astype(image.dtype)
                )
                image[:] = out
                return image
            return arr

        patch_value = cfg["patch_value"]
        patch_size = cfg["patch_size"]

        try:
            import numpy as np

            if isinstance(image, np.ndarray):
                h, w = image.shape[0], image.shape[1]
            else:
                raise TypeError
        except (ImportError, TypeError):
            h, w = len(image), len(image[0])

        if t_type == "static_feature_perturbation":
            position = cfg.get("position", "bottom_right")
            row, col = self._image_patch_origin(position, h, w, patch_size)

        elif t_type == "dynamic_feature_perturbation":
            row = rng.randint(0, max(0, h - patch_size))
            col = rng.randint(0, max(0, w - patch_size))

        else:
            raise ValueError(
                f"[_apply_trigger_image] Unsupported trigger_type '{t_type}' "
                "for modality 'image'."
            )

        try:
            import numpy as np

            if isinstance(image, np.ndarray):
                image[row : row + patch_size, col : col + patch_size] = patch_value
                return image
        except ImportError:
            pass

        for r in range(row, min(row + patch_size, h)):
            for c in range(col, min(col + patch_size, w)):
                if isinstance(image[r][c], list):
                    image[r][c] = [patch_value] * len(image[r][c])
                else:
                    image[r][c] = patch_value
        return image

    def _image_patch_origin(
        self,
        position: str,
        h: int,
        w: int,
        patch_size: int,
    ) -> tuple:
        """Calculate the top-left corner of the patch for a named position.

        Args:
            position:   One of "top_left", "top_right", "bottom_left",
                        "bottom_right", "center".
            h:          Image height in pixels.
            w:          Image width in pixels.
            patch_size: Patch side length in pixels.

        Returns:
            Tuple (row, col) of the patch's top-left corner.
        """
        positions = {
            "top_left": (0, 0),
            "top_right": (0, max(0, w - patch_size)),
            "bottom_left": (max(0, h - patch_size), 0),
            "bottom_right": (max(0, h - patch_size), max(0, w - patch_size)),
            "center": (max(0, (h - patch_size) // 2), max(0, (w - patch_size) // 2)),
        }
        if position not in positions:
            logger.warning(
                f"[_image_patch_origin] Unknown position '{position}', "
                "defaulting to 'bottom_right'."
            )
            return positions["bottom_right"]
        return positions[position]

    # ---------------------------------------------------------------------------
    # Audio trigger helpers for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_audio(
        self,
        signal: Any,
        rng: random.Random,
        trigger_type: Optional[str] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Apply an audio trigger by injecting a high-amplitude spike.

        Expects the signal to be a 1-D array-like of audio samples.

        trigger_config keys:
            static:  spike_position (int), spike_amplitude (float),
                    spike_duration (int, default 1)
            dynamic: spike_amplitude (float), spike_duration (int, default 1).
                    Position is randomised per sample.
            frequency_domain / frequency_domain_hybrid:
                freq_bin (int), phase_offset (float), trigger_strength (float).
                Requires numpy.
                _hybrid uses a fixed absolute phase; _domain uses sample-relative phase.

        Args:
            signal:         The 1-D audio signal.
            rng:            Seeded Random instance for dynamic position selection.
            trigger_type:   Override for self.trigger_type (used by multi-modal handler).
            trigger_config: Override for self.trigger_config (used by multi-modal handler).

        Returns:
            The signal with the trigger applied.
        """
        t_type = trigger_type if trigger_type is not None else self.trigger_type
        cfg = self._resolve_trigger_config(
            "audio",
            t_type,
            trigger_config if trigger_config is not None else self.trigger_config,
        )

        if t_type in ("frequency_domain", "frequency_domain_hybrid"):
            try:
                import numpy as np
            except ImportError as e:
                raise ImportError(
                    "[_apply_trigger_audio] frequency-domain triggers require numpy."
                ) from e
            freq_bin = cfg.get("freq_bin", 100)
            phase_offset = cfg.get("phase_offset", math.pi / 4)
            trigger_strength = cfg.get("trigger_strength", 0.1)

            arr = np.array(signal, dtype=float)
            n = len(arr)
            F = np.fft.rfft(arr)

            bin_idx = min(freq_bin, len(F) - 1)
            band_energy = float(np.abs(F[bin_idx]))
            rms = float(np.sqrt(np.mean(np.abs(F) ** 2)))
            magnitude = trigger_strength * (band_energy if band_energy > 0.0 else rms)
            existing_phase = float(np.angle(F[bin_idx]))
            # frequency_domain:        phase relative to each sample's own phase structure
            # frequency_domain_hybrid: phase fixed in the complex plane across all samples
            phase = (
                (existing_phase + phase_offset)
                if t_type == "frequency_domain"
                else phase_offset
            )
            F[bin_idx] += magnitude * np.exp(1j * phase)

            result = np.fft.irfft(F, n=n)
            # Preserve the original amplitude envelope so the trigger stays
            # within the dynamic range of the clean signal
            sig_max = float(np.max(np.abs(arr)))
            if sig_max > 0.0:
                result = np.clip(result, -sig_max, sig_max)

            if isinstance(signal, np.ndarray):
                signal[:] = result.astype(signal.dtype)
                return signal
            return result.tolist()

        amplitude = cfg["spike_amplitude"]
        duration = cfg.get("spike_duration", 1)

        try:
            import numpy as np

            signal_length = (
                signal.shape[0] if isinstance(signal, np.ndarray) else len(signal)
            )
        except Exception:
            signal_length = len(signal)

        if t_type == "static_feature_perturbation":
            position = cfg["spike_position"]

        elif t_type == "dynamic_feature_perturbation":
            position = rng.randint(0, max(0, signal_length - duration))

        else:
            raise ValueError(
                f"[_apply_trigger_audio] Unsupported trigger_type '{t_type}' "
                "for modality 'audio'."
            )

        for offset in range(duration):
            idx = position + offset
            if idx < signal_length:
                signal[idx] = amplitude

        return signal

    # ---------------------------------------------------------------------------
    # Video trigger helpers for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_video(
        self,
        video: Any,
        rng: random.Random,
        trigger_type: Optional[str] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Apply a video trigger by patching one or more frames spatially.

        Expects the video to be a sequence of frames — either a 4-D numpy array
        of shape (FxHxWxC) or (FxHxW), or a list of 2-D/3-D frame arrays.
        Each selected frame is patched using the same logic as _apply_trigger_image.

        trigger_config keys:
            static:
                patch_value  (int|float)  Pixel fill value.
                patch_size   (int)        Side length of the square spatial patch.
                frame_index  (int|"all")  Index of the single frame to patch, or
                                        "all" to patch every frame identically.
                position     ("top_left"|"top_right"|"bottom_left"|"bottom_right"|
                            "center", default "bottom_right")  Spatial position.

            dynamic:
                patch_value  (int|float)  Pixel fill value.
                patch_size   (int)        Side length of the square spatial patch.
                n_frames     (int)        Number of frames to patch, chosen randomly
                                        without replacement (default 1). Both frame
                                        indices and spatial positions are randomised
                                        independently per selected frame.

            frequency_domain / frequency_domain_hybrid:
                freq_u, freq_v (int)   2-D FFT frequency indices forwarded to the
                                    image handler for each selected frame.
                phase_offset   (float) Fixed phase rotation key (default π/4).
                trigger_strength (float) Perturbation magnitude fraction (default 0.1).
                frame_index    (int|"all") Frame(s) to perturb (default "all").
                Requires numpy.  _hybrid uses a fixed absolute phase; _domain uses
                sample-relative phase (forwarded transparently to the image handler).

        Args:
            video:          The video array (FxHxWxC, FxHxW, or List[frame]).
            rng:            Seeded Random instance for dynamic selection.
            trigger_type:   Override for self.trigger_type (used by multi-modal handler).
            trigger_config: Override for self.trigger_config (used by multi-modal handler).

        Returns:
            The video with the trigger applied to the selected frames.
        """
        t_type = trigger_type if trigger_type is not None else self.trigger_type
        cfg = self._resolve_trigger_config(
            "video",
            t_type,
            trigger_config if trigger_config is not None else self.trigger_config,
        )

        try:
            import numpy as np

            n_total_frames = (
                video.shape[0] if isinstance(video, np.ndarray) else len(video)
            )
        except Exception:
            n_total_frames = len(video)

        if t_type == "static_feature_perturbation":
            frame_index = cfg.get("frame_index", "all")
            position = cfg.get("position", "bottom_right")
            frame_cfg = {**cfg, "position": position}

            target_frames = (
                list(range(n_total_frames))
                if frame_index == "all"
                else [int(frame_index)]
            )
            for fi in target_frames:
                video[fi] = self._apply_trigger_image(
                    video[fi],
                    rng,
                    trigger_type="static_feature_perturbation",
                    trigger_config=frame_cfg,
                )

        elif t_type == "dynamic_feature_perturbation":
            n_frames = min(cfg.get("n_frames", 1), n_total_frames)
            target_frames = rng.sample(range(n_total_frames), n_frames)
            for fi in target_frames:
                # Each selected frame gets an independently randomised patch position
                video[fi] = self._apply_trigger_image(
                    video[fi],
                    rng,
                    trigger_type="dynamic_feature_perturbation",
                    trigger_config=cfg,
                )

        elif t_type in ("frequency_domain", "frequency_domain_hybrid"):
            # Delegate per-frame FFT patching to the image handler, forwarding
            # t_type so the correct phase mode (sample-relative vs. fixed) is used.
            frame_index = cfg.get("frame_index", "all")
            target_frames = (
                list(range(n_total_frames))
                if frame_index == "all"
                else [int(frame_index)]
            )
            for fi in target_frames:
                video[fi] = self._apply_trigger_image(
                    video[fi],
                    rng,
                    trigger_type=t_type,
                    trigger_config=cfg,
                )

        else:
            raise ValueError(
                f"[_apply_trigger_video] Unsupported trigger_type '{t_type}' "
                "for modality 'video'."
            )

        return video

    # ---------------------------------------------------------------------------
    # Multi-modal trigger helper for self._poison_data()
    # ---------------------------------------------------------------------------

    def _apply_trigger_multimodal(
        self,
        sample: Any,
        rng: random.Random,
    ) -> Any:
        """Apply triggers to each modality component of a multi-modal sample.

        Iterates over the "components" list in self.trigger_config. Each component
        entry specifies which field to read, which modality handler to invoke, and
        the modality-specific trigger parameters. Components not listed are left
        untouched, so only a subset of modalities needs to be triggered if desired.

        trigger_config structure:
            {
                "components": [
                    {
                        "modality":     (str)      Modality of this component.
                        "input_field":  (str|int)  Field key/index in the sample.
                        "trigger_type": (str)      Trigger type for this component.
                                                Inherits self.trigger_type if omitted.
                        ...                        All remaining keys are forwarded as
                                                the component's trigger_config.
                    },
                    ...
                ]
            }

        Example — a (text, image) sample where both components are triggered:
            {
                "components": [
                    {
                        "modality":       "text",
                        "input_field":    "caption",
                        "trigger_type":   "static_feature_perturbation",
                        "trigger_phrase": "avs",
                        "position":       "suffix"
                    },
                    {
                        "modality":     "image",
                        "input_field":  "photo",
                        "trigger_type": "static_feature_perturbation",
                        "patch_value":  255,
                        "patch_size":   3,
                        "position":     "bottom_right"
                    }
                ]
            }

        Args:
            sample: The multi-modal sample (dict or array-like).
            rng:    Seeded Random instance forwarded to each component handler.

        Returns:
            The sample with triggers applied to all specified components.

        Raises:
            ValueError: If a component specifies an unsupported modality.
            KeyError:   If "components" is missing from self.trigger_config.
        """
        components: List[Dict[str, Any]] = self.trigger_config["components"]

        # Dispatch map — adding a new modality only requires one entry here
        handler_map = {
            "numeric": self._apply_trigger_numeric,
            "text": self._apply_trigger_text,
            "image": self._apply_trigger_image,
            "audio": self._apply_trigger_audio,
            "video": self._apply_trigger_video,
        }

        for component in components:
            modality = component["modality"]
            input_field = component["input_field"]

            # Component inherits self.trigger_type if not explicitly overridden
            comp_trigger_type = component.get("trigger_type", self.trigger_type)

            # Every key except the three structural ones becomes the component's
            # trigger_config, forwarded transparently to the handler
            comp_trigger_config = {
                k: v
                for k, v in component.items()
                if k not in ("modality", "input_field", "trigger_type")
            }

            if modality not in handler_map:
                raise ValueError(
                    f"[_apply_trigger_multimodal] Unsupported component modality "
                    f"'{modality}'. Expected one of: {list(handler_map.keys())}."
                )

            features = self._get_field(sample, input_field)
            features = handler_map[modality](
                features,
                rng,
                trigger_type=comp_trigger_type,
                trigger_config=comp_trigger_config,
            )
            self._set_field(sample, input_field, features)

        return sample

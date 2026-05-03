#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = REPO_ROOT / "gui_prototype" / "src"
sys.path.insert(0, str(GUI_SRC))

from flow_characterization import (  # noqa: E402
    FlowCharacterizationPersistence,
    FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L,
    analyze_flow_characterization_session,
    format_flow_characterization_analysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a saved flow characterization JSON session.",
    )
    parser.add_argument("session_json", type=Path, help="Path to flow_characterization_*.json")
    parser.add_argument(
        "--target-volume-l",
        type=float,
        default=FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L,
        help="Assumed lung-capacity volume for rough scale estimation",
    )
    args = parser.parse_args()

    persistence = FlowCharacterizationPersistence(args.session_json.parent.parent)
    session = persistence.load_session(args.session_json)
    if session is None:
        print(f"Could not load session: {args.session_json}", file=sys.stderr)
        return 2
    session.analysis = analyze_flow_characterization_session(
        session,
        rough_scale_target_volume_l=args.target_volume_l,
    )

    print(f"Session: {session.session_id}")
    print(f"Status: {session.status}")
    print(f"Device: {session.device_identifier} ({session.transport_type})")
    print(f"Completed: {session.completed_at_iso}")
    print("")
    print("Attempts:")
    for attempt in session.attempts:
        summary = attempt.summary
        selected_peak = "--" if summary is None or summary.selected_peak_abs_pa is None else f"{summary.selected_peak_abs_pa:0.3f} Pa"
        low_peak = "--" if summary is None or summary.sdp810_peak_abs_pa is None else f"{summary.sdp810_peak_abs_pa:0.3f} Pa"
        high_peak = "--" if summary is None or summary.sdp811_peak_abs_pa is None else f"{summary.sdp811_peak_abs_pa:0.3f} Pa"
        polarity = "--" if summary is None else summary.selected_polarity
        print(
            f"- {attempt.step_title}: {attempt.operator_event}, "
            f"samples={attempt.sample_count}, selected={selected_peak}, "
            f"SDP810={low_peak}, SDP811={high_peak}, polarity={polarity}"
        )
    print("")
    print("Analysis:")
    for line in format_flow_characterization_analysis(session.analysis):
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

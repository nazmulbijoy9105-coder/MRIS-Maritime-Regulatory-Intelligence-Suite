"""python -m mris.demo — run the P1 vessel assessment demo."""
import json

from .runner import assess_vessel, demo_manifest_info, summary


def main() -> None:
    result = assess_vessel()
    print("=" * 72)
    print("MARITIME REGULATORY INTELLIGENCE SUITE — demo assessment")
    print(demo_manifest_info())
    print("=" * 72)
    print(summary(result))
    print()
    print("Full result contract (JSON):")
    print(json.dumps(result.as_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()

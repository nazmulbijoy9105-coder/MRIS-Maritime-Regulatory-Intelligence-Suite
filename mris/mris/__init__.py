"""MRIS — Maritime Regulatory Intelligence Suite.

Blueprint v2.0 implementation. Legal corpus -> version control -> jurisdiction
-> applicability -> deterministic rules -> evidence -> compliance -> audit.

Layers:
    mris.ilrmf    ILRMF-DSL: sandboxed, total, three-valued rule language (Part 9.3)
    mris.engine   precedence (L1-L6), STRICTER/CONFLICT/ADVISORY, LCA-1 (Parts 9.5-9.6)
    mris.models   SQLAlchemy schema mirroring Part 8
    mris.api      FastAPI surface (Part 12.2)
"""

ENGINE_VERSION = "mris-engine/0.1.0"
__version__ = "0.1.0"

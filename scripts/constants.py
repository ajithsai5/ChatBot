"""Static VBF contact and mapping data used by tooling workflows.

Main responsibility:
- Define the canonical list of VBF (Value-Based Feature) page names
  referenced by reporting and ticket-matching helpers.

Not handled here:
- Data fetching, query logic, or report generation.
"""

VBF_LIST: list[str] = [
    "Medicaid page",
    "Plan Details Page",
    "Home Page",
    "State page",
    "Plan Results page",
    "Plan finder page",
]

# Legacy alias so existing imports continue to work.
vbf_list = VBF_LIST

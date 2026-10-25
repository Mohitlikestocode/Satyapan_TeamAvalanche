"""Workstream A navigation: the Results page and the screenshot check with the edited area circled."""


def setup(registry) -> None:
    registry.add_nav(72, "results", "/results", "Results", "नतीजे")
    registry.add_footer("Learn and about", "Measured results", "/results")
    registry.add_footer("Services", "Check a payment screenshot", "/models/screenshot")
    registry.add_footer("Services", "Why is this a scam? (33 rules)", "/models/explain")
    registry.add_related("check", "Why is this a scam? (33 rules)", "/models/explain")
    registry.add_footer("Learn and about", "Attack yourself", "/attack")
    registry.add_related("results", "Attack yourself", "/attack")

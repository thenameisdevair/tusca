from rich.console import Console

console = Console()


class CreditTracker:
    def __init__(self, budget: int = 2000):
        self.budget = budget
        self.spent = 0
        self.log: list[dict] = []

    def charge(self, endpoint: str, amount: int) -> bool:
        """Charge credits and return False if budget exceeded."""
        if self.spent + amount > self.budget:
            console.print(
                f"[red]Credit budget exceeded. Spent: {self.spent}/{self.budget}. "
                f"Skipping: {endpoint} ({amount} cr)[/red]"
            )
            return False
        self.spent += amount
        self.log.append({"endpoint": endpoint, "credits": amount, "total": self.spent})
        console.print(
            f"[dim]  ↳ {endpoint} [{amount} cr] — total spent: {self.spent}/{self.budget}[/dim]"
        )
        return True

    def summary(self) -> str:
        lines = ["## Credit Usage\n"]
        lines.append(f"| Endpoint | Credits |")
        lines.append(f"|----------|---------|")
        for entry in self.log:
            lines.append(f"| {entry['endpoint']} | {entry['credits']} |")
        lines.append(f"\n**Total: {self.spent} / {self.budget} credits used**")
        return "\n".join(lines)
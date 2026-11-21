from dataclasses import dataclass
from .models import ContractError, GoalContract, identifier


def positive(value):
    if type(value) is not int or not 1 <= value <= 10**15:
        raise ContractError('Expected a positive bounded integer')


@dataclass(frozen=True)
class BudgetVector:
    blocks: int
    cost: int

    def __post_init__(self):
        positive(self.blocks)
        positive(self.cost)


@dataclass(frozen=True)
class Launch:
    launch_id: str
    mission_id: str
    goal: GoalContract
    grid: tuple[int, int]
    budget: BudgetVector
    policy: str
    scope: str
    scope_locks: tuple[str, ...]
    priority: int
    weight: int
    depends_on: tuple[str, ...]
    expires_at: int

    def __post_init__(self):
        for value in (self.launch_id, self.mission_id, self.policy, self.scope):
            identifier(value)
        if type(self.goal) is not GoalContract or type(self.budget) is not BudgetVector:
            raise ContractError('Launch requires a goal contract and budget vector')
        if type(self.grid) is not tuple or len(self.grid) != 2:
            raise ContractError('Grid is variants by depth')
        for value in (*self.grid, self.weight, self.expires_at):
            positive(value)
        if type(self.priority) is not int or not -1000 <= self.priority <= 1000:
            raise ContractError('Invalid priority')
        for values in (self.scope_locks, self.depends_on):
            if (type(values) is not tuple or len(values) > 32
                    or any(type(value) is not str for value in values) or len(set(values)) != len(values)):
                raise ContractError('Expected bounded unique immutable scopes or events')
        if not self.scope_locks:
            raise ContractError('Explicit scope locks required')
        for scope in self.scope_locks:
            if type(scope) is not str or len(scope) > 512:
                raise ContractError('Invalid scope')
            for part in scope.split('/'):
                identifier(part)
                if part in ('.', '..'):
                    raise ContractError('Scope must be canonical')
        for event in self.depends_on:
            identifier(event)


@dataclass(frozen=True)
class Block:
    launch: Launch
    index: int
    cost: int

    @property
    def variant(self):
        return self.index % self.launch.grid[0]

    @property
    def depth(self):
        return self.index // self.launch.grid[0]

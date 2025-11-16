from dataclasses import dataclass
from typing import Optional


@dataclass
class Employer:
    hh_id: str
    name: str


@dataclass
class Job:
    hh_id: str
    name: str
    employer: Employer
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None

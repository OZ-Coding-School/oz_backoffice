"""organization 공개 조회 (다른 컨텍스트용).

app.main이 app.state.employee_queries에 연결한다(decisions B10).
"""

import uuid

from app.contexts.organization.domain.repositories import EmployeeRepository


class EmployeeQueries:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def exists(self, employee_id: uuid.UUID) -> bool:
        return await self._employees.get(employee_id) is not None

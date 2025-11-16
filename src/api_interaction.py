import requests

from src.vacancy_interaction import Employer, Job


class HeadHunterAPI:
    def __init__(self, email: str):
        self._email = email
        self._url = "https://api.hh.ru/vacancies"
        self._headers = {"User-Agent": f"JobSearch/1.0 ({email})"}

    def get_employer_vacancies(self, employer: Employer) -> list[Job]:
        """Получает информацию от hh.ru"""
        response = requests.get(
            "https://api.hh.ru/vacancies",
            params={"employer_id": employer.hh_id, "per_page": 100},
            headers=self._headers,
        )
        data = response.json()
        jobs = []
        for item in data["items"]:
            salary_data = item.get("salary", {})
            if salary_data is None:
                salary_data_from = None
                salary_data_to = None
            else:
                salary_data_from = salary_data.get("from")
                salary_data_to = salary_data.get("to")
            job = Job(
                hh_id=item["id"],
                name=item["name"],
                employer=employer,
                salary_from=salary_data_from,
                salary_to=salary_data_to,
            )
            jobs.append(job)

        return jobs

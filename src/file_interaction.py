import json
from pathlib import Path
from typing import Any, Dict, List

import psycopg2
from psycopg2 import sql

from src.api_interaction import HeadHunterAPI
from src.vacancy_interaction import Employer, Job

BASE_DIR = Path(__file__).resolve().parent.parent


class JSONManager:
    @staticmethod
    def read_employers_from_json(file_path: str) -> List[Employer]:
        """
        Получает информацию из JSON-фвйла
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            employers = []
            for item in data:
                if isinstance(item, dict):
                    employer_id = item.get("hh_id") or item.get("id")
                    name = item.get("name")
                    if employer_id and name:
                        employer = Employer(
                            hh_id=str(employer_id),
                            name=name,
                        )
                        employers.append(employer)
                    else:
                        print(
                            f"Предупреждение: некоторая информация была пропущена: {item}"
                        )
                else:
                    print(
                        f"Предупреждение: пропущена информация не являющаяся словарем: {item}"
                    )

            print(
                f"Успешно загружено {len(employers)} работодателей из файла по адресу: {file_path}"
            )
            return employers

        except FileNotFoundError:
            print(f"Ошибка: файл по адресу {file_path} не найден.")
            return []
        except json.JSONDecodeError as e:
            print(f"Ошибка: неверный формат JSON-файла {file_path}: {e}")
            return []
        except Exception as e:
            print(f"Возникла ошибка причтении файла: {e}")
            return []


class DatabaseManager:
    def __init__(self, connection_string: str):
        self.conn_string = connection_string

    def save_employer(self, employer: Employer) -> bool:
        """Сохраняет информацию о работодателе в базу данных"""
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO employers (hh_id, name)
                        VALUES (%s, %s)
                        ON CONFLICT (hh_id) DO UPDATE SET
                        name = EXCLUDED.name
                    """,
                        (employer.hh_id, employer.name),
                    )
                conn.commit()
            return True
        except Exception as e:
            print(f"Возникла ошибка при сохранении данных {employer.hh_id}: {e}")
            return False

    def save_job(self, job: Job) -> bool:
        """Сохраняет инфорамацию о вакансии в базу данных"""
        if not self.save_employer(job.employer):
            return False
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                                        INSERT INTO jobs (hh_id, name, employer_id, salary_from, salary_to)
                                        VALUES (%s, %s, %s, %s, %s)
                                        ON CONFLICT (hh_id) DO UPDATE SET
                                        name = EXCLUDED.name,
                                        salary_from = EXCLUDED.salary_from,
                                        salary_to = EXCLUDED.salary_to
                                   """,
                        (
                            job.hh_id,
                            job.name,
                            job.employer.hh_id,
                            job.salary_from,
                            job.salary_to,
                        ),
                    )
                conn.commit()
            return True
        except Exception as e:
            print(f"Возникла ошибка при сохранении данных {job.hh_id}: {e}")
            return False

    def save_employers_bulk(self, employers: List[Employer]) -> int:
        """
        Сохраняет информацию о нескольких работодателях
        """
        saved_count = 0
        for employer in employers:
            if self.save_employer(employer):
                saved_count += 1

        print(f"Успешно сохранено {saved_count} из {len(employers)} работодателей")
        return saved_count

    def get_all_employers(self) -> List[Employer]:
        """Из базы данных в экземпляры класса Employer"""
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT hh_id, name
                        FROM employers 
                        ORDER BY name
                    """
                    )
                    rows = cur.fetchall()

                    employers = []
                    for row in rows:
                        employer = Employer(
                            hh_id=row[0],
                            name=row[1],
                        )
                        employers.append(employer)

                    return employers

        except Exception as e:
            print(f"Ошибка при загрузке информации из базы данных: {e}")
            return []

    def get_all_jobs(self) -> List[Employer]:
        """Из базы данных в экземпляры класса Job"""
        try:
            with psycopg2.connect(self.conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT j.hh_id, j.name, j.salary_from, e.name as employer_name
                        FROM jobs j
                        JOIN employers e ON j.employer_id=e.hh_id
                        ORDER BY j.salary_from
                    """
                    )
                    rows = cur.fetchall()

                    results = []
                    for row in rows:

                        results.append(
                            {
                                "id": row[0],
                                "name": row[1],
                                "salary": float(row[2]) if row[2] else None,
                                "employer_name": row[3],
                            }
                        )

                    return results

        except Exception as e:
            print(f"Ошибка получения информации из базы данных: {e}")
            return []

    def get_employers_job_counts(self) -> List[Dict[str, Any]]:
        """
        получает список всех компаний и количество вакансий
        у каждой компании.
        """
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 
                        e.name as employer_name,
                        COUNT(j.hh_id) as job_count,
                        AVG(COALESCE(j.salary_from, j.salary_to, 
                                   (j.salary_from + j.salary_to) / 2)) as avg_salary
                    FROM employers e
                    LEFT JOIN jobs j ON e.hh_id = j.employer_id
                    GROUP BY e.hh_id, e.name
                    ORDER BY job_count DESC, e.name
                """
                )

                results = []
                for row in cur.fetchall():

                    results.append(
                        {
                            "employer_name": row[0],
                            "job_count": row[1],
                            "avg_salary": float(row[2]) if row[2] else None,
                        }
                    )
                return results

    def get_average_salary_by_employer(self):
        """получает среднюю зарплату по вакансиям"""
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.name, 
                           AVG((COALESCE(j.salary_from, 0) + COALESCE(j.salary_to, 0)) / 2) as avg_salary
                    FROM employers e
                    JOIN jobs j ON e.hh_id = j.employer_id
                    WHERE j.salary_from IS NOT NULL OR j.salary_to IS NOT NULL
                    GROUP BY e.name
                    ORDER BY avg_salary DESC
                """
                )
                results = []
                for row in cur.fetchall():
                    results.append(
                        {
                            "employer_name": row[0],
                            "avg_salary": float(row[1]) if row[1] else None,
                        }
                    )
                return results

    def get_jobs_above_average_salary(self):
        """получает список всех вакансий, у которых зарплата
        выше средней по всем вакансиям."""
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH employer_avg AS (
                        SELECT employer_id, 
                               AVG((COALESCE(salary_from, 0) + COALESCE(salary_to, 0)) / 2) as avg_salary
                        FROM jobs
                        WHERE salary_from IS NOT NULL OR salary_to IS NOT NULL
                        GROUP BY employer_id
                    )
                    SELECT j.hh_id, j.name, e.name as employer,
                           (COALESCE(j.salary_from, 0) + COALESCE(j.salary_to, 0)) / 2 as job_salary,
                           ea.avg_salary as employer_avg_salary
                    FROM jobs j
                    JOIN employers e ON j.employer_id = e.hh_id
                    JOIN employer_avg ea ON j.employer_id = ea.employer_id
                    WHERE (COALESCE(j.salary_from, 0) + COALESCE(j.salary_to, 0)) / 2 > ea.avg_salary
                    ORDER BY e.name, job_salary DESC
                """
                )
                results = []
                for row in cur.fetchall():

                    results.append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "employer": row[2],
                            "salary": float(row[3]) if row[3] else None,
                        }
                    )
                return results

    def search_jobs_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """
        получает список всех вакансий, в названии которых
        содержатся переданные в метод слово
        """
        with psycopg2.connect(self.conn_string) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT 
                        j.hh_id,
                        j.name,
                        e.name as employer_name,
                        j.salary_from,
                        j.salary_to
                    FROM employers e
                    LEFT JOIN jobs j ON e.hh_id = j.employer_id
                    WHERE j.name LIKE %s 
                """,
                    (f"%{keyword}%",),
                )

                results = []

                for row in cur.fetchall():

                    results.append(
                        {
                            "hh_id": row[0],
                            "name": row[1],
                            "employer": row[2],
                            "salary_from": float(row[3]) if row[3] else None,
                            "salary_to": float(row[4]) if row[4] else None,
                        }
                    )
                return results

    def get_connection_info(self):
        """Получает информацию от пользователя для соединения с PostgreSQL"""
        print("\n=== Создание базы данных ===")
        print("Введите информацию для создания базы данных PostgreSQL.")

        host = input("PostgreSQL host [localhost]: ").strip() or "localhost"
        port = input("PostgreSQL port [5432]: ").strip() or "5432"
        user = input("PostgreSQL user [postgres]: ").strip() or "postgres"
        password = input("PostgreSQL password: ")
        database = input("Database name [job_tracker]: ").strip() or "job_tracker"

        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
        }

    def connect_to_postgres(self, connection_info, database=None):
        """Подсоединение к базе данных"""
        try:
            dbname = database or "postgres"
            conn = psycopg2.connect(
                host=connection_info["host"],
                port=connection_info["port"],
                user=connection_info["user"],
                password=connection_info["password"],
                dbname=dbname,
            )
            return conn
        except psycopg2.OperationalError as e:
            print(f"Ошибка при попытке соединения к базе данных: {e}")
            return None

    def database_exists(self, connection_info, database_name):
        """Проверка существования базы данных"""
        conn = self.connect_to_postgres(connection_info)
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
                )
                return cur.fetchone() is not None
        finally:
            conn.close()

    def create_database(self, connection_info, database_name):
        """Создает базу данных"""
        if self.database_exists(connection_info, database_name):
            print(f"База данных '{database_name}' уже существует.")
            return True

        conn = self.connect_to_postgres(connection_info)
        if not conn:
            return False
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                )
            print(f"База данных '{database_name}' создана.")
            return True
        except Exception as e:
            print(f"Ошибка при создании базы данных: {e}")
            return False
        finally:
            conn.close()

    def setup_complete_database(self):
        """Установка базы данных"""
        connection_info = self.get_connection_info()
        database_name = connection_info["database"]
        if not self.create_database(connection_info, database_name):
            return None
        conn = self.connect_to_postgres(connection_info, database_name)
        if not conn:
            return None
        try:
            self.create_tables(conn)
            print("Таблицы созданы!")
            return f"postgresql://{connection_info['user']}:{connection_info['password']}@{connection_info['host']}:{connection_info['port']}/{database_name}"
        except Exception as e:
            print(f"Ошибка при создании таблиц: {e}")
            return None
        finally:
            conn.close()

    def create_tables(self, connection):
        """Создание таблиц"""
        with connection.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employers (
                    hh_id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL
                );
            """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    hh_id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    employer_id VARCHAR(100) REFERENCES employers(hh_id),
                    salary_from INTEGER,
                    salary_to INTEGER
                );
            """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_employer_id ON jobs(employer_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_salary ON jobs(salary_from, salary_to);"
            )

        connection.commit()
        emp = JSONManager.read_employers_from_json(
            str(BASE_DIR / "data/employers.json")
        )
        self.save_employers_bulk(emp)


class UserInterface:
    def __init__(self):
        self.connection_string = None
        self.db = None
        self.api = None

        self.setup_database()

    def setup_database(self):
        """Доступ к базе данных"""
        password = input("Введите password: ").strip()
        self.connection_string = (
            f"postgresql://postgres:{password}@localhost:5432/job_tracker"
        )
        if not self.test_connection(
            f"postgresql://postgres:{password}@localhost:5432/job_tracker"
        ):
            self.setup_new_database()

        self.initialize_services()

    def setup_new_database(self):
        """Запуск при создании новой базы"""
        setup = DatabaseManager(self.connection_string)
        self.connection_string = setup.setup_complete_database()

    def test_connection(self, connection_string):
        """Проверка существования базы данных"""
        try:
            import psycopg2

            conn = psycopg2.connect(connection_string)
            conn.close()
            return True
        except Exception as e:
            print(f"Тест соединения неудачен: {e}")
            return False

    def initialize_services(self):
        """Запуск функций"""
        self.db = DatabaseManager(self.connection_string)
        email = input("Введите e-mail: ").strip()
        self.api = HeadHunterAPI(email)

    def start(self):
        """Основное меню"""
        if not self.db:
            print("База данных не открыта!")
            return

        while True:
            print("\n=== Возмжные действия ===")
            print("1. Посмотреть имеющуюся информация по работадателям")
            print("2. Получить информацию о вакансиях из интернета по работадателям")
            print("3. Посмотреть информацию в базе данных")
            print("4. Информация о базе данных")
            print("5. Выход")

            choice = input("Выберите действие: ").strip()

            if choice == "1":
                self.view_all_employers()
            elif choice == "2":
                self.fetch_jobs()
            elif choice == "3":
                self.show_statistics()
            elif choice == "4":
                self.show_database_info()
            elif choice == "5":
                break
            else:
                print("Недопустимый ответ")

    def view_all_employers(self):
        """Информация о всех работодателях в базе данных"""
        employers = self.db.get_all_employers()
        if not employers:
            print("Информации о работодателях не найдено в базе данных.")
            return

        print(f"\nНайдено {len(employers)} работодателях:")
        for i, employer in enumerate(employers, 1):
            print(f"{i}. {employer.name} (ID: {employer.hh_id})")

    def show_database_info(self):
        """Информация о соединении с базой данных"""
        safe_connection = self.connection_string
        if "@" in safe_connection:
            parts = safe_connection.split("@")
            user_part = parts[0]
            if ":" in user_part:
                protocol, credentials = user_part.split("://")
                user, _ = credentials.split(":")
                safe_connection = f"{protocol}://{user}:****@{parts[1]}"
        print(f"\nDatabase: {safe_connection}")
        try:
            with psycopg2.connect(self.connection_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM employers")
                    employer_count = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM jobs")
                    job_count = cur.fetchone()[0]

                    print(f"Employers in database: {employer_count}")
                    print(f"Jobs in database: {job_count}")
        except Exception as e:
            print(f"Error getting database info: {e}")

    def show_statistics(self):
        """Меню информации из базы данных"""
        while True:
            print("\n=== Информация из базы данных ===")
            print("1. Компании и количество вакансий")
            print("2. Вакансии по ключевому слову")
            print("3. Средняя зарплата по вакансиям ")
            print("4. Вакансии, у которых зарплата выше средней")
            print("5. Вакансии с указанием названия компании")
            print("6. Обратно")

            choice = input("Выберете действие: ").strip()

            if choice == "1":
                self.show_employers_job_counts()
            elif choice == "2":
                self.show_jobs_by_keyword()
            elif choice == "3":
                self.show_average_salary()
            elif choice == "4":
                self.show_above_average_salary()
            elif choice == "5":
                self.show_all_jobs()
            elif choice == "6":
                break
            else:
                print("Недопустимый ответ")

    def show_average_salary(self):
        """Средняя зарплата"""
        results = self.db.get_average_salary_by_employer()
        print(f"\nНайдено {len(results)} позиции:")
        print(f"{'Компания':<25}  {'з/п':<15} ")
        print("-" * 60)
        for emp in results:
            print(f"{emp['employer_name']:<25}  {round(emp['avg_salary'],2):<6} ")

    def show_above_average_salary(self):
        """Зарплата выше средней"""
        results = self.db.get_jobs_above_average_salary()
        print(f"\nНайдено {len(results)} :")
        print(f"{'Компания':<15}  {'з/п':<15} {'Должность':<15}")
        print("-" * 60)
        for emp in results:
            print(f"{emp['employer']:<15} {emp['salary']:<15} {emp['name']:<25}   ")

    def show_employers_job_counts(self):
        """Количество вакансий по работодателю"""
        results = self.db.get_employers_job_counts()

        if not results:
            print("Нет данных.")
            return

        print(f"\n{'Компания':<30} {'Количество':<15}{'Средняя з/п':<15}")
        print("-" * 60)

        for emp in results:
            salary_display = f"{emp['avg_salary']:,.0f}" if emp["avg_salary"] else "N/A"
            print(
                f"{emp['employer_name']:<30} {emp['job_count']:<15}  {salary_display:<15}"
            )

        total_jobs = sum(emp["job_count"] for emp in results)
        print(f"\nВсего вакансий: {total_jobs}")

    def fetch_jobs(self):
        """Получить вакансии по работодателям"""
        employers = self.db.get_all_employers()
        if not employers:
            print("Нет информации по работодателям.")
            return

        print(f"Скачиваем информацию о вакансиях по {len(employers)} работодателям...")

        total_jobs = 0
        for employer in employers:
            try:
                jobs = self.api.get_employer_vacancies(employer)
                saved_count = 0

                for job in jobs:

                    if self.db.save_job(job):
                        saved_count += 1

                total_jobs += saved_count
                print(f"  {employer.name}: {saved_count} новая вакансия")

            except Exception as e:
                print(f"  Ошибка при скачивании информации {employer.name}: {e}")

        print(f"\nВсего: {total_jobs} новых вакансий")

    def show_jobs_by_keyword(self):
        keyword = input("Введите ключевое слово: ").strip()
        if not keyword:
            print("Ключевого слова не введено.")
        results = self.db.search_jobs_by_keyword(keyword)
        if not results:
            print("Нет данных.")
            return

        print(f"\n{'Компания ':<15} {'Должность':<15}")
        print("-" * 60)

        for emp in results:
            print(f"{emp['employer']:<15} {emp['name']:<6}")

    def show_all_jobs(self):
        results = self.db.get_all_jobs()
        print(f"\nНайдено {len(results)} :")
        print(f"{'id':<10}  {'з/п':<15} {'Компания':<15} {'Должность':<15}")
        print("-" * 80)
        for emp in results:
            print(
                f"{emp['id']}   {emp['salary']}    {emp['employer_name']:<15} {emp['name']:<15} "
            )

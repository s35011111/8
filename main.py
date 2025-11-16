from src.file_interaction import UserInterface


def main():

    print("Приложение для анализа и хранения данных скачаных с hh.ru.")

    try:
        ui = UserInterface()
        ui.start()
    except KeyboardInterrupt:
        print("\n\nПриложение будет закрыто")
    except Exception as e:
        print(f"Во время работы приложения возникла ошибка: {e}")


if __name__ == "__main__":
    main()
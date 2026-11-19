import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Difficulty:
    name: str
    maximum: int
    attempts: int


DIFFICULTIES = {
    "1": Difficulty("Легко", 50, 10),
    "2": Difficulty("Нормально", 100, 7),
    "3": Difficulty("Сложно", 500, 8),
}


def choose_difficulty() -> Difficulty:
    print("\nВыберите сложность:")
    for key, difficulty in DIFFICULTIES.items():
        print(
            f"{key}. {difficulty.name}: число от 1 до {difficulty.maximum}, "
            f"попыток — {difficulty.attempts}"
        )

    while True:
        choice = input("Ваш выбор: ").strip()
        if choice in DIFFICULTIES:
            return DIFFICULTIES[choice]
        print("Выберите вариант 1, 2 или 3.")


def show_hint(number: int, guess: int, lower_bound: int, upper_bound: int) -> None:
    distance = abs(number - guess)
    if distance <= 5:
        print("Подсказка: очень близко!")
    elif distance <= 20:
        print("Подсказка: близко.")
    else:
        print("Подсказка: пока далеко.")

    print(f"Число {'чётное' if number % 2 == 0 else 'нечётное'}.")
    print(f"Оно находится между {lower_bound} и {upper_bound}.")


def play_round() -> None:
    difficulty = choose_difficulty()
    number = random.randint(1, difficulty.maximum)
    lower_bound = 1
    upper_bound = difficulty.maximum
    used_guesses = set()
    score = 0

    print(
        f"\nЯ загадал число от 1 до {difficulty.maximum}. "
        f"У вас {difficulty.attempts} попыток."
    )

    for attempt in range(1, difficulty.attempts + 1):
        remaining = difficulty.attempts - attempt + 1
        try:
            guess = int(input(f"Попытка {attempt}/{difficulty.attempts}. Ваш вариант: "))
        except ValueError:
            print("Введите целое число — такая попытка не засчитывается.")
            continue

        if not 1 <= guess <= difficulty.maximum:
            print(f"Введите число от 1 до {difficulty.maximum}.")
            continue
        if guess in used_guesses:
            print("Вы уже называли это число. Попробуйте другое.")
            continue

        used_guesses.add(guess)
        score = max(0, (difficulty.attempts - attempt + 1) * 10)

        if guess == number:
            print(f"\nПобеда! Вы угадали за {attempt} попыток.")
            print(f"Ваш счёт: {score} очков.")
            return

        if guess < number:
            lower_bound = max(lower_bound, guess + 1)
            print("Загаданное число больше.")
        else:
            upper_bound = min(upper_bound, guess - 1)
            print("Загаданное число меньше.")

        if remaining > 1:
            show_hint(number, guess, lower_bound, upper_bound)

    print(f"\nПопытки закончились. Было загадано число {number}.")
    print("В следующий раз получится!")


def main() -> None:
    print("=== Угадай число ===")
    while True:
        play_round()
        answer = input("\nСыграть ещё раз? (д/н): ").strip().lower()
        if answer not in {"д", "да", "y", "yes"}:
            print("Спасибо за игру!")
            break


if __name__ == "__main__":
    main()

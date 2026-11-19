import random


MODES = {
    "1": ("Новичок", 50, 10),
    "2": ("Профи", 100, 7),
    "3": ("Мифик", 500, 8),
}


def choose_mode():
    print("\n// ВЫБЕРИ СЕКТОР")
    for key, (name, maximum, attempts) in MODES.items():
        print(f"  {key}. {name} — {maximum} координат, {attempts} ходов")
    while True:
        choice = input("Сектор: ").strip()
        if choice in MODES:
            name, maximum, attempts = MODES[choice]
            return name, maximum, attempts
        print("Выбери 1, 2 или 3.")


def play_round():
    name, maximum, attempts = choose_mode()
    target = random.randint(1, maximum)
    used = set()
    lower, upper = 1, maximum

    print(f"\nNUM//HUNT :: режим «{name}»")
    print(f"Цель скрыта в секторе 1–{maximum}. Ходов: {attempts}.\n")

    for attempt in range(1, attempts + 1):
        try:
            guess = int(input(f"[{attempt}/{attempts}] Координата: ").strip())
        except ValueError:
            print("! Нужна целая координата. Ход не засчитан.")
            continue

        if not 1 <= guess <= maximum:
            print(f"! Координата вне диапазона 1–{maximum}")
            continue
        if guess in used:
            print("! Эта координата уже была проверена")
            continue

        used.add(guess)
        if guess == target:
            score = (attempts - attempt + 1) * 100
            print(f"\nDIRECT HIT! Цель найдена за {attempt} ходов.")
            print(f"Скор: {score} XP")
            return

        if guess < target:
            lower = max(lower, guess + 1)
            direction = "выше"
        else:
            upper = min(upper, guess - 1)
            direction = "ниже"

        distance = abs(target - guess)
        ratio = distance / maximum
        heat = "ОГОНЬ" if ratio <= .03 else "ЖАРКО" if ratio <= .10 else "ТЕПЛО" if ratio <= .22 else "ХОЛОДНО"
        print(f"Цель {direction} · {heat} · зона {lower}–{upper}")

    print(f"\nСектор закрыт. Загаданное число: {target}")


def main():
    print("=== NUM//HUNT ===")
    streak = 0
    while True:
        play_round()
        again = input("\nЗапустить новый сектор? (д/н): ").strip().lower()
        if again not in {"д", "да", "y", "yes"}:
            print("Сессия завершена.")
            break


if __name__ == "__main__":
    main()

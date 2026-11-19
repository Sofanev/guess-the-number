import random


def main():
    number = random.randint(1, 100)
    attempts = 0

    print("Я загадал число от 1 до 100.")
    print("Попробуйте угадать!")

    while True:
        try:
            guess = int(input("Ваш вариант: "))
        except ValueError:
            print("Введите целое число.")
            continue

        if not 1 <= guess <= 100:
            print("Введите число от 1 до 100.")
            continue

        attempts += 1

        if guess < number:
            print("Слишком мало!")
        elif guess > number:
            print("Слишком много!")
        else:
            print(f"Верно! Вы угадали за {attempts} попыток.")
            break


if __name__ == "__main__":
    main()

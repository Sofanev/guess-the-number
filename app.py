import random
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"

DIFFICULTIES = {
    "easy": {"name": "Легко", "maximum": 50, "attempts": 10},
    "normal": {"name": "Нормально", "maximum": 100, "attempts": 7},
    "hard": {"name": "Сложно", "maximum": 500, "attempts": 8},
}


def start_game(level="normal"):
    difficulty = DIFFICULTIES.get(level, DIFFICULTIES["normal"])
    session["game"] = {
        "level": level,
        "number": random.randint(1, difficulty["maximum"]),
        "attempts_used": 0,
        "used_guesses": [],
        "lower_bound": 1,
        "upper_bound": difficulty["maximum"],
        "status": "playing",
        "message": "Игра началась! Сделайте первую попытку.",
        "message_type": "info",
        "score": 0,
    }


def current_game():
    game = session.get("game")
    if not game or game["level"] not in DIFFICULTIES:
        start_game()
        game = session["game"]
    return game


@app.route("/", methods=["GET", "POST"])
def index():
    game = current_game()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "new_game":
            start_game(request.form.get("level", game["level"]))
            return redirect(url_for("index"))

        if game["status"] != "playing":
            game["message"] = "Раунд завершён. Начните новую игру."
            game["message_type"] = "warning"
        else:
            raw_guess = request.form.get("guess", "").strip()
            try:
                guess = int(raw_guess)
            except ValueError:
                game["message"] = "Введите целое число."
                game["message_type"] = "error"
            else:
                difficulty = DIFFICULTIES[game["level"]]
                if not 1 <= guess <= difficulty["maximum"]:
                    game["message"] = f"Введите число от 1 до {difficulty['maximum']}."
                    game["message_type"] = "error"
                elif guess in game["used_guesses"]:
                    game["message"] = "Вы уже называли это число. Попробуйте другое."
                    game["message_type"] = "warning"
                else:
                    game["used_guesses"].append(guess)
                    game["attempts_used"] += 1
                    remaining = difficulty["attempts"] - game["attempts_used"]

                    if guess == game["number"]:
                        game["status"] = "won"
                        game["score"] = max(10, (remaining + 1) * 10)
                        game["message"] = (
                            f"Победа! Вы угадали число за {game['attempts_used']} попыток "
                            f"и набрали {game['score']} очков."
                        )
                        game["message_type"] = "success"
                    else:
                        if guess < game["number"]:
                            game["lower_bound"] = max(game["lower_bound"], guess + 1)
                            direction = "больше"
                        else:
                            game["upper_bound"] = min(game["upper_bound"], guess - 1)
                            direction = "меньше"

                        if remaining <= 0:
                            game["status"] = "lost"
                            game["message"] = (
                                f"Попытки закончились. Было загадано число {game['number']}."
                            )
                            game["message_type"] = "error"
                        else:
                            distance = abs(game["number"] - guess)
                            closeness = "очень близко" if distance <= 5 else (
                                "близко" if distance <= 20 else "пока далеко"
                            )
                            parity = "чётное" if game["number"] % 2 == 0 else "нечётное"
                            game["message"] = (
                                f"Загаданное число {direction}. Подсказка: {closeness}. "
                                f"Оно {parity}."
                            )
                            game["message_type"] = "info"

        session.modified = True

    return render_template("index.html", game=game, difficulties=DIFFICULTIES)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

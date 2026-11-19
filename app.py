import random
import time

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key-before-deploying"

DIFFICULTIES = {
    "rookie": {"name": "Новичок", "maximum": 50, "attempts": 10, "time": 75, "accent": "lime"},
    "pro": {"name": "Профи", "maximum": 100, "attempts": 7, "time": 60, "accent": "violet"},
    "mythic": {"name": "Мифик", "maximum": 500, "attempts": 8, "time": 90, "accent": "pink"},
}


def get_profile():
    profile = session.get("profile")
    if not profile:
        profile = {"xp": 0, "wins": 0, "streak": 0, "best_streak": 0, "guesses": 0}
        session["profile"] = profile
    return profile


def start_game(level="pro"):
    difficulty = DIFFICULTIES.get(level, DIFFICULTIES["pro"])
    session["game"] = {
        "level": level,
        "number": random.randint(1, difficulty["maximum"]),
        "attempts_used": 0,
        "used_guesses": [],
        "lower_bound": 1,
        "upper_bound": difficulty["maximum"],
        "status": "playing",
        "message": "Сектор открыт. Сделай первый ход.",
        "message_type": "info",
        "score": 0,
        "started_at": time.time(),
        "time_limit": difficulty["time"],
        "hints_left": 2,
        "combo": 1,
        "history": [],
    }


def current_game():
    game = session.get("game")
    if not game or game["level"] not in DIFFICULTIES:
        start_game()
        game = session["game"]
    return game


def seconds_left(game):
    elapsed = time.time() - game["started_at"]
    return max(0, int(game["time_limit"] - elapsed))


def heat_label(game, guess):
    distance = abs(game["number"] - guess)
    maximum = DIFFICULTIES[game["level"]]["maximum"]
    ratio = distance / maximum
    if ratio <= 0.03:
        return "ОГОНЬ"
    if ratio <= 0.10:
        return "ЖАРКО"
    if ratio <= 0.22:
        return "ТЕПЛО"
    return "ХОЛОДНО"


@app.route("/", methods=["GET", "POST"])
def index():
    get_profile()
    game = current_game()

    if request.method == "POST":
        action = request.form.get("action", "guess")

        if action == "new_game":
            start_game(request.form.get("level", game["level"]))
            return redirect(url_for("index"))

        if action == "reset_stats":
            session["profile"] = {"xp": 0, "wins": 0, "streak": 0, "best_streak": 0, "guesses": 0}
            return redirect(url_for("index"))

        if action == "hint" and game["status"] == "playing":
            if game["hints_left"] > 0:
                game["hints_left"] -= 1
                number = game["number"]
                if game["hints_left"] == 1:
                    clue = "Это " + ("чётное" if number % 2 == 0 else "нечётное") + " число"
                else:
                    zone = max(1, (number - 1) // 10 * 10)
                    clue = f"Цель находится в зоне примерно {zone}–{min(zone + 9, DIFFICULTIES[game['level']]['maximum'])}"
                game["message"] = "СКАН: " + clue
                game["message_type"] = "hint"
            else:
                game["message"] = "Сканы закончились на этот раунд"
                game["message_type"] = "warning"

        elif game["status"] != "playing":
            game["message"] = "Раунд завершён. Запускай следующий сектор!"
            game["message_type"] = "warning"

        elif action == "guess":
            if seconds_left(game) <= 0:
                game["status"] = "lost"
                game["message"] = f"Время вышло. Загаданное число: {game['number']}"
                game["message_type"] = "error"
                session["profile"]["streak"] = 0
            else:
                raw_guess = request.form.get("guess", "").strip()
                try:
                    guess = int(raw_guess)
                except ValueError:
                    game["message"] = "Введите целое число"
                    game["message_type"] = "error"
                else:
                    maximum = DIFFICULTIES[game["level"]]["maximum"]
                    if not 1 <= guess <= maximum:
                        game["message"] = f"Координаты вне диапазона: 1–{maximum}"
                        game["message_type"] = "error"
                    elif guess in game["used_guesses"]:
                        game["message"] = "Эту координату ты уже проверял"
                        game["message_type"] = "warning"
                    else:
                        game["used_guesses"].append(guess)
                        game["attempts_used"] += 1
                        session["profile"]["guesses"] += 1
                        difficulty = DIFFICULTIES[game["level"]]
                        remaining = difficulty["attempts"] - game["attempts_used"]

                        if guess == game["number"]:
                            profile = session["profile"]
                            game["status"] = "won"
                            game["combo"] = min(profile["streak"] + 1, 5)
                            game["score"] = 100 + remaining * 40 + seconds_left(game) * 2
                            game["score"] *= DIFFICULTIES[game["level"]]["maximum"] // 100 + 1
                            profile["xp"] += game["score"]
                            profile["wins"] += 1
                            profile["streak"] += 1
                            profile["best_streak"] = max(profile["best_streak"], profile["streak"])
                            game["message"] = f"DIRECT HIT! Сектор взят за {game['attempts_used']} ходов"
                            game["message_type"] = "success"
                            game["history"].append({"guess": guess, "heat": "HIT", "direction": "цель"})
                        else:
                            if guess < game["number"]:
                                game["lower_bound"] = max(game["lower_bound"], guess + 1)
                                direction = "выше"
                            else:
                                game["upper_bound"] = min(game["upper_bound"], guess - 1)
                                direction = "ниже"

                            heat = heat_label(game, guess)
                            game["history"].append({"guess": guess, "heat": heat, "direction": direction})

                            if remaining <= 0:
                                game["status"] = "lost"
                                game["message"] = f"Попытки на нуле. Цель была {game['number']}"
                                game["message_type"] = "error"
                                session["profile"]["streak"] = 0
                            else:
                                parity = "чётная" if game["number"] % 2 == 0 else "нечётная"
                                game["message"] = f"Цель {direction} · {heat} · Ключ: {parity}"
                                game["message_type"] = "info"

        session.modified = True

    profile = session["profile"]
    level = profile["xp"] // 500 + 1
    level_progress = profile["xp"] % 500
    return render_template(
        "index.html",
        game=game,
        difficulties=DIFFICULTIES,
        profile=profile,
        seconds_left=seconds_left(game),
        level=level,
        level_progress=level_progress,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

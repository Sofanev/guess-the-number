import os
import random
import sqlite3
import time
import uuid
from contextlib import closing

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploying")
app.config["DATABASE"] = os.path.join(app.instance_path, "numhunt.sqlite3")

PLAYERS = ("Софья", "Сергей", "Мила", "Настя")
DIFFICULTIES = {
    "rookie": {"name": "Новичок", "maximum": 50, "attempts": 10, "time": 75, "accent": "lime"},
    "pro": {"name": "Профи", "maximum": 100, "attempts": 7, "time": 60, "accent": "violet"},
    "mythic": {"name": "Мифик", "maximum": 500, "attempts": 8, "time": 90, "accent": "pink"},
}


def connect_db():
    os.makedirs(app.instance_path, exist_ok=True)
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with closing(connect_db()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                name TEXT PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                guesses INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                player TEXT NOT NULL REFERENCES players(name),
                outcome TEXT NOT NULL,
                score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.executemany("INSERT OR IGNORE INTO players (name) VALUES (?)", [(name,) for name in PLAYERS])
        db.commit()


def player_name():
    name = session.get("player")
    if name not in PLAYERS:
        name = PLAYERS[0]
        session["player"] = name
    return name


def get_profile(name):
    with closing(connect_db()) as db:
        row = db.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()
    return dict(row)


def get_leaderboard():
    with closing(connect_db()) as db:
        rows = db.execute("SELECT * FROM players ORDER BY xp DESC, wins DESC, name ASC").fetchall()
    return [dict(row) for row in rows]


def record_guess(name):
    with closing(connect_db()) as db:
        db.execute("UPDATE players SET guesses = guesses + 1 WHERE name = ?", (name,))
        db.commit()


def save_result(game, name, outcome):
    if game.get("result_saved"):
        return
    with closing(connect_db()) as db:
        db.execute("BEGIN IMMEDIATE")
        if outcome == "won":
            db.execute("""
                UPDATE players
                SET xp = xp + ?, wins = wins + 1, streak = streak + 1,
                    best_streak = MAX(best_streak, streak + 1)
                WHERE name = ?
            """, (game["score"], name))
        else:
            db.execute("UPDATE players SET streak = 0 WHERE name = ?", (name,))
        db.execute("""
            INSERT OR IGNORE INTO results (id, player, outcome, score, difficulty, attempts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (game["id"], name, outcome, game["score"], game["level"], game["attempts_used"]))
        db.commit()
    game["result_saved"] = True


def start_game(level="pro"):
    difficulty = DIFFICULTIES.get(level, DIFFICULTIES["pro"])
    session["game"] = {
        "id": str(uuid.uuid4()),
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
        "history": [],
        "result_saved": False,
    }


def current_game():
    game = session.get("game")
    if not game or game.get("level") not in DIFFICULTIES:
        start_game()
        game = session["game"]
    return game


def seconds_left(game):
    elapsed = time.time() - game["started_at"]
    return max(0, int(game["time_limit"] - elapsed))


def heat_label(game, guess):
    ratio = abs(game["number"] - guess) / DIFFICULTIES[game["level"]]["maximum"]
    if ratio <= 0.03:
        return "ОГОНЬ"
    if ratio <= 0.10:
        return "ЖАРКО"
    if ratio <= 0.22:
        return "ТЕПЛО"
    return "ХОЛОДНО"


def end_by_timeout(game, name):
    if game["status"] == "playing" and seconds_left(game) <= 0:
        game["status"] = "lost"
        game["message"] = f"Время вышло. Загаданное число: {game['number']}"
        game["message_type"] = "error"
        save_result(game, name, "lost")


@app.route("/", methods=["GET", "POST"])
def index():
    name = player_name()
    game = current_game()
    end_by_timeout(game, name)

    if request.method == "POST":
        action = request.form.get("action", "guess")

        if action == "select_player":
            selected = request.form.get("player", "")
            if selected in PLAYERS:
                session["player"] = selected
                start_game(game["level"])
            return redirect(url_for("index"))

        if action == "new_game":
            start_game(request.form.get("level", game["level"]))
            return redirect(url_for("index"))

        if action == "hint" and game["status"] == "playing":
            if game["hints_left"] > 0:
                game["hints_left"] -= 1
                number = game["number"]
                if game["hints_left"] == 1:
                    clue = "Это " + ("чётное" if number % 2 == 0 else "нечётное") + " число"
                else:
                    zone = max(1, (number - 1) // 10 * 10)
                    maximum = DIFFICULTIES[game["level"]]["maximum"]
                    clue = f"Цель находится в зоне примерно {zone}–{min(zone + 9, maximum)}"
                game["message"] = "СКАН: " + clue
                game["message_type"] = "hint"
            else:
                game["message"] = "Сканы закончились на этот раунд"
                game["message_type"] = "warning"

        elif game["status"] != "playing":
            game["message"] = "Раунд завершён. Запускай следующий сектор!"
            game["message_type"] = "warning"

        elif action == "guess":
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
                    record_guess(name)
                    remaining = DIFFICULTIES[game["level"]]["attempts"] - game["attempts_used"]

                    if guess == game["number"]:
                        game["status"] = "won"
                        game["score"] = (100 + remaining * 40 + seconds_left(game) * 2) * (maximum // 100 + 1)
                        game["message"] = f"DIRECT HIT! Сектор взят за {game['attempts_used']} ходов"
                        game["message_type"] = "success"
                        game["history"].append({"guess": guess, "heat": "HIT", "direction": "цель"})
                        save_result(game, name, "won")
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
                            save_result(game, name, "lost")
                        else:
                            parity = "чётная" if game["number"] % 2 == 0 else "нечётная"
                            game["message"] = f"Цель {direction} · {heat} · Ключ: {parity}"
                            game["message_type"] = "info"

        session.modified = True

    profile = get_profile(name)
    leaderboard = get_leaderboard()
    level = profile["xp"] // 500 + 1
    level_progress = profile["xp"] % 500
    return render_template(
        "index.html",
        game=game,
        difficulties=DIFFICULTIES,
        profile=profile,
        players=PLAYERS,
        current_player=name,
        leaderboard=leaderboard,
        seconds_left=seconds_left(game),
        level=level,
        level_progress=level_progress,
    )


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

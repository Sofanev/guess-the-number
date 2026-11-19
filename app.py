import os
import random
import sqlite3
import time
import uuid

from flask import Flask, redirect, render_template, request, session

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "num-hunt-local-secret")
app.config["DATABASE"] = os.path.join(app.instance_path, "numhunt.sqlite3")

PLAYERS = ("Софья", "Сергей", "Мила", "Настя")
DIFFICULTIES = {
    "easy": {"name": "Легко", "maximum": 50, "attempts": 10, "time": 75},
    "normal": {"name": "Нормально", "maximum": 100, "attempts": 7, "time": 60},
    "hard": {"name": "Сложно", "maximum": 500, "attempts": 8, "time": 90},
}

MISSIONS = {
    "easy": {"chapter": "ГЛАВА I", "title": "Сигнал в старом городе", "brief": "Охотники улавливают слабый цифровой след. Сначала найди вход в сеть."},
    "normal": {"chapter": "ГЛАВА II", "title": "Сердце Хранилища", "brief": "Код спрятан за тремя защитными периметрами. Не позволяй системе догадаться о тебе раньше времени."},
    "hard": {"chapter": "ГЛАВА III", "title": "Последний ключ", "brief": "Финальный сектор пробуждён. Только точность и холодная логика помогут раскрыть тайну."},
}


def connect_db():
    os.makedirs(app.instance_path, exist_ok=True)
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS players (
                name TEXT PRIMARY KEY,
                xp INTEGER NOT NULL DEFAULT 0,
                wins INTEGER NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                best_streak INTEGER NOT NULL DEFAULT 0,
                guesses INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                hider_points INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                player TEXT NOT NULL,
                outcome TEXT NOT NULL,
                score INTEGER NOT NULL,
                difficulty TEXT NOT NULL,
                attempts INTEGER NOT NOT NULL,
                mode TEXT NOT NULL,
                hider TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        columns = {row[1] for row in db.execute("PRAGMA table_info(players)")}
        if "losses" not in columns:
            db.execute("ALTER TABLE players ADD COLUMN losses INTEGER NOT NULL DEFAULT 0")
        if "hider_points" not in columns:
            db.execute("ALTER TABLE players ADD COLUMN hider_points INTEGER NOT NULL DEFAULT 0")
        for name in PLAYERS:
            db.execute("INSERT OR IGNORE INTO players(name) VALUES (?)", (name,))


def current_player():
    name = session.get("player")
    if name not in PLAYERS:
        name = "Софья"
        session["player"] = name
    return name


def get_profile(name):
    with connect_db() as db:
        row = db.execute("SELECT * FROM players WHERE name=?", (name,)).fetchone()
    return dict(row)


def get_leaderboard():
    with connect_db() as db:
        rows = db.execute("SELECT * FROM players ORDER BY xp DESC, wins DESC, name ASC").fetchall()
    return [dict(row) for row in rows]


def seconds_left(game):
    if game.get("mode") != "solo":
        return 0
    elapsed = time.time() - game["started_at"]
    return max(0, int(game["time_limit"] - elapsed))


def start_game(level="normal", mode="solo", hider=None, guesser=None):
    difficulty = DIFFICULTIES.get(level, DIFFICULTIES["normal"])
    session["game"] = {
        "id": str(uuid.uuid4()), "level": level, "mode": mode,
        "hider": hider, "guesser": guesser,
        "number": random.randint(1, difficulty["maximum"]) if mode == "solo" else None,
        "phase": "playing" if mode == "solo" else "set_number",
        "attempts_used": 0, "used_guesses": [], "lower_bound": 1,
        "upper_bound": difficulty["maximum"], "status": "playing",
        "message": "Сигнал найден. Сделай первый выстрел." if mode == "solo" else "Хранитель должен ввести секретный ключ.",
        "message_type": "info", "score": 0, "hider_score": 0,
        "started_at": time.time(), "time_limit": difficulty["time"],
        "hints_left": 2, "history": [], "result_saved": False,
    }


def current_game():
    game = session.get("game")
    if not game or game.get("level") not in DIFFICULTIES:
        start_game()
        game = session["game"]
    return game


def heat_label(game, guess):
    ratio = abs(game["number"] - guess) / DIFFICULTIES[game["level"]]["maximum"]
    if ratio <= .03: return "ОГОНЬ"
    if ratio <= .10: return "ЖАРКО"
    if ratio <= .22: return "ТЕПЛО"
    return "ХОЛОДНО"


def calculate_score(game):
    d = DIFFICULTIES[game["level"]]
    remaining = max(0, d["attempts"] - game["attempts_used"])
    difficulty_bonus = {"easy": 100, "normal": 150, "hard": 250}[game["level"]]
    time_bonus = seconds_left(game) * 2 if game["mode"] == "solo" else 0
    return 100 + remaining * 40 + time_bonus + difficulty_bonus


def save_result(game, player, outcome):
    if game.get("result_saved"):
        return
    with connect_db() as db:
        if outcome == "won":
            db.execute("""UPDATE players SET xp=xp+?, wins=wins+1, streak=streak+1,
                best_streak=MAX(best_streak, streak+1) WHERE name=?""", (game["score"], player))
        else:
            db.execute("UPDATE players SET xp=xp+?, losses=losses+1, streak=0 WHERE name=?", (game["score"], player))
        db.execute("""INSERT OR IGNORE INTO results
            (id,player,outcome,score,difficulty,attempts,mode,hider)
            VALUES (?,?,?,?,?,?,?,?)""",
            (game["id"], player, outcome, game["score"], game["level"], game["attempts_used"], game["mode"], game["hider"]))
    game["result_saved"] = True


def record_attempt(player):
    with connect_db() as db:
        db.execute("UPDATE players SET guesses=guesses+1 WHERE name=?", (player,))


@app.route("/", methods=["GET", "POST"])
def index():
    player = current_player()
    game = current_game()

    if game["mode"] == "solo" and game["status"] == "playing" and seconds_left(game) <= 0:
        game.update(status="lost", phase="finished", score=20,
                    message=f"Время вышло. Хранитель скрывал число {game['number']}", message_type="error")
        save_result(game, player, "lost")

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "select_player":
            selected = request.form.get("player", "")
            if selected in PLAYERS:
                session["player"] = selected
            return redirect("/")

        if action == "new_game":
            start_game(request.form.get("level", game["level"]), "solo", guesser=current_player())
            return redirect("/")

        if action == "setup_pass":
            hider = request.form.get("hider", "")
            guesser = request.form.get("guesser", "")
            level = request.form.get("level", game["level"])
            if hider in PLAYERS and guesser in PLAYERS and hider != guesser:
                start_game(level, "pass", hider=hider, guesser=guesser)
                session["player"] = hider
            else:
                game["message"] = "Хранитель и охотник должны быть разными игроками"
                game["message_type"] = "warning"

        elif action == "set_number" and game["mode"] == "pass" and game["phase"] == "set_number":
            maximum = DIFFICULTIES[game["level"]]["maximum"]
            try:
                number = int(request.form.get("secret_number", "").strip())
            except ValueError:
                number = 0
            if 1 <= number <= maximum:
                game["number"] = number
                game["phase"] = "playing"
                session["player"] = game["guesser"]
                game["message"] = f"Ключ спрятан. {game['guesser']} входит в сектор"
                game["message_type"] = "info"
            else:
                game["message"] = f"Ключ должен быть числом от 1 до {maximum}"
                game["message_type"] = "error"

        elif action == "guess" and game["status"] == "playing" and game["phase"] == "playing":
            maximum = DIFFICULTIES[game["level"]]["maximum"]
            try:
                guess = int(request.form.get("guess", "").strip())
            except ValueError:
                guess = None
            guesser = game["guesser"] if game["mode"] == "pass" else player

            if guess is None:
                game["message"] = "Сканер принимает только целые числа"
                game["message_type"] = "error"
            elif not 1 <= guess <= maximum:
                game["message"] = f"Координата вне карты: 1—{maximum}"
                game["message_type"] = "error"
            elif guess in game["used_guesses"]:
                game["message"] = "Эта точка уже исследована"
                game["message_type"] = "warning"
            else:
                game["used_guesses"].append(guess)
                game["attempts_used"] += 1
                record_attempt(guesser)

                if guess == game["number"]:
                    game.update(status="won", phase="finished", score=calculate_score(game),
                                message=f"Ключ найден! {guesser} раскрывает тайну сектора", message_type="success")
                    game["history"].append({"guess": guess, "heat": "HIT", "direction": "тайна раскрыта"})
                    save_result(game, guesser, "won")
                    if game["mode"] == "pass":
                        with connect_db() as db:
                            db.execute("UPDATE players SET losses=losses+1, streak=0 WHERE name=?", (game["hider"],))
                else:
                    direction = "выше" if guess < game["number"] else "ниже"
                    heat = heat_label(game, guess)
                    game["history"].append({"guess": guess, "heat": heat, "direction": direction})
                    if game["attempts_used"] >= DIFFICULTIES[game["level"]]["attempts"]:
                        game.update(status="lost", phase="finished", score=20,
                                    message=f"Сектор закрыт. Ключ был: {game['number']}", message_type="error")
                        save_result(game, guesser, "lost")
                        if game["mode"] == "pass":
                            hider = game["hider"]
                            game["hider_score"] = 100
                            with connect_db() as db:
                                db.execute("""UPDATE players SET xp=xp+100, wins=wins+1,
                                    streak=streak+1, best_streak=MAX(best_streak, streak+1),
                                    hider_points=hider_points+100 WHERE name=?""", (hider,))
                    else:
                        game["message"] = f"След ведёт {direction} · {heat}"
                        game["message_type"] = "info"

        session.modified = True

    player = current_player()
    profile = get_profile(player)
    return render_template("index.html", game=game, difficulties=DIFFICULTIES,
        missions=MISSIONS, mission=MISSIONS[game["level"]], players=PLAYERS,
        player=player, profile=profile, leaderboard=get_leaderboard(),
        level=profile["xp"] // 500 + 1, level_progress=profile["xp"] % 500,
        seconds_left=seconds_left(game))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

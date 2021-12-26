import os
import json
from flask import (
    Flask,
    render_template,
    request,
    abort,
    redirect,
    url_for,
    send_from_directory,
)
from flask_login import (
    LoginManager,
    login_user,
    current_user,
    login_required,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy

op = os.path


app = Flask(__name__)
app.secret_key = "8288975bbb4b17b4b02cbb573bc0a77be37e995440c10ad908bb43624d6d0e62"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.sqlite3"
ROOT = op.dirname(__file__)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/login/"


def _mkdir(path):
    if not op.isdir(path):
        os.makedirs(path)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    user_id = db.Column(db.String(), unique=True, nullable=False)
    password = db.Column(db.String(), nullable=False)

    def is_active(self):
        return True

    def get_id(self):
        return self.user_id

    def is_authenticated(self):
        return True


class Cards(db.Model):
    __tablename__ = "cards"
    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    front = db.Column(db.String(), nullable=False)
    back = db.Column(db.String(), nullable=False)
    image = db.Column(db.String())
    tags = db.Column(db.String())


class Decks(db.Model):
    __tablename__ = "decks"
    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    name = db.Column(db.String(), nullable=False)
    user = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def get_cards(self):
        cards = []
        for card in DeckCard.query.filter_by(deck=self.id).all():
            cards.append(Cards.query.get(card.card))
        return cards


class DeckCard(db.Model):
    __tablename__ = "deckcard"
    id = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    deck = db.Column(db.Integer, db.ForeignKey("decks.id"), nullable=False)
    card = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.filter_by(user_id=user_id).first()


@app.route("/")
@login_required
def index():
    if current_user.is_authenticated():
        cards = Cards.query.filter_by(user=current_user.id)
        decks = Decks.query.filter_by(user=current_user.id)
        return render_template("index.html", cards=cards, decks=decks)
    return redirect(url_for("login"))


@app.route("/login/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        logout_user()
        return render_template("login.html")
    if request.method == "POST":
        user = request.form["user_id"]
        password = request.form["password"]
        user = User.query.filter_by(user_id=user).first()
        if not user:
            abort(404, f"User {user} not found.")
        if password != user.password:
            abort(403, "Incorrect password.")
        login_user(user)
        return redirect(url_for("index"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", existing_user=False)
    if request.method == "POST":
        user_id = user_id = request.form["user_id"]
        existing_user = User.query.filter_by(user_id=user_id).first()
        if existing_user is not None:
            return render_template("signup.html", existing_user=existing_user)
        user = User(user_id=user_id, password=request.form["password-1"])
        db.session.add(user)
        db.session.commit()
        return redirect("/login/")


@app.route("/logout/", methods=["GET"])
def logout():
    logout_user()
    return redirect("/login/")


@app.route("/upload/", defaults={"filename": ""}, methods=["POST", "GET"])
@app.route("/upload/<path:filename>")
@login_required
def upload(filename):
    path = op.join(ROOT, "static", "uploads", current_user.user_id)
    if request.method == "POST":
        _mkdir(path)
        _file = request.files["file"]
        target = op.join(path, _file.filename)
        _file.save(target)
        return op.relpath(target, ROOT), 201
    if request.method == "GET":
        return send_from_directory(path, filename)


@app.route("/card/", defaults={"card_id": ""}, methods=["GET", "POST"])
@app.route("/card/<string:card_id>")
@login_required
def card(card_id):
    if request.method == "GET":
        if card_id == "create":
            return render_template("create-card.html")
        card_data = Cards.query.filter_by(card_id=int(card_id))
        return render_template("card.html", card_data)
    if request.method == "POST":
        if card_id:
            abort(400, "card_id not allowed when POSTing a card.")
        card = Cards(
            user=current_user.id,
            front=request.form["cardfront"],
            back=request.form["cardback"],
            image=request.form["cardimg"],
        )
        db.session.add(card)
        db.session.commit()
        return redirect("/card/create")


@app.route("/deck/", defaults={"deck_id": ""}, methods=["POST", "GET"])
@app.route("/deck/<int:deck_id>")
@login_required
def deck(deck_id):
    if request.method == "GET":
        deck = Decks.query.get(deck_id)
        return render_template("deck.html", deck=deck)
    if request.method == "POST":
        deck = Decks(name=request.form["deckname"], user=current_user.id)
        db.session.add(deck)
        db.session.commit()

        # Add cards to deck
        for card in json.loads(request.form["cards"]):
            card_id = int(card.split("-")[-1])
            card = Cards.query.get(card_id)
            if card is None:
                abort(404, f"Card with id {card_id} not found.")
            deckcard = DeckCard(deck=deck.id, card=card.id)
            db.session.add(deckcard)
            db.session.commit()
        return redirect("/")


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)

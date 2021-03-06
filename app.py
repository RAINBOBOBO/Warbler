import os

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError

from forms import UserAddForm, LoginForm, MessageForm, UserUpdateForm
from models import db, connect_db, User, Message


CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
# app.config['SQLALCHEMY_DATABASE_URI'] = (
#     os.environ.get('DATABASE_URL', 'postgres:///warbler'))
app.config['SQLALCHEMY_DATABASE_URI'] = (os.environ.get(
    'DATABASE_URL', 'postgres://rainb:qwerty@localhost/warbler'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = True
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
# toolbar = DebugToolbarExtension(app)

connect_db(app)

DEFAULT_USER_IMG = '/static/images/default-pic.png'


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


# def check_logged_in():
#     """Check if the user is logged in."""
#     # Log out what request and g is. Log out what the request and g is in the route. 
#     print(f"checked logged in g: {g.user}")

#     if not g.user:
#          # not the g we expect. g in a function that is not a route. Pass in g into check_logged_in
#         print("We reached the flash!")
#         flash("Access unauthorized.", "danger")
#         return redirect("/")

# decorator function for checking to see if the user is logged in.
def check_logged_in(fn):
    def inner(*args, **kwargs):
        if not g.user:
            flash("Access unauthorized.", "danger")
            return redirect("/")
        return fn(*args, **kwargs)
    inner.__name__ = fn.__name__ # TODO Why does this fix our problem?
    return inner

@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            # db.session.commit() moved to User.signup()
            # TODO: is this ok?

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()
    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)

@app.route('/logout', methods=['POST'])
def logout():
    """Handle logout of user."""

    do_logout()
    flash('Successfully logged out')

    return redirect('/login')


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    return render_template('users/show.html', user=user)


@app.route('/users/<int:user_id>/following')
@check_logged_in
def show_following(user_id):
    """Show list of people this user is following."""

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)


@app.route('/users/<int:user_id>/followers')
@check_logged_in
def users_followers(user_id):
    """Show list of followers of this user."""

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
@check_logged_in
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
@check_logged_in
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/liked/<int:message_id>', methods=['POST'])
@check_logged_in
def like_message(message_id):
    """ Have currently-logged-in-user like the message."""

    liked_message = Message.query.get(message_id)
    g.user.liked_messages.append(liked_message)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/liked")


@app.route('/users/unlike/<int:message_id>', methods=['POST'])
@check_logged_in
def unlike_message(message_id):
    """Have currently logged in user unlike a message."""

    liked_message = Message.query.get(message_id)
    g.user.liked_messages.remove(liked_message)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/liked")


@app.route('/users/<int:user_id>/liked')
@check_logged_in
def show_liked(user_id):
    """Displays the liked warbles of the currently logged in user."""

    user = User.query.get_or_404(user_id)

    return render_template("users/liked.html", user=user)


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""

    if not g.user:
        flash('You must login!')
        return redirect('/login')

    form = UserUpdateForm(obj=g.user)
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        image_url = form.image_url.data or DEFAULT_USER_IMG
        header_image_url = form.header_image_url.data
        bio = form.bio.data
        password = form.password.data

        if User.authenticate(username, password) == g.user:
            g.user.username = username
            g.user.email = email
            g.user.image_url = image_url
            g.user.header_image_url = header_image_url
            g.user.bio = bio

            db.session.commit()

            return redirect(f'/users/{g.user.id}')
        else:
            flash("Username and/or password is invalid.")
            return redirect('/')
    else:
        return render_template("users/edit.html", form=form, user_id=g.user.id)


@app.route('/users/delete', methods=["POST"])
@check_logged_in
def delete_user():
    """Delete user."""

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:


@app.route('/messages/new', methods=["GET", "POST"])
@check_logged_in
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    # if not g.user:
    #     flash("Access unauthorized.", "danger")
    #     return redirect("/")

    # TODO: FIX THIS
    
    # research decorator
        

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template('messages/new.html', form=form)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    return render_template('messages/show.html', message=msg)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    msg = Message.query.get(message_id)

    if not g.user or g.user.id != msg.user_id:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")

##############################################################################
# Direct Messages

@app.route('/directmessages/new', methods=['GET', 'POST'])
@check_logged_in
def slide_dm():
    """Slide a direct message to another user."""

    form = DirectMessageForm()

    if form.validate_on_submit():
        recipient=form.recipient.data

        check_user = User.query.filter(User.username == recipient).first()
        if not check_user:
            flash("User doesn't exist!")
            return render_template("") #TODO: create this template

        new_dm = DirectMessage(
            text=form.text.data
            recipient=recipient
        )

        db.session.add(new_dm)
        db.session.commit()


##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """
    # breakpoint()
    if g.user:
        ids_in_following = [u.id for u in g.user.following] + [g.user.id]
        messages = (Message
                    .query
                    .filter(Message.user_id.in_(ids_in_following))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())

        return render_template('home.html', messages=messages)

    else:
        return render_template('home-anon.html')


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response

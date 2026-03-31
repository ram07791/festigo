from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
import os
from sqlalchemy import event

app = Flask(__name__)
app.secret_key = "secret123"

# =========================
# DATABASE CONFIG (SQLITE)
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'festigo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session security
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False

db = SQLAlchemy(app)

# =========================
# ENABLE FOREIGN KEYS SAFELY
# =========================
with app.app_context():
    @event.listens_for(db.engine, "connect")
    def enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# =========================
# MODELS
# =========================

class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(100), nullable=False, unique=True)
    user_password = db.Column(db.String(255), nullable=False)
    user_role = db.Column(db.String(20), default='user')


class Event(db.Model):
    __tablename__ = 'events'
    event_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_title = db.Column(db.String(250), nullable=False)
    event_description = db.Column(db.Text)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    event_seats = db.Column(db.Integer, nullable=False)
    event_price = db.Column(db.Integer, nullable=False)


class Booking(db.Model):
    __tablename__ = 'bookings'
    booking_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=False)
    total_tickets = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='confirmed')


class Registration(db.Model):
    __tablename__ = 'registrations'
    registration_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)
    event_ref_id = db.Column(db.Integer, db.ForeignKey('events.event_id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    seat_type = db.Column(db.String(50), nullable=False)


class Blog(db.Model):
    __tablename__ = 'blog'
    blog_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.event_id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    description = db.Column(db.Text)


# =========================
# CREATE DATABASE
# =========================
with app.app_context():
    db.create_all()


# =========================
# HOME
# =========================
@app.route('/')
def home():
    testimonials = [
        {"image": "images/naik.jpeg", "text": "Amazing experience!", "name": "Naik", "role": "Organizer"},
        {"image": "images/mall.jpeg", "text": "Smooth booking!", "name": "Mall", "role": "User"},
        {"image": "images/abhinav.jpeg", "text": "Best platform!", "name": "abhinav", "role": "Planner"}
    ]
    return render_template('index.html', testimonials=testimonials)


@app.route('/overview')
def overview():
    return render_template('overview.html')


# =========================
# AUTH
# =========================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(user_name=request.form['username']).first()
        if user and check_password_hash(user.user_password, request.form['password']):
            session['user_id'] = user.user_id
            session['role'] = user.user_role
            session['username'] = user.user_name
            flash("Login Successful")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid Credentials")
    return render_template('login.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']
        role = request.form['role']

        existing_user = User.query.filter(
            (User.user_name == username) | (User.user_email == email)
        ).first()

        if existing_user:
            flash("User already exists")
            return redirect(url_for('register'))

        if password != confirm:
            flash("Passwords do not match")
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)

        new_user = User(
            user_name=username,
            user_email=email,
            user_password=hashed,
            user_role=role
        )

        db.session.add(new_user)
        db.session.commit()
        flash("Registered Successfully")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect(url_for('login'))


# =========================
# DASHBOARD
# =========================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    events = Event.query.all()

    return render_template('dashboard.html',
        username=session.get('username'),
        role=session.get('role'),
        events=events
    )


@app.route('/my_events')
def my_events():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'organizer':
        return "Access Denied"

    events = Event.query.filter_by(created_by=session['user_id']).all()
    return render_template('my_events.html', events=events)


# =========================
# EVENTS
# =========================
@app.route('/schedule')
def schedule():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    events = Event.query.order_by(Event.event_date.asc()).all()
    return render_template('schedule.html', events=events, today=date.today())


@app.route('/add_event', methods=['GET','POST'])
def add_event():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'organizer':
        return "Unauthorized"

    if request.method == 'POST':
        event_obj = Event(
            event_title=request.form['title'],
            event_description=request.form['description'],
            event_date=datetime.strptime(request.form['date'], "%Y-%m-%dT%H:%M"),
            location=request.form['location'],
            event_seats=int(request.form['seats']),
            event_price=int(request.form['price']),
            created_by=session['user_id']
        )
        db.session.add(event_obj)
        db.session.commit()

        flash("Event Added Successfully")
        return redirect(url_for('schedule'))

    return render_template('add_event.html')


@app.route('/edit_event/<int:event_id>', methods=['GET','POST'])
def edit_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'organizer':
        return "Unauthorized"

    event_obj = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        event_obj.event_title = request.form['title']
        event_obj.event_description = request.form['description']
        event_obj.event_date = datetime.strptime(request.form['date'], "%Y-%m-%dT%H:%M")
        event_obj.location = request.form['location']
        event_obj.event_seats = int(request.form['seats'])
        event_obj.event_price = int(request.form['price'])

        db.session.commit()
        flash("Event updated successfully")
        return redirect(url_for('schedule'))

    return render_template('edit_event.html', event=event_obj)


@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('role') != 'organizer':
        return "Unauthorized"

    event_obj = Event.query.get_or_404(event_id)

    # ✅ Check ownership
    if event_obj.created_by != session['user_id']:
        return "You cannot delete this event"

    # ✅ Correct delete order
    Registration.query.filter_by(event_ref_id=event_id).delete()
    Booking.query.filter_by(event_id=event_id).delete()
    Blog.query.filter_by(event_id=event_id).delete()

    db.session.delete(event_obj)
    db.session.commit()

    flash("Event deleted successfully")
    return redirect(url_for('schedule'))


# =========================
# BOOKING
# =========================
@app.route('/book/<int:event_id>', methods=['GET','POST'])
def book_event(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    event_obj = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        total_tickets = int(request.form.get('ticket_count'))

        booking = Booking(
            user_id=session['user_id'],
            event_id=event_id,
            total_tickets=total_tickets
        )

        db.session.add(booking)
        db.session.flush()

        registrations = []

        for i in range(1, total_tickets + 1):
            seat_type = request.form.get(f"seat_{i}")

            reg = Registration(
                booking_id=booking.booking_id,
                event_ref_id=event_id,
                participant_id=session['user_id'],
                seat_type=seat_type
            )

            db.session.add(reg)
            db.session.flush()
            registrations.append(reg)

        db.session.commit()

        return redirect(url_for('ticket', registration_id=registrations[0].registration_id))

    return render_template('book.html', event=event_obj)


@app.route("/ticket/<int:registration_id>")
def ticket(registration_id):
    registration = Registration.query.get_or_404(registration_id)
    event_obj = Event.query.get_or_404(registration.event_ref_id)
    user = User.query.get(registration.participant_id)
    booking = Booking.query.get_or_404(registration.booking_id)

    return render_template("ticket.html",
        event=event_obj,
        registration=registration,
        user=user,
        booking=booking
    )


# =========================
# BLOG / REVIEWS
# =========================
@app.route('/blog')
def blog():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    blogs = Blog.query.order_by(Blog.blog_id.desc()).all()
    events = Event.query.all()
    event_map = {e.event_id: e.event_title for e in events}

    return render_template('blog.html', blogs=blogs, event=None, event_map=event_map)


@app.route('/reviews/<int:event_id>')
def view_reviews(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    event_obj = Event.query.get_or_404(event_id)
    blogs = Blog.query.filter_by(event_id=event_id).all()

    events = Event.query.all()
    event_map = {e.event_id: e.event_title for e in events}

    return render_template('blog.html', blogs=blogs, event=event_obj, event_map=event_map)


@app.route('/add_review/<int:event_id>', methods=['GET','POST'])
def add_review(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    event_obj = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        new_review = Blog(
            event_id=event_id,
            user_id=session['user_id'],
            description=request.form['review']
        )
        db.session.add(new_review)
        db.session.commit()

        flash("Review added successfully")
        return redirect(url_for('view_reviews', event_id=event_id))

    return render_template('add_review.html', event=event_obj)


@app.route('/add_review', methods=['GET','POST'])
def add_review_global():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    events = Event.query.all()

    if request.method == 'POST':
        new_review = Blog(
            event_id=int(request.form['event_id']),
            user_id=session['user_id'],
            description=request.form['review']
        )
        db.session.add(new_review)
        db.session.commit()

        flash("Review added successfully")
        return redirect(url_for('blog'))

    return render_template('add_review_global.html', events=events)


@app.route('/edit_review/<int:blog_id>', methods=['GET','POST'])
def edit_review(blog_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    blog_obj = Blog.query.get_or_404(blog_id)
    next_page = request.args.get('next')

    if request.method == 'POST':
        blog_obj.description = request.form['review']
        db.session.commit()

        flash("Review updated successfully")
        return redirect(next_page or url_for('blog'))

    return render_template('edit_review.html', blog=blog_obj)


@app.route('/delete_review/<int:blog_id>')
def delete_review(blog_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    blog_obj = Blog.query.get_or_404(blog_id)
    db.session.delete(blog_obj)
    db.session.commit()

    flash("Review deleted successfully")
    return redirect(url_for('blog'))


# =========================
# RUN
# =========================
if __name__ == '__main__':
    app.run()
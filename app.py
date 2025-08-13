
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, Email, Optional, Length
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///students.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False, index=True)
    last_name = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    birthdate = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)


class Speciality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

class StudentForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)], render_kw={"type": "tel"})
    birthdate = DateField("Birthdate (YYYY-MM-DD)", validators=[Optional()], format="%Y-%m-%d")
    submit = SubmitField("Save")


class ClassForm(FlaskForm):
    name = StringField("Class name", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Save")


class SpecialityForm(FlaskForm):
    name = StringField("Speciality name", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Save")

@app.route("/", methods=["GET"])
def index():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Student.first_name.ilike(like),
                Student.last_name.ilike(like),
                Student.email.ilike(like),
                Student.phone.ilike(like),
            )
        )
    students = query.order_by(Student.created_at.desc()).paginate(page=page, per_page=10)
    return render_template("index.html", students=students, q=q)

@app.route("/students/new", methods=["GET", "POST"])
def create_student():
    form = StudentForm()
    if form.validate_on_submit():
        s = Student(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data or None,
            birthdate=form.birthdate.data or None,
        )
        db.session.add(s)
        try:
            db.session.commit()
            flash("Student created successfully.", "success")
            return redirect(url_for("index"))
        except Exception:
            db.session.rollback()
            flash("Email must be unique or data invalid.", "danger")
    return render_template("form.html", form=form, title="Add student")

@app.route("/students/<int:student_id>", methods=["GET"])
def show_student(student_id):
    s = Student.query.get_or_404(student_id)
    return render_template("show.html", s=s)

@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    s = Student.query.get_or_404(student_id)
    form = StudentForm(obj=s)
    if form.validate_on_submit():
        s.first_name = form.first_name.data
        s.last_name = form.last_name.data
        s.email = form.email.data
        s.phone = form.phone.data or None
        s.birthdate = form.birthdate.data or None
        try:
            db.session.commit()
            flash("Student updated.", "success")
            return redirect(url_for("show_student", student_id=s.id))
        except Exception:
            db.session.rollback()
            flash("Update failed (email must be unique?).", "danger")
    return render_template("form.html", form=form, title="Edit student")

@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    s = Student.query.get_or_404(student_id)
    db.session.delete(s)
    db.session.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("index"))


@app.route("/classes/new", methods=["GET", "POST"])
def create_class():
    form = ClassForm()
    classes = Class.query.order_by(Class.name).all()
    if form.validate_on_submit():
        c = Class(name=form.name.data)
        db.session.add(c)
        try:
            db.session.commit()
            flash("Class created successfully.", "success")
            return redirect(url_for("create_class"))
        except Exception:
            db.session.rollback()
            flash("Class name must be unique.", "danger")
    return render_template(
        "single_field_form.html",
        form=form,
        title="Add class",
        existing=classes,
        list_title="Existing classes",
    )


@app.route("/specialities/new", methods=["GET", "POST"])
def create_speciality():
    form = SpecialityForm()
    specialities = Speciality.query.order_by(Speciality.name).all()
    if form.validate_on_submit():
        s = Speciality(name=form.name.data)
        db.session.add(s)
        try:
            db.session.commit()
            flash("Speciality created successfully.", "success")
            return redirect(url_for("create_speciality"))
        except Exception:
            db.session.rollback()
            flash("Speciality name must be unique.", "danger")
    return render_template(
        "single_field_form.html",
        form=form,
        title="Add speciality",
        existing=specialities,
        list_title="Existing specialities",
    )

@app.route("/__health")
def health():
    return {
        "status": "ok",
        "students": Student.query.count(),
        "classes": Class.query.count(),
        "specialities": Speciality.query.count(),
    }

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

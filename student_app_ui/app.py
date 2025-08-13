
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField, SelectField
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
    class_name = db.Column(db.String(80), nullable=False)
    specialty_name = db.Column(db.String(80), nullable=False)


class ClassSpecialty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(80), nullable=False, index=True)
    specialty_name = db.Column(db.String(80), nullable=False, index=True)
    __table_args__ = (
        db.UniqueConstraint("class_name", "specialty_name", name="uix_class_specialty"),
    )

class StudentForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    birthdate = DateField("Birthdate (YYYY-MM-DD)", validators=[Optional()], format="%Y-%m-%d")
    class_name = SelectField("Class", validators=[DataRequired()], choices=[])
    specialty_name = SelectField("Specialty", validators=[DataRequired()], choices=[])
    submit = SubmitField("Save")


class ClassSpecialtyForm(FlaskForm):
    class_name = StringField("Class", validators=[DataRequired(), Length(max=80)])
    specialty_name = StringField("Specialty", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Save")


@app.route("/classes/new", methods=["GET", "POST"])
def create_class_specialty():
    form = ClassSpecialtyForm()
    if form.validate_on_submit():
        cs = ClassSpecialty(
            class_name=form.class_name.data,
            specialty_name=form.specialty_name.data,
        )
        db.session.add(cs)
        try:
            db.session.commit()
            flash("Class and specialty created.", "success")
            return redirect(url_for("index"))
        except Exception:
            db.session.rollback()
            flash("Could not save class/specialty (duplicate?).", "danger")
    return render_template("class_form.html", form=form, title="Add class/specialty")


@app.route("/classes/<class_name>/specialties", methods=["GET"])
def get_specialties(class_name):
    specs = ClassSpecialty.query.filter_by(class_name=class_name).all()
    return {"specialties": [c.specialty_name for c in specs]}

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
                Student.class_name.ilike(like),
                Student.specialty_name.ilike(like),
            )
        )
    students = query.order_by(Student.created_at.desc()).paginate(page=page, per_page=10)
    return render_template("index.html", students=students, q=q)

@app.route("/students/new", methods=["GET", "POST"])
def create_student():
    form = StudentForm()
    classes = sorted({cs.class_name for cs in ClassSpecialty.query.all()})
    form.class_name.choices = [(c, c) for c in classes]
    selected_class = form.class_name.data or (classes[0] if classes else None)
    specialties = (
        [cs.specialty_name for cs in ClassSpecialty.query.filter_by(class_name=selected_class)]
        if selected_class
        else []
    )
    form.specialty_name.choices = [(s, s) for s in specialties]
    if form.validate_on_submit():
        s = Student(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data or None,
            birthdate=form.birthdate.data or None,
            class_name=form.class_name.data,
            specialty_name=form.specialty_name.data,
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
    classes = sorted({cs.class_name for cs in ClassSpecialty.query.all()})
    form.class_name.choices = [(c, c) for c in classes]
    selected_class = form.class_name.data or (classes[0] if classes else None)
    specialties = (
        [cs.specialty_name for cs in ClassSpecialty.query.filter_by(class_name=selected_class)]
        if selected_class
        else []
    )
    form.specialty_name.choices = [(sp, sp) for sp in specialties]
    if form.validate_on_submit():
        s.first_name = form.first_name.data
        s.last_name = form.last_name.data
        s.email = form.email.data
        s.phone = form.phone.data or None
        s.birthdate = form.birthdate.data or None
        s.class_name = form.class_name.data
        s.specialty_name = form.specialty_name.data
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

@app.route("/__health")
def health():
    return {"status": "ok", "students": Student.query.count()}

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

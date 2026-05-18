from datetime import date, datetime
import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy import CheckConstraint, UniqueConstraint
from wtforms import DateField, FloatField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, NumberRange, Optional

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///leave_app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role = db.Column(db.String(40), nullable=False, default="EMPLOYEE")
    leave_balance = db.Column(db.Float, nullable=False, default=0)
    leave_reserved = db.Column(db.Float, nullable=False, default=0)
    recovery_balance = db.Column(db.Float, nullable=False, default=0)
    recovery_reserved = db.Column(db.Float, nullable=False, default=0)

    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    functional_manager_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    hierarchical_manager_id = db.Column(db.Integer, db.ForeignKey("employee.id"))

    team = db.relationship("Team", backref="employees")

    __table_args__ = (
        CheckConstraint("leave_balance >= 0"),
        CheckConstraint("leave_reserved >= 0"),
        CheckConstraint("recovery_balance >= 0"),
        CheckConstraint("recovery_reserved >= 0"),
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    request_type = db.Column(db.String(20), nullable=False)  # LEAVE / RECOVERY / AUTH
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="PENDING_FUNCTIONAL")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now())

    functional_decision = db.Column(db.String(20), default="PENDING")
    hierarchical_decision = db.Column(db.String(20), default="PENDING")
    hr_decision = db.Column(db.String(20), default="PENDING")

    employee = db.relationship("Employee", backref="requests")

    __table_args__ = (
        CheckConstraint("quantity > 0"),
        CheckConstraint("start_date <= end_date"),
    )


class EmployeeForm(FlaskForm):
    first_name = StringField("Prénom", validators=[DataRequired()])
    last_name = StringField("Nom", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    role = SelectField(
        "Rôle",
        choices=[
            ("EMPLOYEE", "Employé"),
            ("MANAGER_FUNCTIONAL", "Manager fonctionnel"),
            ("MANAGER_HIERARCHICAL", "Manager hiérarchique"),
            ("HR", "RH"),
        ],
        validators=[DataRequired()],
    )
    team_id = SelectField("Équipe", coerce=int, validators=[Optional()])
    functional_manager_id = SelectField("Manager fonctionnel", coerce=int, validators=[Optional()])
    hierarchical_manager_id = SelectField("Manager hiérarchique", coerce=int, validators=[Optional()])
    leave_balance = FloatField("Solde congé", validators=[DataRequired(), NumberRange(min=0)])
    recovery_balance = FloatField("Solde récupération", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Enregistrer")


class LeaveRequestForm(FlaskForm):
    employee_id = SelectField("Employé", coerce=int, validators=[DataRequired()])
    request_type = SelectField(
        "Type",
        choices=[("LEAVE", "Congé"), ("RECOVERY", "Récupération"), ("AUTH", "Autorisation")],
        validators=[DataRequired()],
    )
    start_date = DateField("Date début", validators=[DataRequired()], format="%Y-%m-%d")
    end_date = DateField("Date fin", validators=[DataRequired()], format="%Y-%m-%d")
    quantity = FloatField("Quantité (jours/heures)", validators=[DataRequired(), NumberRange(min=0.5)])
    reason = TextAreaField("Motif", validators=[Optional()])
    submit = SubmitField("Soumettre")


def _seed_if_empty():
    if Employee.query.count() > 0:
        return
    t1 = Team(name="IT")
    t2 = Team(name="RH")
    db.session.add_all([t1, t2])
    db.session.flush()

    hr = Employee(first_name="Sami", last_name="Rahmani", email="sami@company.com", role="HR", team=t2, leave_balance=30, recovery_balance=15)
    mf = Employee(first_name="Nadia", last_name="Benali", email="nadia@company.com", role="MANAGER_FUNCTIONAL", team=t1, leave_balance=25, recovery_balance=10)
    mh = Employee(first_name="Karim", last_name="Haddad", email="karim@company.com", role="MANAGER_HIERARCHICAL", team=t1, leave_balance=25, recovery_balance=10)
    emp = Employee(
        first_name="Yassine",
        last_name="Mansouri",
        email="yassine@company.com",
        role="EMPLOYEE",
        team=t1,
        leave_balance=20,
        recovery_balance=8,
        functional_manager_id=2,
        hierarchical_manager_id=3,
    )
    db.session.add_all([hr, mf, mh, emp])
    db.session.commit()


def reserve_balance(employee: Employee, request_type: str, qty: float):
    if request_type == "AUTH":
        return True, ""
    if request_type == "LEAVE":
        available = employee.leave_balance - employee.leave_reserved
        if available < qty:
            return False, f"Solde congé insuffisant ({available:.1f} disponible)."
        employee.leave_reserved += qty
    elif request_type == "RECOVERY":
        available = employee.recovery_balance - employee.recovery_reserved
        if available < qty:
            return False, f"Solde récupération insuffisant ({available:.1f} disponible)."
        employee.recovery_reserved += qty
    return True, ""


def release_or_consume(request_obj: LeaveRequest, action: str):
    employee = request_obj.employee
    qty = request_obj.quantity
    if request_obj.request_type == "AUTH":
        return
    if request_obj.request_type == "LEAVE":
        if action == "release":
            employee.leave_reserved = max(0, employee.leave_reserved - qty)
        else:
            employee.leave_reserved = max(0, employee.leave_reserved - qty)
            employee.leave_balance = max(0, employee.leave_balance - qty)
    if request_obj.request_type == "RECOVERY":
        if action == "release":
            employee.recovery_reserved = max(0, employee.recovery_reserved - qty)
        else:
            employee.recovery_reserved = max(0, employee.recovery_reserved - qty)
            employee.recovery_balance = max(0, employee.recovery_balance - qty)


@app.route("/")
def index():
    return render_template("dashboard.html", employees=Employee.query.all(), requests=LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all())


@app.route("/employees/new", methods=["GET", "POST"])
def create_employee():
    form = EmployeeForm()
    teams = Team.query.order_by(Team.name).all()
    employees = Employee.query.order_by(Employee.first_name).all()
    form.team_id.choices = [(0, "--")]+[(t.id, t.name) for t in teams]
    form.functional_manager_id.choices = [(0, "--")]+[(e.id, e.full_name) for e in employees]
    form.hierarchical_manager_id.choices = [(0, "--")]+[(e.id, e.full_name) for e in employees]

    if form.validate_on_submit():
        e = Employee(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            role=form.role.data,
            team_id=form.team_id.data or None,
            functional_manager_id=form.functional_manager_id.data or None,
            hierarchical_manager_id=form.hierarchical_manager_id.data or None,
            leave_balance=form.leave_balance.data,
            recovery_balance=form.recovery_balance.data,
        )
        db.session.add(e)
        db.session.commit()
        flash("Employé créé.", "success")
        return redirect(url_for("index"))
    return render_template("employee_form.html", form=form)


@app.route("/requests/new", methods=["GET", "POST"])
def create_request():
    form = LeaveRequestForm()
    employees = Employee.query.order_by(Employee.first_name).all()
    form.employee_id.choices = [(e.id, e.full_name) for e in employees]

    if form.validate_on_submit():
        employee = Employee.query.get_or_404(form.employee_id.data)
        ok, message = reserve_balance(employee, form.request_type.data, form.quantity.data)
        if not ok:
            flash(message, "danger")
            return render_template("request_form.html", form=form)

        request_obj = LeaveRequest(
            employee_id=employee.id,
            request_type=form.request_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            quantity=form.quantity.data,
            reason=form.reason.data,
            status="PENDING_FUNCTIONAL",
        )
        db.session.add(request_obj)
        db.session.commit()
        flash("Demande soumise, solde réservé.", "success")
        return redirect(url_for("index"))
    return render_template("request_form.html", form=form)


@app.route("/requests/<int:request_id>/<string:stage>/<string:decision>", methods=["POST"])
def review_request(request_id: int, stage: str, decision: str):
    request_obj = LeaveRequest.query.get_or_404(request_id)
    if request_obj.status in {"REJECTED", "APPROVED"}:
        flash("Cette demande est déjà finalisée.", "warning")
        return redirect(url_for("index"))

    if decision not in {"approve", "reject"}:
        flash("Action invalide.", "danger")
        return redirect(url_for("index"))

    if stage == "functional" and request_obj.status == "PENDING_FUNCTIONAL":
        request_obj.functional_decision = "APPROVED" if decision == "approve" else "REJECTED"
        if decision == "approve":
            request_obj.status = "PENDING_HIERARCHICAL"
        else:
            request_obj.status = "REJECTED"
            release_or_consume(request_obj, "release")
    elif stage == "hierarchical" and request_obj.status == "PENDING_HIERARCHICAL":
        request_obj.hierarchical_decision = "APPROVED" if decision == "approve" else "REJECTED"
        if decision == "approve":
            release_or_consume(request_obj, "consume")
            request_obj.status = "PENDING_HR"
        else:
            request_obj.status = "REJECTED"
            release_or_consume(request_obj, "release")
    elif stage == "hr" and request_obj.status == "PENDING_HR":
        request_obj.hr_decision = "APPROVED" if decision == "approve" else "REJECTED"
        request_obj.status = "APPROVED" if decision == "approve" else "REJECTED"
        if decision == "reject":
            flash("RH a rejeté après consommation: prévoir régularisation manuelle si nécessaire.", "warning")
    else:
        flash("Étape non valide pour cette demande.", "danger")
        return redirect(url_for("index"))

    db.session.commit()
    flash("Demande mise à jour.", "success")
    return redirect(url_for("index"))


@app.route("/__health")
def health():
    return {"status": "ok", "employees": Employee.query.count(), "requests": LeaveRequest.query.count()}


with app.app_context():
    db.create_all()
    _seed_if_empty()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

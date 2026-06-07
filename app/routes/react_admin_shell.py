from flask import Blueprint, redirect, render_template

from app.routes.main import _get_initial_data

bp = Blueprint("react_admin_shell", __name__)


@bp.route("/admin")
def admin_root_redirect():
    return redirect("/admin/dashboard")


@bp.route("/admin/dashboard")
@bp.route("/admin/dashboard/<path:subpath>")
def admin_dashboard_spa(subpath=None):
    return render_template("spa.html", initial_data=_get_initial_data())

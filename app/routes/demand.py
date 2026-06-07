from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app.authz import role_required
from app.models import Inquiry, Product
from app import db

demand = Blueprint("demand", __name__)


@demand.route("/list")
def list_demands():
    demand_type = request.args.get("type", "")
    product_name = request.args.get("product", "")
    query = Inquiry.query.filter(Inquiry.status.in_(("open", "active")))
    if demand_type:
        query = query.filter_by(direction=demand_type)
    if product_name:
        query = query.join(Product).filter(Product.name.contains(product_name))
    demands = query.order_by(Inquiry.created_at.desc()).all()

    if request.args.get("_format") == "json":
        from flask import jsonify

        return jsonify(
            [
                {
                    "id": d.id,
                    "type": d.direction,
                    "product_name": d.product.name if d.product else (d.product_name or ""),
                    "enterprise_name": d.poster.name if d.poster else "",
                    "quantity": d.quantity,
                    "unit": d.unit or "",
                    "status": d.status,
                }
                for d in demands
            ]
        )

    from app.routes.main import _render_spa

    return _render_spa()


@demand.route("/create", methods=["GET", "POST"])
@role_required("enterprise")
def create():
    if request.method == "POST":
        demand_type = request.form.get("type")
        product_name = request.form.get("product_name")
        quantity = request.form.get("quantity")
        unit = request.form.get("unit")
        description = request.form.get("description")

        if not all([demand_type, product_name]):
            flash("请填写必填项", "danger")
            products = current_user.products.all()
            return render_template("demand/create.html", products=products)

        product = Product.query.filter_by(
            name=product_name, enterprise_id=current_user.id
        ).first()
        if not product:
            product = Product(name=product_name, enterprise_id=current_user.id)
            db.session.add(product)
            db.session.flush()

        inquiry = Inquiry(
            direction=demand_type,
            product_id=product.id,
            product_name=product_name,
            quantity=int(quantity) if quantity else None,
            unit=unit,
            description=description,
            poster_id=current_user.id,
            status="open",
        )
        db.session.add(inquiry)
        db.session.commit()

        flash("发布成功", "success")
        return redirect(url_for("demand.list_demands"))

    products = current_user.products.all()
    return render_template("demand/create.html", products=products)


@demand.route("/my")
@role_required("enterprise")
def my_demands():
    demands = (
        Inquiry.query.filter_by(poster_id=current_user.id)
        .order_by(Inquiry.created_at.desc())
        .all()
    )
    return render_template("demand/my_demands.html", demands=demands)


@demand.route("/<int:demand_id>/delete", methods=["POST"])
@role_required("enterprise")
def delete(demand_id):
    demand_obj = Inquiry.query.get_or_404(demand_id)
    if demand_obj.poster_id != current_user.id:
        flash("无权限操作", "danger")
        return redirect(url_for("demand.my_demands"))

    db.session.delete(demand_obj)
    db.session.commit()
    flash("已删除", "success")
    return redirect(url_for("demand.my_demands"))


@demand.route("/<int:demand_id>/close", methods=["POST"])
@role_required("enterprise")
def close(demand_id):
    demand_obj = Inquiry.query.get_or_404(demand_id)
    if demand_obj.poster_id != current_user.id:
        flash("无权限操作", "danger")
        return redirect(url_for("demand.my_demands"))

    demand_obj.status = "closed"
    db.session.commit()
    flash("已关闭", "success")
    return redirect(url_for("demand.my_demands"))

"""Produits d'investissement, investissements et régularisations quotidiennes."""
from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class InvestmentProduct(TimestampMixin, db.Model):
    __tablename__ = "investment_products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration_days = db.Column(db.Integer, default=120, nullable=False)
    min_amount = db.Column(db.BigInteger, nullable=False)
    max_amount = db.Column(db.BigInteger, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    terms = db.Column(db.Text, nullable=True)
    fees_bps = db.Column(db.Integer, default=0, nullable=False)
    risk_policy = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="draft", nullable=False)  # draft/approved/paused/closed
    launch_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    income_method = db.Column(db.String(40), default="daily", nullable=False)
    annual_rate_bps = db.Column(db.Integer, default=0, nullable=False)  # taux approuvé uniquement
    exit_terms = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<InvestmentProduct {self.name} {self.status}>"


class Investment(TimestampMixin, db.Model):
    __tablename__ = "investments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("investment_products.id"), nullable=False)
    capital = db.Column(db.BigInteger, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)  # active/completed/cancelled/interrupted
    capital_repaid = db.Column(db.BigInteger, default=0, nullable=False)
    confirmed_income = db.Column(db.BigInteger, default=0, nullable=False)

    product = db.relationship("InvestmentProduct", backref="investments")

    def __repr__(self) -> str:
        return f"<Investment {self.id} {self.capital} {self.status}>"


class InvestmentAccrual(TimestampMixin, db.Model):
    __tablename__ = "investment_accruals"

    id = db.Column(db.Integer, primary_key=True)
    investment_id = db.Column(db.Integer, db.ForeignKey("investments.id"), nullable=False, index=True)
    accrual_date = db.Column(db.Date, nullable=False)
    estimated_amount = db.Column(db.BigInteger, default=0, nullable=False)
    accrued_amount = db.Column(db.BigInteger, default=0, nullable=False)
    confirmed_amount = db.Column(db.BigInteger, default=0, nullable=False)
    paid_amount = db.Column(db.BigInteger, default=0, nullable=False)
    status = db.Column(db.String(20), default="estimated", nullable=False)
    __table_args__ = (
        db.UniqueConstraint("investment_id", "accrual_date", name="uq_accrual_investment_date"),
    )

    def __repr__(self) -> str:
        return f"<InvestmentAccrual {self.investment_id} {self.accrual_date}>"

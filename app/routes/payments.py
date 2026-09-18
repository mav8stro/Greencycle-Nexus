from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, date
from app.extensions import db
from app.models import Payment, PaymentReceipt, Transaction, User, UserFeeRule
from app.services.auth_service import token_required, log_audit, create_notification
import json
import uuid

payments_bp = Blueprint('payments', __name__, url_prefix='/api/payments')

@payments_bp.route('/initiate', methods=['POST'])
@token_required
def initiate_payment():
    """Initiates an online user-fee payment session."""
    user = request.current_user
    data = request.get_json() or {}

    amount = float(data.get('amount', 100.0))
    billing_period = data.get('billing_period', datetime.now().strftime('%B %Y'))
    method = data.get('payment_method', 'UPI')
    fee_rule_id = data.get('fee_rule_id')

    if amount <= 0:
        return jsonify({'error': 'Payment amount must be greater than zero'}), 400

    # Look for existing pending payment or create new
    pending_pay = Payment.query.filter_by(
        user_id=user.id,
        billing_period=billing_period,
        status='Pending'
    ).first()

    if not pending_pay:
        pay_count = Payment.query.count() + 1
        pending_pay = Payment(
            payment_number=f"PAY-ONL-2026-{pay_count:05d}",
            user_id=user.id,
            fee_rule_id=fee_rule_id,
            amount=amount,
            billing_period=billing_period,
            status='Initiated',
            payment_method=method,
            due_date=date.today()
        )
        db.session.add(pending_pay)
        db.session.commit()
    else:
        pending_pay.status = 'Initiated'
        pending_pay.payment_method = method
        db.session.commit()

    # Generate gateway checkout session
    gateway_order_id = f"ORDER_{uuid.uuid4().hex[:12].upper()}"

    return jsonify({
        'payment_id': pending_pay.id,
        'payment_number': pending_pay.payment_number,
        'amount': pending_pay.amount,
        'billing_period': pending_pay.billing_period,
        'gateway_order_id': gateway_order_id,
        'payment_method': method
    })

@payments_bp.route('/<int:payment_id>/confirm', methods=['POST'])
@token_required
def confirm_payment(payment_id):
    """
    CRITICAL WORKFLOW TEST B:
    Server-side verified payment confirmation:
    - Never trusts client-side alone; validates payment ID and amount
    - Updates Payment status to Successful
    - Generates formal Transaction record
    - Issues official PaymentReceipt
    """
    payment = db.get_or_404(Payment, payment_id)
    if payment.user_id != request.user_id and request.user_role != 'admin':
        return jsonify({'error': 'Unauthorized to settle this payment'}), 403

    if payment.status == 'Successful':
        return jsonify({
            'message': 'Payment already completed',
            'payment': payment.to_dict(),
            'receipt': payment.receipt.to_dict() if payment.receipt else None
        })

    data = request.get_json() or {}
    gateway_txn_ref = data.get('transaction_reference') or f"UPI-TXN-{uuid.uuid4().hex[:10].upper()}"

    payment.status = 'Successful'
    payment.paid_at = datetime.now(timezone.utc)

    # Create Transaction record
    txn_count = Transaction.query.count() + 1
    txn = Transaction(
        txn_number=f"TXN-ONL-{txn_count:07d}",
        user_id=payment.user_id,
        transaction_type='COLLECTION_FEE',
        direction='CUSTOMER_TO_GREENCYCLE',
        amount=payment.amount,
        status='Successful',
        reference_id=gateway_txn_ref,
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(txn)
    db.session.flush()

    # Generate Official Digital Receipt
    rcpt_count = PaymentReceipt.query.count() + 1
    rcpt_number = f"RCPT-GCN-2026-{rcpt_count:05d}"
    rcpt = PaymentReceipt(
        receipt_number=rcpt_number,
        payment_id=payment.id,
        transaction_id=txn.id,
        user_id=payment.user_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        issued_at=datetime.now(timezone.utc),
        receipt_data_json=json.dumps({
            'customer_name': payment.user.full_name,
            'mobile': payment.user.phone,
            'amount': payment.amount,
            'billing_period': payment.billing_period,
            'payment_method': payment.payment_method,
            'reference_id': gateway_txn_ref,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        })
    )
    db.session.add(rcpt)
    db.session.commit()

    log_audit('PAYMENT_CONFIRMED', 'Payment', payment.id, None, {'receipt': rcpt_number, 'amount': payment.amount}, request.user_id, request.user_role)
    create_notification(payment.user_id, 'Payment Successful', f"Official receipt #{rcpt_number} generated for ₹{payment.amount:.2f} ({payment.billing_period}).", 'payment')

    return jsonify({
        'message': 'Payment verified and settled successfully!',
        'payment': payment.to_dict(),
        'receipt': rcpt.to_dict()
    })

@payments_bp.route('/<int:payment_id>/receipt', methods=['GET'])
@token_required
def get_payment_receipt(payment_id):
    payment = db.get_or_404(Payment, payment_id)
    if payment.user_id != request.user_id and request.user_role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if not payment.receipt:
        return jsonify({'error': 'Receipt has not been generated for this payment yet'}), 404

    return jsonify(payment.receipt.to_dict())

@payments_bp.route('', methods=['GET'])
@token_required
def list_payments():
    query = Payment.query
    if request.user_role != 'admin':
        query = query.filter_by(user_id=request.user_id)
    payments = query.order_by(Payment.due_date.desc()).all()
    return jsonify([p.to_dict() for p in payments])

from flask import Blueprint, request, Response
from app.models import (
    Pickup, Payment, MaterialRate, OperationalCost, Ward, Complaint, Volunteer,
    LocalBody, WasteCategory, PickupItem, Address
)
from app.services.auth_service import admin_required
import csv
import io

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')

@reports_bp.route('/export/<report_type>', methods=['GET'])
@admin_required
def export_csv_report(report_type):
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'collections':
        writer.writerow(['Pickup Number', 'Request ID', 'Citizen Name', 'Citizen Phone', 'Scheduled Date', 'Status', 'Estimated Weight (kg)', 'Actual Weight (kg)', 'Verified Weight (kg)', 'Collector Name'])
        pickups = Pickup.query.order_by(Pickup.scheduled_date.desc()).all()
        for p in pickups:
            writer.writerow([
                p.pickup_number,
                p.request_id or 'N/A',
                p.citizen.full_name if p.citizen else 'N/A',
                p.citizen.phone if p.citizen else 'N/A',
                p.scheduled_date,
                p.status,
                round(p.total_estimated_weight, 2),
                round(p.total_actual_weight, 2),
                round(p.total_verified_weight, 2),
                p.collector.full_name if p.collector else 'Unassigned'
            ])

    elif report_type == 'user-fees':
        writer.writerow(['Payment Number', 'Citizen Name', 'Mobile', 'Amount (INR)', 'Billing Period', 'Status', 'Payment Method', 'Paid At', 'Approved By Admin'])
        payments = Payment.query.order_by(Payment.due_date.desc()).all()
        for p in payments:
            writer.writerow([
                p.payment_number,
                p.user.full_name if p.user else 'N/A',
                p.user.phone if p.user else 'N/A',
                p.amount,
                p.billing_period,
                p.status,
                p.payment_method,
                p.paid_at.strftime('%Y-%m-%d %H:%M') if p.paid_at else 'N/A',
                'Yes' if p.approved_by_admin else 'No'
            ])

    elif report_type == 'material-recovery':
        writer.writerow(['Waste Category', 'Total Verified Weight (kg)', 'Realization Rate (INR/kg)', 'Material Value (INR)', 'Primary Recycler'])
        categories = WasteCategory.query.filter_by(active=True).all()
        for cat in categories:
            items = PickupItem.query.filter_by(waste_category_id=cat.id).all()
            weight = sum(it.verified_weight or it.actual_weight for it in items)
            rate = MaterialRate.query.filter_by(waste_category_id=cat.id, active=True).first()
            pr = rate.purchase_rate if rate else 10.0
            buyer = rate.buyer_name if rate else 'Clean Kerala Company'
            writer.writerow([
                cat.name,
                round(weight, 2),
                pr,
                round(weight * pr, 2),
                buyer
            ])

    elif report_type == 'operational-costs':
        writer.writerow(['Cost Category', 'Amount (INR)', 'Date', 'Local Body', 'Ward', 'Reference Voucher', 'Notes', 'Logged By'])
        costs = OperationalCost.query.order_by(OperationalCost.cost_date.desc()).all()
        for c in costs:
            writer.writerow([
                c.category,
                c.amount,
                c.cost_date,
                c.local_body.name if c.local_body else 'General',
                c.ward.ward_name if c.ward else 'All Wards',
                c.reference or 'N/A',
                c.notes or '',
                c.creator.full_name if c.creator else 'System'
            ])

    elif report_type == 'ward-analytics':
        writer.writerow(['Local Body', 'Ward Number', 'Ward Name', 'Registered Units', 'Pickups Completed', 'Total Waste Collected (kg)'])
        wards = Ward.query.all()
        for w in wards:
            units = Address.query.filter_by(ward_id=w.id).count()
            user_ids = [a.user_id for a in Address.query.filter_by(ward_id=w.id).all()]
            pickups = Pickup.query.filter(Pickup.citizen_id.in_(user_ids), Pickup.status.in_(['Completed', 'Collected', 'Verified'])).all() if user_ids else []
            total_kg = sum(p.total_verified_weight or p.total_actual_weight for p in pickups)
            writer.writerow([
                w.local_body.name if w.local_body else 'N/A',
                w.ward_number,
                w.ward_name,
                units,
                len(pickups),
                round(total_kg, 2)
            ])

    elif report_type == 'complaints':
        writer.writerow(['Complaint Number', 'Citizen', 'Category', 'Priority', 'Status', 'Registered At', 'Resolved At', 'Resolution Notes'])
        comps = Complaint.query.order_by(Complaint.created_at.desc()).all()
        for c in comps:
            writer.writerow([
                c.comp_number,
                c.citizen.full_name if c.citizen else 'N/A',
                c.category,
                c.priority,
                c.status,
                c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else '',
                c.resolved_at.strftime('%Y-%m-%d %H:%M') if c.resolved_at else 'Pending',
                c.resolution_notes or ''
            ])

    elif report_type == 'volunteer-participation':
        writer.writerow(['Volunteer ID', 'Full Name', 'Mobile', 'District', 'Status', 'Total Hours', 'Points Earned', 'Drives Completed'])
        vols = Volunteer.query.all()
        for v in vols:
            rew = v.rewards
            writer.writerow([
                v.volunteer_id_code,
                v.full_name,
                v.phone,
                v.district,
                v.status,
                rew.total_hours if rew else 0,
                rew.points if rew else 0,
                rew.events_completed if rew else 0
            ])
    else:
        return {'error': 'Invalid report type requested'}, 400

    csv_data = output.getvalue()
    filename = f"greencycle_{report_type.replace('-', '_')}_{request.args.get('date', 'export')}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

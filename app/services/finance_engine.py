from datetime import datetime, date
from sqlalchemy import func
from app.extensions import db
from app.models.finance import UserFeeRule, MaterialRate, OperationalCost, Payment, Transaction
from app.models.collection import Pickup, PickupItem
from app.models.waste import CollectionRequest, WasteCategory
from app.models.civic import Address, LocalBody
from app.models.operations import Vehicle, Facility
from app.models.feedback import SystemConfig

def get_applicable_user_fee(local_body_id: int, customer_type: str = 'Household', service_type: str = 'Standard Household Collection'):
    """Resolves the user fee from active user_fee_rules."""
    today = date.today()
    rule = UserFeeRule.query.filter(
        UserFeeRule.local_body_id == local_body_id,
        UserFeeRule.customer_type == customer_type,
        UserFeeRule.active == True,
        UserFeeRule.effective_from <= today
    ).order_by(UserFeeRule.id.desc()).first()

    if not rule:
        # Fallback to general rule or default demo rate
        rule = UserFeeRule.query.filter(
            UserFeeRule.customer_type == customer_type,
            UserFeeRule.active == True
        ).first()

    if rule:
        return {
            'rule_id': rule.id,
            'base_fee': rule.base_fee,
            'additional_fee': rule.additional_fee,
            'service_type': rule.service_type,
            'frequency': rule.collection_frequency,
            'notes': rule.notes
        }

    # Safe fallback if rules are being configured
    default_base = 250.0 if 'Shop' in customer_type or 'Commercial' in customer_type else 100.0
    return {
        'rule_id': None,
        'base_fee': default_base,
        'additional_fee': 0.0,
        'service_type': service_type,
        'frequency': 'Monthly',
        'notes': '[DEMO DATA] Default baseline fee'
    }

def calculate_pickup_material_economics(pickup_id: int):
    """
    Calculates material economic value from verified or actual weights:
    Material Value = Verified Weight * Purchase Rate
    Citizen Payout = Verified Weight * Buyback Rate (separate transaction)
    """
    pickup = db.session.get(Pickup, pickup_id)
    if not pickup:
        return {'material_value': 0.0, 'citizen_payout': 0.0, 'items_breakdown': []}

    total_material_value = 0.0
    total_citizen_payout = 0.0
    breakdown = []

    req = pickup.collection_request
    local_body_id = req.local_body_id if req else None

    for item in pickup.items:
        weight = item.verified_weight if item.verified_weight > 0 else item.actual_weight
        if weight <= 0:
            continue

        # Look up active material rate
        rate = MaterialRate.query.filter(
            MaterialRate.waste_category_id == item.waste_category_id,
            MaterialRate.active == True
        ).order_by(MaterialRate.id.desc()).first()

        purchase_rate = rate.purchase_rate if rate else 10.0
        buyback_rate = rate.buyback_rate if rate else 0.0

        item_value = weight * purchase_rate
        item_payout = weight * buyback_rate

        total_material_value += item_value
        total_citizen_payout += item_payout

        breakdown.append({
            'category_id': item.waste_category_id,
            'category_name': item.category.name if item.category else 'Unknown',
            'weight_kg': weight,
            'purchase_rate': purchase_rate,
            'buyback_rate': buyback_rate,
            'material_value': round(item_value, 2),
            'citizen_payout': round(item_payout, 2)
        })

    return {
        'material_value': round(total_material_value, 2),
        'citizen_payout': round(total_citizen_payout, 2),
        'items_breakdown': breakdown
    }

def calculate_fuel_cost(distance_km: float, vehicle_id: int):
    """
    Fuel Consumed = Distance / Vehicle Mileage
    Fuel Cost = Fuel Consumed * Configured Fuel Price
    """
    vehicle = db.session.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.mileage_kml <= 0:
        mileage = 10.0
        fuel_type = 'Diesel'
    else:
        mileage = vehicle.mileage_kml
        fuel_type = vehicle.fuel_type

    # Read fuel price config
    config_key = f"FUEL_PRICE_{fuel_type.upper()}"
    cfg = SystemConfig.query.filter_by(config_key=config_key).first()
    if cfg:
        price = float(cfg.config_value)
    else:
        price = 94.50 if fuel_type == 'Diesel' else (7.50 if fuel_type == 'Electric' else 105.20)

    fuel_consumed = distance_km / mileage
    fuel_cost = fuel_consumed * price
    return {
        'distance_km': distance_km,
        'mileage_kml': mileage,
        'fuel_type': fuel_type,
        'fuel_price': price,
        'fuel_consumed': round(fuel_consumed, 2),
        'fuel_cost': round(fuel_cost, 2)
    }

def get_business_economics_summary(local_body_id=None, start_date=None, end_date=None):
    """
    Computes overall P&L and operational unit economics:
    Revenue = User Fees Collected + Material Value
    Operating Costs = Sum of Operational Costs
    Net Operating Result = Revenue - Costs
    """
    # 1. Collection User Fees
    fee_query = db.session.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.status == 'Successful'
    )
    if local_body_id:
        fee_query = fee_query.join(UserFeeRule, Payment.fee_rule_id == UserFeeRule.id).filter(
            UserFeeRule.local_body_id == local_body_id
        )
    user_fee_revenue = float(fee_query.scalar() or 0.0)

    # 2. Material Revenue
    pickup_items = PickupItem.query.all()
    material_revenue = 0.0
    total_waste_kg = 0.0

    rates_cache = {r.waste_category_id: r for r in MaterialRate.query.filter_by(active=True).all()}
    for pi in pickup_items:
        w = pi.verified_weight if pi.verified_weight > 0 else pi.actual_weight
        if w > 0:
            total_waste_kg += w
            rate = rates_cache.get(pi.waste_category_id)
            pr = rate.purchase_rate if rate else 10.0
            material_revenue += (w * pr)

    total_revenue = user_fee_revenue + material_revenue

    # 3. Operational Costs breakdown
    cost_query = OperationalCost.query
    if local_body_id:
        cost_query = cost_query.filter(OperationalCost.local_body_id == local_body_id)
    costs = cost_query.all()

    cost_by_category = {}
    total_operating_cost = 0.0
    for c in costs:
        total_operating_cost += c.amount
        cost_by_category[c.category] = cost_by_category.get(c.category, 0.0) + c.amount

    net_operating_result = total_revenue - total_operating_cost

    # 4. Unit economics
    pickups_count = Pickup.query.filter(Pickup.status.in_(['Completed', 'Collected', 'Verified'])).count() or 1
    safe_kg = total_waste_kg if total_waste_kg > 0 else 1.0

    return {
        'total_revenue': round(total_revenue, 2),
        'user_fee_revenue': round(user_fee_revenue, 2),
        'material_revenue': round(material_revenue, 2),
        'total_operating_cost': round(total_operating_cost, 2),
        'net_operating_result': round(net_operating_result, 2),
        'cost_breakdown': {k: round(v, 2) for k, v in cost_by_category.items()},
        'total_waste_kg': round(total_waste_kg, 2),
        'pickups_completed_count': pickups_count,
        'revenue_per_pickup': round(total_revenue / pickups_count, 2),
        'cost_per_pickup': round(total_operating_cost / pickups_count, 2),
        'net_per_pickup': round(net_operating_result / pickups_count, 2),
        'revenue_per_kg': round(total_revenue / safe_kg, 2),
        'cost_per_kg': round(total_operating_cost / safe_kg, 2),
        'net_per_kg': round(net_operating_result / safe_kg, 2)
    }

def calculate_environmental_impact():
    """
    Computes diverted recyclables and estimated CO2 reduction.
    Clearly returned with disclaimer that conversions are estimates based on standard factors.
    """
    items = PickupItem.query.all()
    category_weights = {}
    total_diverted_kg = 0.0

    for it in items:
        w = it.verified_weight if it.verified_weight > 0 else it.actual_weight
        if w > 0:
            cat_code = it.category.code if it.category else 'OTHER'
            category_weights[cat_code] = category_weights.get(cat_code, 0.0) + w
            total_diverted_kg += w

    # Default Kerala conversion factors (kg CO2e saved / kg recovered)
    factors = {
        'PLASTIC': 1.5,
        'PAPER': 1.1,
        'CARDBOARD': 1.2,
        'GLASS': 0.3,
        'METAL': 2.8,
        'E-WASTE': 3.2,
        'TEXTILE': 1.8,
        'ORGANIC': 0.5,
        'OTHER': 0.5
    }

    total_co2_avoided_kg = 0.0
    breakdown = {}
    for code, kg in category_weights.items():
        factor = factors.get(code, 0.5)
        saved = kg * factor
        total_co2_avoided_kg += saved
        breakdown[code] = {
            'weight_kg': round(kg, 2),
            'factor': factor,
            'co2_saved_kg': round(saved, 2)
        }

    return {
        'total_waste_diverted_kg': round(total_diverted_kg, 2),
        'estimated_co2_avoided_kg': round(total_co2_avoided_kg, 2),
        'tree_equivalent': round(total_co2_avoided_kg / 21.0, 1),  # ~21 kg CO2 absorbed per tree/year
        'category_breakdown': breakdown,
        'disclaimer': 'Note: Environmental metrics are scientific estimates based on configured emission factors.'
    }

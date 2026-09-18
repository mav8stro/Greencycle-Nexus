from datetime import datetime, date, timedelta
from app.extensions import db
from app.models import (
    User, LocalBody, Ward, Address, WasteCategory,
    UserFeeRule, MaterialRate, OperationalCost, Transaction, Payment, PaymentReceipt,
    Collector, Vehicle, Facility, MaterialMovement, CollectionSchedule, Pickup, PickupItem,
    CollectionRequest, CollectionRequestItem, Complaint, SystemConfig,
    Volunteer, Event, EventRegistration, Attendance, VolunteerReward, Notification, AuditLog
)
from app.services.auth_service import hash_password

def seed_database():
    """Seeds the database with comprehensive Kerala civic and demonstration data."""
    if User.query.first():
        return  # Already seeded

    # 1. System Config
    configs = [
        SystemConfig(config_key='FUEL_PRICE_DIESEL', config_value='94.50', description='Diesel price per liter in Kerala'),
        SystemConfig(config_key='FUEL_PRICE_PETROL', config_value='105.20', description='Petrol price per liter in Kerala'),
        SystemConfig(config_key='FUEL_PRICE_ELECTRIC', config_value='7.50', description='Commercial EV charging rate per kWh in Kerala'),
        SystemConfig(config_key='PAYMENT_GATEWAY_MODE', config_value='MOCK_SECURE', description='Configurable payment gateway mode (MOCK_SECURE, RAZORPAY, STRIPE)'),
        SystemConfig(config_key='NOTIFICATION_EMAIL_ENABLED', config_value='false', description='Whether SMTP email triggers are active'),
        SystemConfig(config_key='VOLUNTEER_POINTS_PER_HOUR', config_value='15', description='Points awarded per volunteer hour (configurable by Admin)'),
        SystemConfig(config_key='VOLUNTEER_WASTE_KG_PER_EVENT', config_value='20.0', description='Estimated waste contribution (kg) credited per event (configurable estimate only)'),
        SystemConfig(config_key='CO2_FACTOR_DEFAULT', config_value='0.8', description='Default estimated kg CO2e avoided per kg waste diverted (clearly an estimate)'),
        SystemConfig(config_key='APP_NAME', config_value='GreenCycle Nexus', description='Application display name'),
        SystemConfig(config_key='APP_VERSION', config_value='2.0-kerala-civic', description='Application version string'),
    ]
    db.session.add_all(configs)

    # 2. Local Bodies
    kochi_corp = LocalBody(name='Kochi Municipal Corporation', district='Ernakulam', body_type='Corporation', pincode='682011', service_area='Central Kochi, Fort Kochi, Marine Drive, Edappally')
    kozhikode_corp = LocalBody(name='Kozhikode Municipal Corporation', district='Kozhikode', body_type='Corporation', pincode='673001', service_area='Mananchira, Beach, Mavoor Road')
    venganoor_gp = LocalBody(name='Venganoor Grama Panchayat', district='Thiruvananthapuram', body_type='Grama Panchayat', pincode='695523', service_area='Kovalam Rural, Venganoor North, Vizhinjam Outskirts')
    db.session.add_all([kochi_corp, kozhikode_corp, venganoor_gp])
    db.session.flush()

    # 3. Wards
    w_fort_kochi = Ward(local_body_id=kochi_corp.id, ward_number=1, ward_name='Fort Kochi Heritage', pincode='682001')
    w_marine_drive = Ward(local_body_id=kochi_corp.id, ward_number=12, ward_name='Marine Drive Waterfront', pincode='682031')
    w_palarivattom = Ward(local_body_id=kochi_corp.id, ward_number=14, ward_name='Palarivattom Commercial Hub', pincode='682025')
    w_mananchira = Ward(local_body_id=kozhikode_corp.id, ward_number=5, ward_name='Mananchira Central', pincode='673001')
    w_kovalam = Ward(local_body_id=venganoor_gp.id, ward_number=3, ward_name='Kovalam Rural Coast', pincode='695527')
    db.session.add_all([w_fort_kochi, w_marine_drive, w_palarivattom, w_mananchira, w_kovalam])
    db.session.flush()

    # 4. Waste Categories (All 11 Default Categories)
    cat_plastic = WasteCategory(code='PLASTIC', name='Plastic (Clean & Dry)', description='PET bottles, milk packets, containers, polythene covers', collection_type='Door-to-door dry', is_recyclable=True, requires_special_handling=False, sorting_instructions='Rinse milk packets and dry. Crush PET bottles.', disposal_route='Mini-MCF -> Central MCF -> Clean Kerala Company')
    cat_paper = WasteCategory(code='PAPER', name='Paper & Newspaper', description='Old newspapers, books, white paper, magazines', collection_type='Door-to-door dry', is_recyclable=True, requires_special_handling=False, sorting_instructions='Tie in neat bundles. Keep dry.', disposal_route='Mini-MCF -> Paper Recycling Mills')
    cat_cardboard = WasteCategory(code='CARDBOARD', name='Cardboard & Cartons', description='Corrugated boxes, packaging cartons', collection_type='Door-to-door dry', is_recyclable=True, requires_special_handling=False, sorting_instructions='Flatten all cardboard boxes before handover.', disposal_route='Central MCF -> Kraft Paper Recyclers')
    cat_glass = WasteCategory(code='GLASS', name='Glass Bottles & Jars', description='Beverage bottles, cosmetic glass containers, jars', collection_type='Drop-off / Monthly Special', is_recyclable=True, requires_special_handling=False, sorting_instructions='Separate broken glass carefully. Rinse bottles.', disposal_route='Central MCF -> Glass Re-melting Units')
    cat_metal = WasteCategory(code='METAL', name='Metal Scrap & Tins', description='Beverage cans, tin food containers, iron, aluminium scrap', collection_type='Door-to-door dry', is_recyclable=True, requires_special_handling=False, sorting_instructions='Rinse tin cans. Keep ferrous and non-ferrous separate if possible.', disposal_route='Central MCF -> Metal Smelting Foundries')
    cat_textile = WasteCategory(code='TEXTILE', name='Textile & Clean Rags', description='Clean discarded clothing, bedsheets, curtains', collection_type='Monthly Special', is_recyclable=True, requires_special_handling=False, sorting_instructions='Wash and dry. Mouldy textiles cannot be recycled.', disposal_route='RRF -> Fiber Reclamation Units')
    cat_ewaste = WasteCategory(code='E-WASTE', name='Electronic & Electrical Waste', description='Cables, chargers, old phones, tube lights, printed circuit boards', collection_type='Special On-demand Request', is_recyclable=True, requires_special_handling=True, sorting_instructions='CRITICAL: Do NOT tamper or dismantle batteries. Pack in cardboard boxes.', disposal_route='Authorized E-Waste Dismantler & Recycler (KSPCB Approved)')
    cat_organic = WasteCategory(code='ORGANIC', name='Organic / Biodegradable Waste', description='Kitchen food scraps, vegetable peels, garden waste', collection_type='Door-to-door wet', is_recyclable=True, requires_special_handling=False, sorting_instructions='Keep free of all plastic bags and staples.', disposal_route='Community Biogas Plant / Aerobic Compost Units')
    cat_sanitary = WasteCategory(code='SANITARY', name='Sanitary & Hygiene Waste', description='Diapers, sanitary pads, medical cotton', collection_type='Special Incineration Stream', is_recyclable=False, requires_special_handling=True, sorting_instructions='Wrap securely in paper and mark with red indicator. Keep strictly segregated.', disposal_route='Common Biomedical Waste Facility (IMAGE / KEIL)')
    cat_hazardous = WasteCategory(code='HAZARDOUS', name='Domestic Hazardous Waste', description='Pesticide containers, paint cans, expired chemicals, lithium batteries', collection_type='Special Collection Camp', is_recyclable=False, requires_special_handling=True, sorting_instructions='DANGER: Do not mix chemicals. Keep in original sealed containers with labels.', disposal_route='KEIL Hazardous Waste Treatment Facility Ambalamedu')
    cat_other = WasteCategory(code='OTHER', name='Other Non-Recyclable Dry Waste', description='Multi-layered packaging, thermocol, composite discards', collection_type='Door-to-door dry', is_recyclable=False, requires_special_handling=False, sorting_instructions='Keep dry and clean for RDF processing.', disposal_route='Refuse Derived Fuel (RDF) / Cement Kilns Co-processing')

    categories = [cat_plastic, cat_paper, cat_cardboard, cat_glass, cat_metal, cat_textile, cat_ewaste, cat_organic, cat_sanitary, cat_hazardous, cat_other]
    db.session.add_all(categories)
    db.session.flush()

    # 5. Users
    # Admin (Controlled)
    admin_user = User(
        phone='9000000001',
        email='admin@greencycle.kerala.gov.in',
        password_hash=hash_password('1111'),
        role='admin',
        full_name='Er. Rajesh Pillai (Chief Civic Officer)',
        is_active=True
    )
    
    # Citizen 1: Household
    cit1 = User(
        phone='9000000002',
        email='anand.varma@kerala.example.com',
        password_hash=hash_password('2222'),
        role='citizen',
        full_name='Anand Varma',
        is_active=True
    )

    # Citizen 2: Commercial Shop
    cit2 = User(
        phone='9000000004',
        email='sales@malabarspices.example.com',
        password_hash=hash_password('4444'),
        role='citizen',
        full_name='Malabar Spice Traders (Attn: George Thomas)',
        is_active=True
    )

    # Worker 1: Haritha Karma Sena Lead
    worker1 = User(
        phone='9000000003',
        email='suresh.collector@hks.kerala.gov.in',
        password_hash=hash_password('3333'),
        role='worker',
        full_name='Suresh Kumar',
        is_active=True
    )

    # Worker 2: Municipal Driver / Operator
    worker2 = User(
        phone='9000000005',
        email='rajesh.driver@kochicorp.kerala.gov.in',
        password_hash=hash_password('5555'),
        role='worker',
        full_name='Rajesh M. (Tipper Operator)',
        is_active=True
    )

    # Volunteer: Dr. Lakshmi Menon
    vol_user = User(
        phone='9000000006',
        email='lakshmi.menon@keralauniv.ac.in',
        password_hash=hash_password('6666'),
        role='volunteer',
        full_name='Dr. Lakshmi Menon',
        is_active=True,
        must_change_password=False
    )

    db.session.add_all([admin_user, cit1, cit2, worker1, worker2, vol_user])
    db.session.flush()

    # 6. Addresses
    addr_cit1 = Address(
        user_id=cit1.id,
        house_number='Flat 4B, Marine Crest',
        street_address='Shanmugham Road, Marine Drive',
        local_body_id=kochi_corp.id,
        ward_id=w_marine_drive.id,
        district='Ernakulam',
        pincode='682031',
        customer_type='Household',
        resident_count=4,
        preferred_day='Wednesday',
        preferred_slot='08:00 AM - 11:00 AM'
    )
    addr_cit2 = Address(
        user_id=cit2.id,
        house_number='Building XII/450',
        street_address='Palarivattom Junction, Bypass Road',
        local_body_id=kochi_corp.id,
        ward_id=w_palarivattom.id,
        district='Ernakulam',
        pincode='682025',
        customer_type='Shop',
        resident_count=8,
        preferred_day='Tuesday',
        preferred_slot='09:00 AM - 12:00 PM'
    )
    db.session.add_all([addr_cit1, addr_cit2])

    # 7. Worker / Collector Profiles
    col1 = Collector(
        user_id=worker1.id,
        local_body_id=kochi_corp.id,
        ward_id=w_marine_drive.id,
        route_name='Marine Drive Waterfront Route 12-A',
        employment_type='Haritha Karma Sena',
        salary_or_rate=450.0,
        rate_type='Daily',
        status='Active'
    )
    col2 = Collector(
        user_id=worker2.id,
        local_body_id=kochi_corp.id,
        ward_id=w_palarivattom.id,
        route_name='Palarivattom Commercial Route 14-B',
        employment_type='Municipal Staff',
        salary_or_rate=650.0,
        rate_type='Daily',
        status='Active'
    )
    db.session.add_all([col1, col2])

    # 8. Volunteer Profile & Rewards
    vol_profile = Volunteer(
        volunteer_id_code='GCN-VOL-2026-00001',
        user_id=vol_user.id,
        full_name='Dr. Lakshmi Menon',
        email='lakshmi.menon@keralauniv.ac.in',
        phone='9000000006',
        address='Plot 18, Cochin University Road, Kalamassery',
        district='Ernakulam',
        local_body_id=kochi_corp.id,
        skills='Environmental Auditing, Youth Outreach, Public Speaking',
        availability='Weekends & Holidays',
        emergency_contact='K. Menon (+91 9447001122)',
        status='Approved',
        approved_at=datetime.utcnow() - timedelta(days=30),
        approved_by=admin_user.id
    )
    db.session.add(vol_profile)
    db.session.flush()

    vol_reward = VolunteerReward(
        volunteer_id=vol_profile.id,
        points=240,
        total_hours=18.5,
        events_completed=4,
        waste_collected_kg=125.0,
        badges_json='["Coastal Guardian", "Clean Kerala Star", "Master Segregator"]'
    )
    db.session.add(vol_reward)

    # 9. Vehicles
    veh_ev = Vehicle(
        reg_number='KL-07-CD-1024',
        vehicle_type='Electric Mini-Tipper',
        fuel_type='Electric',
        mileage_kml=4.5,  # km/kWh
        capacity_kg=600.0,
        assigned_route='Marine Drive Ward 12',
        assigned_collector_id=worker1.id,
        active=True
    )
    veh_diesel = Vehicle(
        reg_number='KL-07-AB-4509',
        vehicle_type='Diesel Tipper Van',
        fuel_type='Diesel',
        mileage_kml=11.5,
        capacity_kg=1200.0,
        assigned_route='Palarivattom Ward 14',
        assigned_collector_id=worker2.id,
        active=True
    )
    db.session.add_all([veh_ev, veh_diesel])
    db.session.flush()

    # 10. Facilities
    fac_mini = Facility(name='Mini-MCF Marine Drive (Ward 12)', facility_type='Mini-MCF', local_body_id=kochi_corp.id, location='Near KSRTC Marine Drive Jetty', capacity_kg=2500.0, contact='+91 484 2361001', manager_name='Smt. Usha Kumari', status='Operational')
    fac_central = Facility(name='Central MCF Edappally', facility_type='MCF', local_body_id=kochi_corp.id, location='NH-66 Toll Gate Road, Edappally', capacity_kg=15000.0, contact='+91 484 2534220', manager_name='Shri. Biju Mohan', status='Operational')
    fac_rrf = Facility(name='Brahmapuram Resource Recovery Facility', facility_type='RRF', local_body_id=kochi_corp.id, location='Brahmapuram Industrial Estate', capacity_kg=50000.0, contact='+91 484 2789100', manager_name='Er. Mathew V.', status='Operational')
    fac_recycler = Facility(name='Clean Kerala Company Recycler Depot', facility_type='Authorized Recycler', local_body_id=kochi_corp.id, location='Eloor Industrial Belt, Aluva', capacity_kg=100000.0, contact='+91 484 2603344', manager_name='Clean Kerala Operations Head', status='Operational')
    fac_keil = Facility(name='KEIL Hazardous Waste Treatment Complex', facility_type='Disposal Facility', local_body_id=kochi_corp.id, location='Ambalamedu FACT Complex', capacity_kg=40000.0, contact='+91 484 2721111', manager_name='Safety Director KEIL', status='Operational')
    db.session.add_all([fac_mini, fac_central, fac_rrf, fac_recycler, fac_keil])
    db.session.flush()

    # 11. User Fee Rules [DEMO DATA]
    fee_rules = [
        UserFeeRule(local_body_id=kochi_corp.id, customer_type='Household', service_type='Standard Household Collection', collection_frequency='Monthly', base_fee=100.0, additional_fee=0.0, effective_from=date(2026, 1, 1), active=True, notes='[DEMO DATA] Standard monthly doorstep collection for residential units in Kochi Corp'),
        UserFeeRule(local_body_id=kochi_corp.id, customer_type='Shop', service_type='Commercial Collection', collection_frequency='Monthly', base_fee=250.0, additional_fee=0.0, effective_from=date(2026, 1, 1), active=True, notes='[DEMO DATA] Standard commercial shop monthly collection tariff'),
        UserFeeRule(local_body_id=kochi_corp.id, customer_type='Household', service_type='Special Pickup', collection_frequency='Per-Pickup', base_fee=150.0, additional_fee=10.0, effective_from=date(2026, 1, 1), active=True, notes='[DEMO DATA] On-demand special pickup (Base ₹150 + ₹10/kg extra)'),
        UserFeeRule(local_body_id=venganoor_gp.id, customer_type='Household', service_type='Standard Household Collection', collection_frequency='Monthly', base_fee=80.0, additional_fee=0.0, effective_from=date(2026, 1, 1), active=True, notes='[DEMO DATA] Grama Panchayat subsidized rate')
    ]
    db.session.add_all(fee_rules)
    db.session.flush()

    # 12. Material Rates [DEMO DATA]
    mat_rates = [
        MaterialRate(waste_category_id=cat_plastic.id, buyer_name='Clean Kerala Company', purchase_rate=18.0, buyback_rate=5.0, processing_cost=3.0, disposal_cost=1.0, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_paper.id, buyer_name='Ernakulam Paper Mills', purchase_rate=12.0, buyback_rate=4.0, processing_cost=2.0, disposal_cost=0.5, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_cardboard.id, buyer_name='Perumbavoor Kraft Recyclers', purchase_rate=11.0, buyback_rate=3.5, processing_cost=1.8, disposal_cost=0.5, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_glass.id, buyer_name='Cochin Glassworks', purchase_rate=4.5, buyback_rate=1.0, processing_cost=1.5, disposal_cost=1.0, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_metal.id, buyer_name='Kerala Smelting Consortium', purchase_rate=28.0, buyback_rate=10.0, processing_cost=4.0, disposal_cost=1.5, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_textile.id, buyer_name='Tirupur Shoddy Yarn Mills', purchase_rate=8.0, buyback_rate=2.0, processing_cost=2.0, disposal_cost=1.0, effective_from=date(2026, 1, 1), active=True),
        MaterialRate(waste_category_id=cat_ewaste.id, buyer_name='Green Clean E-Waste Dismantlers', purchase_rate=35.0, buyback_rate=12.0, processing_cost=15.0, disposal_cost=5.0, effective_from=date(2026, 1, 1), active=True)
    ]
    db.session.add_all(mat_rates)

    # 13. Collection Schedules
    sched1 = CollectionSchedule(local_body_id=kochi_corp.id, ward_id=w_marine_drive.id, route_name='Marine Drive Ward 12-A', waste_category_id=cat_plastic.id, collection_day='Wednesday', time_slot='08:00 AM - 11:00 AM', collector_id=worker1.id, vehicle_id=veh_ev.id, active=True)
    sched2 = CollectionSchedule(local_body_id=kochi_corp.id, ward_id=w_marine_drive.id, route_name='Marine Drive Ward 12-B', waste_category_id=cat_organic.id, collection_day='Monday', time_slot='07:30 AM - 10:00 AM', collector_id=worker1.id, vehicle_id=veh_ev.id, active=True)
    sched3 = CollectionSchedule(local_body_id=kochi_corp.id, ward_id=w_palarivattom.id, route_name='Palarivattom Ward 14-A', waste_category_id=cat_cardboard.id, collection_day='Tuesday', time_slot='09:00 AM - 12:00 PM', collector_id=worker2.id, vehicle_id=veh_diesel.id, active=True)
    db.session.add_all([sched1, sched2, sched3])

    # 14. Completed Pickup & Verification Example
    req1 = CollectionRequest(
        req_number='GCN-REQ-2026-00101',
        citizen_id=cit1.id,
        local_body_id=kochi_corp.id,
        ward_id=w_marine_drive.id,
        address_id=addr_cit1.id,
        requested_date=date.today() - timedelta(days=2),
        requested_slot='08:00 AM - 11:00 AM',
        notes='Household segregated dry recyclables and paper bundles',
        status='Completed',
        is_special_waste=False,
        created_at=datetime.utcnow() - timedelta(days=3)
    )
    db.session.add(req1)
    db.session.flush()

    item_plastic = CollectionRequestItem(request_id=req1.id, waste_category_id=cat_plastic.id, estimated_weight=4.0)
    item_paper = CollectionRequestItem(request_id=req1.id, waste_category_id=cat_paper.id, estimated_weight=6.0)
    db.session.add_all([item_plastic, item_paper])

    # Pickup record with Estimated vs Actual vs Verified weights
    pickup1 = Pickup(
        pickup_number='GCN-PKP-2026-00101',
        request_id=req1.id,
        citizen_id=cit1.id,
        collector_id=worker1.id,
        vehicle_id=veh_ev.id,
        scheduled_date=date.today() - timedelta(days=2),
        scheduled_slot='08:00 AM - 11:00 AM',
        status='Completed',
        started_at=datetime.utcnow() - timedelta(days=2, hours=3),
        arrived_at=datetime.utcnow() - timedelta(days=2, hours=2, minutes=45),
        completed_at=datetime.utcnow() - timedelta(days=2, hours=2, minutes=30),
        total_estimated_weight=10.0,
        total_actual_weight=11.2,
        total_verified_weight=11.2,
        weighed_by='Suresh Kumar (HKS Collector)',
        weighed_at=datetime.utcnow() - timedelta(days=2, hours=2, minutes=35),
        notes='Properly washed and dried segregated plastics and tied papers.'
    )
    db.session.add(pickup1)
    db.session.flush()

    p_item1 = PickupItem(pickup_id=pickup1.id, waste_category_id=cat_plastic.id, estimated_weight=4.0, actual_weight=4.5, verified_weight=4.5)
    p_item2 = PickupItem(pickup_id=pickup1.id, waste_category_id=cat_paper.id, estimated_weight=6.0, actual_weight=6.7, verified_weight=6.7)
    db.session.add_all([p_item1, p_item2])

    # Material Movement traceability record
    mov1 = MaterialMovement(
        movement_code='MOV-2026-00042',
        pickup_id=pickup1.id,
        waste_category_id=cat_plastic.id,
        source_type='Household',
        source_name='Marine Crest 4B, Ward 12',
        destination_type='Mini-MCF',
        destination_name='Mini-MCF Marine Drive (Ward 12)',
        weight_kg=4.5,
        status='Received',
        handler_id=worker1.id,
        movement_date=datetime.utcnow() - timedelta(days=2)
    )
    mov2 = MaterialMovement(
        movement_code='MOV-2026-00043',
        pickup_id=pickup1.id,
        waste_category_id=cat_plastic.id,
        source_type='Mini-MCF',
        source_name='Mini-MCF Marine Drive (Ward 12)',
        destination_type='Recycler',
        destination_name='Clean Kerala Company Recycler Depot',
        weight_kg=4.5,
        status='Dispatched',
        handler_id=admin_user.id,
        movement_date=datetime.utcnow() - timedelta(days=1)
    )
    db.session.add_all([mov1, mov2])

    # 15. Pending Special Waste Request Example
    req2 = CollectionRequest(
        req_number='GCN-REQ-2026-00102',
        citizen_id=cit1.id,
        local_body_id=kochi_corp.id,
        ward_id=w_marine_drive.id,
        address_id=addr_cit1.id,
        requested_date=date.today() + timedelta(days=2),
        requested_slot='09:00 AM - 12:00 PM',
        notes='Old CRT monitor and discarded laptop battery. Marked with hazard sticker.',
        status='Requested',
        is_special_waste=True,
        created_at=datetime.utcnow() - timedelta(hours=4)
    )
    db.session.add(req2)
    db.session.flush()
    item_ewaste = CollectionRequestItem(request_id=req2.id, waste_category_id=cat_ewaste.id, estimated_weight=8.5)
    db.session.add(item_ewaste)

    # 16. Financial Transactions & Payments
    # Successful Collection Fee Payment for Anand Varma
    pay1 = Payment(
        payment_number='PAY-2026-0091',
        user_id=cit1.id,
        fee_rule_id=fee_rules[0].id,
        amount=100.0,
        billing_period='September 2026',
        status='Successful',
        payment_method='UPI',
        due_date=date(2026, 9, 30),
        paid_at=datetime.utcnow() - timedelta(days=10),
        notes='Online UPI payment via BHIM/GPay'
    )
    db.session.add(pay1)
    db.session.flush()

    txn1 = Transaction(
        txn_number='TXN-UPI-9823411',
        user_id=cit1.id,
        transaction_type='COLLECTION_FEE',
        direction='CUSTOMER_TO_GREENCYCLE',
        amount=100.0,
        status='Successful',
        reference_id=pay1.payment_number,
        created_at=datetime.utcnow() - timedelta(days=10)
    )
    db.session.add(txn1)
    db.session.flush()

    rcpt1 = PaymentReceipt(
        receipt_number='RCPT-GCN-2026-0091',
        payment_id=pay1.id,
        transaction_id=txn1.id,
        user_id=cit1.id,
        amount=100.0,
        payment_method='UPI',
        issued_at=datetime.utcnow() - timedelta(days=10),
        receipt_data_json='{"customer_name": "Anand Varma", "ward": "Ward 12: Marine Drive", "service": "Standard Household Collection", "billing_period": "September 2026", "payment_mode": "UPI / NetBanking"}'
    )
    db.session.add(rcpt1)

    # Cash Payment recorded on doorstep by Collector, awaiting Admin Reconciliation
    pay_cash = Payment(
        payment_number='PAY-2026-0092',
        user_id=cit2.id,
        fee_rule_id=fee_rules[1].id,
        amount=250.0,
        billing_period='September 2026',
        status='Pending',
        payment_method='Cash',
        due_date=date(2026, 9, 30),
        paid_at=datetime.utcnow() - timedelta(hours=5),
        collector_id=worker2.id,
        approved_by_admin=False,
        notes='Cash received by Rajesh M. on doorstep route'
    )
    db.session.add(pay_cash)

    # 17. Operational Costs
    costs = [
        OperationalCost(category='Labour Cost', amount=900.0, cost_date=date.today() - timedelta(days=1), local_body_id=kochi_corp.id, ward_id=w_marine_drive.id, reference='HKS Daily Wage Voucher #881', notes='Daily honorarium for 2 HKS collectors', created_by=admin_user.id),
        OperationalCost(category='Fuel Cost', amount=380.0, cost_date=date.today() - timedelta(days=1), local_body_id=kochi_corp.id, ward_id=w_palarivattom.id, reference='Diesel Fuel Bill IOCL #4412', notes='4.02 liters diesel for collection tipper KL-07-AB-4509', created_by=admin_user.id),
        OperationalCost(category='PPE', amount=250.0, cost_date=date.today() - timedelta(days=5), local_body_id=kochi_corp.id, ward_id=w_marine_drive.id, reference='Safety Store Inv #102', notes='Rubber puncture-resistant gloves and masks for collectors', created_by=admin_user.id),
        OperationalCost(category='Sorting Cost', amount=320.0, cost_date=date.today() - timedelta(days=2), local_body_id=kochi_corp.id, reference='MCF Baler Operation', notes='Baling and sorting plastic scrap at Central MCF', created_by=admin_user.id)
    ]
    db.session.add_all(costs)

    # 18. Volunteer Events
    ev1 = Event(
        event_code='EVT-2026-COAST-01',
        title='Marine Drive Coastal Cleanup & Segregation Drive',
        description='Join Suchitwa Mission and GreenCycle Nexus to clear legacy plastics along the Marine Drive walkway and promote domestic segregation.',
        banner_url='https://images.unsplash.com/photo-1618477461853-cf6ed80faba5?auto=format&fit=crop&w=800&q=80',
        event_date=date.today() + timedelta(days=7),
        start_time='07:00 AM',
        end_time='11:00 AM',
        location='Marine Drive Rainbow Bridge Plaza, Ernakulam',
        local_body_id=kochi_corp.id,
        ward_id=w_marine_drive.id,
        max_participants=50,
        registration_deadline=date.today() + timedelta(days=5),
        required_skills='Basic waste segregation, enthusiasm',
        status='Published',
        qr_checkin_token='GCN-EVT-COAST-IN-9824',
        qr_checkout_token='GCN-EVT-COAST-OUT-9824'
    )
    ev2 = Event(
        event_code='EVT-2026-EWASTE-02',
        title='Mega E-Waste Collection & Awareness Camp',
        description='Community electronic waste collection drive with certified dismantler Clean Kerala Company.',
        event_date=date.today() + timedelta(days=14),
        start_time='09:00 AM',
        end_time='04:00 PM',
        location='Jawaharlal Nehru International Stadium Ground, Kaloor',
        local_body_id=kochi_corp.id,
        ward_id=w_palarivattom.id,
        max_participants=75,
        registration_deadline=date.today() + timedelta(days=12),
        required_skills='E-waste recording, safety guidance',
        status='Published',
        qr_checkin_token='GCN-EVT-EWASTE-IN-3109',
        qr_checkout_token='GCN-EVT-EWASTE-OUT-3109'
    )
    db.session.add_all([ev1, ev2])
    db.session.flush()

    # Volunteer Event Registration & Past Completed Attendance
    ev_reg = EventRegistration(event_id=ev1.id, volunteer_id=vol_profile.id, status='Approved', registered_at=datetime.utcnow() - timedelta(days=2))
    db.session.add(ev_reg)

    # 19. Complaint Example
    comp1 = Complaint(
        comp_number='CMP-2026-0041',
        citizen_id=cit1.id,
        pickup_id=pickup1.id,
        category='Waste Not Accepted',
        description='Collector initially hesitated to take bundled cardboard citing excess volume.',
        priority='Low',
        status='Resolved',
        assigned_admin_id=admin_user.id,
        resolution_notes='Spoke with HKS supervisor. Commercial and high volume dry waste collection schedule explained.',
        created_at=datetime.utcnow() - timedelta(days=2),
        resolved_at=datetime.utcnow() - timedelta(days=1)
    )
    db.session.add(comp1)

    # 20. Notification & Audit Log Examples
    n1 = Notification(user_id=cit1.id, title='Waste Collection Completed', message='Your dry recyclables (11.2 kg) were verified and collected by Suresh Kumar.', notification_type='pickup')
    n2 = Notification(user_id=worker1.id, title='Route Assigned for Wednesday', message='You have 18 doorstep collection stops assigned in Ward 12.', notification_type='schedule')
    n3 = Notification(user_id=admin_user.id, title='Pending Cash Reconciliation', message='Worker Rajesh M. recorded cash collection ₹250.00 from Malabar Spice Traders.', notification_type='payment')
    db.session.add_all([n1, n2, n3])

    audit1 = AuditLog(actor_id=admin_user.id, actor_role='admin', action='SEED_DATABASE', entity_type='System', entity_id='1', new_values='{"status": "Initialized Kerala civic seed data"}')
    db.session.add(audit1)

    db.session.commit()
    print("Database successfully seeded with realistic Kerala civic and operational demo data!")

import unittest
import json
from app import create_app
from app.extensions import db
from app.models import (
    User, CollectionRequest, Pickup, Payment, PaymentReceipt,
    Volunteer, Event, Attendance, UserFeeRule, WasteCategory
)

class GreenCycleNexusWorkflowTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def setUp(self):
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def get_token(self, phone, pin):
        res = self.client.post('/api/auth/login', json={'phone': phone, 'pin': pin})
        data = json.loads(res.data)
        self.assertEqual(res.status_code, 200, f"Login failed for {phone}: {data}")
        return data['token']

    def test_a_end_to_end_collection_workflow(self):
        """TEST A: Citizen registration -> Local Body -> Ward -> Collection request -> Schedule -> Collector assignment -> Actual weight -> Completion"""
        # 1. Register new citizen with Kerala civic details
        cit_phone = "9876500001"
        reg_res = self.client.post('/api/auth/register', json={
            'phone': cit_phone,
            'pin': '7777',
            'full_name': 'K. P. Narayanan',
            'role': 'citizen',
            'local_body_id': 1,
            'ward_id': 2,
            'house_number': 'House 14/B',
            'street_address': 'Marine Drive Walkway Road',
            'district': 'Ernakulam',
            'pincode': '682031',
            'customer_type': 'Household'
        })
        self.assertIn(reg_res.status_code, (201, 409))
        cit_token = self.get_token(cit_phone, '7777')

        # 2. Submit collection request
        cat = WasteCategory.query.filter_by(code='PLASTIC').first()
        req_res = self.client.post('/api/citizen/requests', headers={'Authorization': f'Bearer {cit_token}'}, json={
            'items': [{'waste_category_id': cat.id, 'estimated_weight': 5.0}],
            'requested_date': '2026-10-05',
            'requested_slot': '08:00 AM - 11:00 AM',
            'notes': 'Segregated PET bottles and clean milk covers'
        })
        self.assertEqual(req_res.status_code, 201)
        req_data = json.loads(req_res.data)['request']
        req_id = req_data['id']

        # 3. Admin schedules request into active Pickup and assigns Collector
        admin_token = self.get_token('9000000001', '1111')
        worker = User.query.filter_by(role='worker').first()
        sched_res = self.client.post(f'/api/collection/requests/{req_id}/schedule', headers={'Authorization': f'Bearer {admin_token}'}, json={
            'collector_id': worker.id,
            'scheduled_date': '2026-10-05'
        })
        self.assertEqual(sched_res.status_code, 201)
        pickup_id = json.loads(sched_res.data)['pickup']['id']

        # 4. Collector marks En Route and Arrived
        worker_token = self.get_token(worker.phone, '3333' if worker.phone == '9000000003' else '5555')
        enroute_res = self.client.post(f'/api/worker/pickups/{pickup_id}/status', headers={'Authorization': f'Bearer {worker_token}'}, json={'status': 'En Route'})
        self.assertEqual(enroute_res.status_code, 200)

        arrived_res = self.client.post(f'/api/worker/pickups/{pickup_id}/status', headers={'Authorization': f'Bearer {worker_token}'}, json={'status': 'Arrived'})
        self.assertEqual(arrived_res.status_code, 200)

        # 5. Collector weighs waste on doorstep, confirms actual weight, and completes pickup
        verify_res = self.client.post(f'/api/worker/pickups/{pickup_id}/verify', headers={'Authorization': f'Bearer {worker_token}'}, json={
            'items': [{'waste_category_id': cat.id, 'actual_weight': 5.8}],
            'notes': 'Verified clean segregated dry plastic at calibrated portable scale'
        })
        self.assertEqual(verify_res.status_code, 200)
        verify_data = json.loads(verify_res.data)['pickup']
        self.assertEqual(verify_data['status'], 'Completed')
        self.assertEqual(verify_data['total_actual_weight'], 5.8)

    def test_b_citizen_payment_and_receipt(self):
        """TEST B: Citizen payment -> Pending -> Successful -> Receipt -> Dashboard updated"""
        cit_token = self.get_token('9000000002', '2222')
        # 1. Initiate payment
        init_res = self.client.post('/api/payments/initiate', headers={'Authorization': f'Bearer {cit_token}'}, json={
            'amount': 100.0,
            'billing_period': 'October 2026',
            'payment_method': 'UPI'
        })
        self.assertEqual(init_res.status_code, 200)
        pay_id = json.loads(init_res.data)['payment_id']

        # 2. Server-side verified confirmation
        conf_res = self.client.post(f'/api/payments/{pay_id}/confirm', headers={'Authorization': f'Bearer {cit_token}'}, json={
            'transaction_reference': 'UPI-TEST-OCT-9988'
        })
        self.assertEqual(conf_res.status_code, 200)
        conf_data = json.loads(conf_res.data)
        self.assertEqual(conf_data['payment']['status'], 'Successful')
        self.assertIsNotNone(conf_data['receipt']['receipt_number'])

        # 3. Retrieve receipt
        rcpt_res = self.client.get(f'/api/payments/{pay_id}/receipt', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(rcpt_res.status_code, 200)

    def test_c_doorstep_cash_and_admin_reconciliation(self):
        """TEST C: Cash payment -> Collector records -> Admin approves -> Reconciliation"""
        worker_token = self.get_token('9000000003', '3333')
        cit = User.query.filter_by(phone='9000000002').first()

        # 1. Worker records cash
        cash_res = self.client.post('/api/worker/cash', headers={'Authorization': f'Bearer {worker_token}'}, json={
            'citizen_id': cit.id,
            'amount': 100.0,
            'billing_period': 'November 2026',
            'notes': 'Received ₹100 cash on doorstep'
        })
        self.assertEqual(cash_res.status_code, 201)
        pay_id = json.loads(cash_res.data)['payment']['id']

        # 2. Admin views reconciliation queue
        admin_token = self.get_token('9000000001', '1111')
        q_res = self.client.get('/api/admin/cash-reconciliation', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(q_res.status_code, 200)

        # 3. Admin approves and reconciles
        app_res = self.client.post(f'/api/admin/cash-reconciliation/{pay_id}/approve', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(app_res.status_code, 200)
        app_data = json.loads(app_res.data)
        self.assertTrue(app_data['payment']['approved_by_admin'])
        self.assertEqual(app_data['payment']['status'], 'Successful')

    def test_d_volunteer_onboarding_and_credentials(self):
        """TEST D: Volunteer -> Registration -> Admin approval -> Volunteer ID -> Temp password -> First login -> Password change"""
        vol_phone = "9876500002"
        # 1. Registration
        reg_res = self.client.post('/api/auth/register', json={
            'phone': vol_phone,
            'pin': '5555',
            'full_name': 'Meera Nair',
            'role': 'volunteer',
            'email': 'meera.nair@example.kerala.gov.in',
            'address': 'Kaloor, Ernakulam',
            'district': 'Ernakulam'
        })
        self.assertIn(reg_res.status_code, (201, 409))
        vol = Volunteer.query.filter_by(phone=vol_phone).first()

        # 2. Admin approves volunteer
        admin_token = self.get_token('9000000001', '1111')
        app_res = self.client.post(f'/api/admin/volunteers/{vol.id}/approve', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(app_res.status_code, 200)
        app_data = json.loads(app_res.data)
        temp_pass = app_data['temporary_password']
        self.assertTrue(app_data['generated_volunteer_id'].startswith('GCN-VOL-2026-'))

        # 3. First login with temporary credentials
        login_res = self.client.post('/api/auth/login', json={'phone': vol_phone, 'pin': temp_pass})
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        self.assertTrue(login_data['must_change_password'])
        vol_token = login_data['token']

        # 4. Password change
        ch_res = self.client.post('/api/auth/change-password', headers={'Authorization': f'Bearer {vol_token}'}, json={
            'old_pin': temp_pass,
            'new_pin': '8888'
        })
        self.assertEqual(ch_res.status_code, 200)

        # 5. Verify login with new password
        verify_login = self.client.post('/api/auth/login', json={'phone': vol_phone, 'pin': '8888'})
        self.assertEqual(verify_login.status_code, 200)

    def test_e_event_registration_and_qr_attendance(self):
        """TEST E: Event -> Admin creates -> Volunteer registers -> QR check-in -> QR check-out -> Hours & points"""
        admin_token = self.get_token('9000000001', '1111')
        # 1. Admin creates event
        ev_res = self.client.post('/api/events', headers={'Authorization': f'Bearer {admin_token}'}, json={
            'title': 'Subhash Park Plastic-Free Campaign',
            'description': 'Civic anti-littering and plastic audit drive',
            'event_date': '2026-10-12',
            'location': 'Subhash Bose Park, Ernakulam',
            'max_participants': 40
        })
        self.assertEqual(ev_res.status_code, 201)
        ev_data = json.loads(ev_res.data)
        ev_id = ev_data['id']
        in_token = ev_data['qr_checkin_token']
        out_token = ev_data['qr_checkout_token']

        # 2. Volunteer registers
        vol_token = self.get_token('9000000006', '6666')
        reg_res = self.client.post(f'/api/volunteer/events/{ev_id}/register', headers={'Authorization': f'Bearer {vol_token}'})
        self.assertEqual(reg_res.status_code, 201)

        # 3. QR Check-in
        cin_res = self.client.post('/api/volunteer/attendance/qr-checkin', headers={'Authorization': f'Bearer {vol_token}'}, json={
            'qr_token': in_token
        })
        self.assertEqual(cin_res.status_code, 200)

        # 4. Duplicate Check-in prevented
        dup_res = self.client.post('/api/volunteer/attendance/qr-checkin', headers={'Authorization': f'Bearer {vol_token}'}, json={
            'qr_token': in_token
        })
        self.assertEqual(dup_res.status_code, 400)

        # 5. QR Check-out
        cout_res = self.client.post('/api/volunteer/attendance/qr-checkout', headers={'Authorization': f'Bearer {vol_token}'}, json={
            'qr_token': out_token
        })
        self.assertEqual(cout_res.status_code, 200)
        cout_data = json.loads(cout_res.data)
        self.assertGreaterEqual(cout_data['attendance']['hours_spent'], 2.0)
        self.assertGreaterEqual(cout_data['rewards']['points'], 30)

    def test_f_special_waste_handling(self):
        """TEST F: Special waste -> Citizen requests -> System identifies special handling -> Movement recorded"""
        cit_token = self.get_token('9000000002', '2222')
        ewaste_cat = WasteCategory.query.filter_by(code='E-WASTE').first()
        self.assertTrue(ewaste_cat.requires_special_handling)

        req_res = self.client.post('/api/citizen/requests', headers={'Authorization': f'Bearer {cit_token}'}, json={
            'items': [{'waste_category_id': ewaste_cat.id, 'estimated_weight': 12.0}],
            'requested_date': '2026-10-18',
            'requested_slot': '09:00 AM - 12:00 PM',
            'notes': 'Old computer UPS and lithium inverter battery'
        })
        self.assertEqual(req_res.status_code, 201)
        req_data = json.loads(req_res.data)
        self.assertTrue(req_data['special_waste_alert'])
        self.assertTrue(req_data['request']['is_special_waste'])

    def test_g_idor_protection(self):
        """TEST G: Citizen 1 attempts to access Citizen 2's request -> Returns 403"""
        cit1_token = self.get_token('9000000002', '2222')
        # Create request belonging to Citizen 2
        cit2 = User.query.filter_by(phone='9000000004').first()
        req2 = CollectionRequest.query.filter_by(citizen_id=cit2.id).first()
        if not req2:
            cit2_token = self.get_token('9000000004', '4444')
            cat = WasteCategory.query.first()
            r = self.client.post('/api/citizen/requests', headers={'Authorization': f'Bearer {cit2_token}'}, json={
                'items': [{'waste_category_id': cat.id, 'estimated_weight': 2.0}],
                'requested_date': '2026-10-20'
            })
            req2_id = json.loads(r.data)['request']['id']
        else:
            req2_id = req2.id

        # Citizen 1 tries to access Citizen 2's request detail
        idor_res = self.client.get(f'/api/citizen/requests/{req2_id}', headers={'Authorization': f'Bearer {cit1_token}'})
        self.assertEqual(idor_res.status_code, 403)

    def test_h_role_authorization(self):
        """TEST H: Non-admin attempts admin API -> Returns 403"""
        cit_token = self.get_token('9000000002', '2222')
        res = self.client.get('/api/admin/dashboard', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(res.status_code, 403)

        res2 = self.client.get('/api/admin/cash-reconciliation', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(res2.status_code, 403)

    def test_i_legacy_backwards_compatible_endpoints(self):
        """TEST I: Backwards-compatible root endpoints & model methods from README specification"""
        # 1. Citizen login via legacy /login
        cit_res = self.client.post('/login', json={'phone': '9000000002', 'pin': '2222'})
        self.assertEqual(cit_res.status_code, 200)
        cit_data = json.loads(cit_res.data)
        self.assertIn('token', cit_data)
        self.assertIn('user_id', cit_data)
        cit_token = cit_data['token']
        cit_id = cit_data['user_id']

        # 2. Log waste via legacy /waste
        waste_res = self.client.post('/waste', headers={'Authorization': f'Bearer {cit_token}'}, json={
            'food': 4.0,
            'plastic': 2.0,
            'other': 1.0
        })
        self.assertEqual(waste_res.status_code, 201)
        entry = json.loads(waste_res.data)
        self.assertEqual(entry['amount'], 15.0)  # 4*2 + 2*3 + 1*1 = 8 + 6 + 1 = 15
        entry_id = entry['id']

        # 3. View history via legacy /history/<id>
        hist_res = self.client.get(f'/history/{cit_id}', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(hist_res.status_code, 200)
        history_list = json.loads(hist_res.data)
        self.assertTrue(any(e['id'] == entry_id for e in history_list))

        # 4. Admin login and view pending via legacy /pending
        admin_res = self.client.post('/login', json={'phone': '9000000001', 'pin': '1111'})
        self.assertEqual(admin_res.status_code, 200)
        admin_token = json.loads(admin_res.data)['token']

        pending_res = self.client.get('/pending', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(pending_res.status_code, 200)
        pending_list = json.loads(pending_res.data)
        self.assertTrue(any(e['id'] == entry_id for e in pending_list))

        # 5. Admin approve via legacy /approve/<id>
        app_res = self.client.post(f'/approve/{entry_id}', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(app_res.status_code, 200)
        app_data = json.loads(app_res.data)
        self.assertEqual(app_data['payment_created']['amount'], 15.0)

        # 6. Citizen view payments via legacy /payments/<id>
        pay_res = self.client.get(f'/payments/{cit_id}', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(pay_res.status_code, 200)
        pay_data = json.loads(pay_res.data)
        self.assertIn('total_due', pay_data)

        # 7. Citizen view schedule via legacy /schedule/<id>
        sched_res = self.client.get(f'/schedule/{cit_id}', headers={'Authorization': f'Bearer {cit_token}'})
        self.assertEqual(sched_res.status_code, 200)

        # 8. Worker login and pickups via legacy /pickups/<worker_id>
        worker_res = self.client.post('/login', json={'phone': '9000000003', 'pin': '3333'})
        self.assertEqual(worker_res.status_code, 200)
        worker_data = json.loads(worker_res.data)
        worker_token = worker_data['token']
        worker_id = worker_data['user_id']

        pickups_res = self.client.get(f'/pickups/{worker_id}', headers={'Authorization': f'Bearer {worker_token}'})
        self.assertEqual(pickups_res.status_code, 200)
        worker_pickups = json.loads(pickups_res.data)

        # 9. Worker collect via legacy /collect/<id>
        if worker_pickups:
            p_id = worker_pickups[0]['id']
            col_res = self.client.post(f'/collect/{p_id}', headers={'Authorization': f'Bearer {worker_token}'})
            self.assertEqual(col_res.status_code, 200)

        # 10. Model properties backwards compatibility
        user = User.query.filter_by(phone='9000000002').first()
        self.assertIsNotNone(user.pin)
        self.assertTrue(len(user.waste_entries) > 0)

        we = user.waste_entries[0]
        self.assertAlmostEqual(we.total_amount(), (we.food * 2) + (we.plastic * 3) + (we.other * 1))

        pay = Payment.query.filter_by(user_id=cit_id).first()
        self.assertIsNotNone(pay.paid)

        # 11. Model Query backwards compatibility (filter_by aliases and hybrid expressions)
        unpaid_pays = Payment.query.filter_by(paid=False).all()
        self.assertTrue(len(unpaid_pays) > 0)
        paid_pays = Payment.query.filter_by(paid=True).all()
        self.assertTrue(len(paid_pays) > 0)

        cit_pickups = Pickup.query.filter_by(user_id=cit_id).all()
        self.assertTrue(len(cit_pickups) > 0)
        wkr_pickups = Pickup.query.filter_by(worker_id=worker_id).all()
        self.assertTrue(len(wkr_pickups) > 0)
        ordered_pickups = Pickup.query.order_by(Pickup.date.asc()).all()
        self.assertTrue(len(ordered_pickups) > 0)

        queried_user = User.query.filter_by(phone=user.phone, pin=user.pin).first()
        self.assertIsNotNone(queried_user)
        self.assertEqual(queried_user.id, user.id)
        self.assertTrue(len(user.pickups_as_worker) >= 0)

if __name__ == '__main__':
    unittest.main()

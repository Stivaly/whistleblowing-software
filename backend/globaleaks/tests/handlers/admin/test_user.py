from globaleaks import models
from globaleaks.rest import errors
from globaleaks.handlers.admin import user
from globaleaks.tests import helpers


class TestAdminCollection(helpers.TestCollectionHandler):
    _handler = user.UsersCollection
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'admin',
            'name': 'Mario Rossi',
            'mail_address': 'admin@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }

    def get_dummy_request(self):
        data = helpers.TestCollectionHandler.get_dummy_request(self)
        data['pgp_key_remove'] = False
        return data


class TestAdminInstance(helpers.TestInstanceHandler):
    _handler = user.UserInstance
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'admin',
            'mail_address': 'admin@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }

    def get_dummy_request(self):
        data = helpers.TestInstanceHandler.get_dummy_request(self)
        data['pgp_key_remove'] = False
        return data


class TestReceiverCollection(TestAdminCollection):
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'receiver',
            'name': 'Mario Rossi',
            'mail_address': 'receiver@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }


class TestReceiverInstance(TestAdminInstance):
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'receiver',
            'name': 'Mario Rossi',
            'mail_address': 'receiver@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }


class TestCustodianCollection(TestAdminCollection):
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'custodian',
            'name': 'Mario Rossi',
            'mail_address': 'custodian@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }


class TestCustodianInstance(TestAdminInstance):
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'custodian',
            'mail_address': 'custodian@theguardian.com',
            'language': 'en'
        }
    }


class TestAdminPermissionsUpdate(helpers.TestInstanceHandler):
    _handler = user.UserInstance
    _test_desc = {
        'model': models.User,
        'create': user.create_user,
        'data': {
            'role': 'receiver',
            'mail_address': 'receiver@theguardian.com',
            'language': 'en',
            'send_activation_link': True
        }
    }

    def get_dummy_request(self):
        data = helpers.TestInstanceHandler.get_dummy_request(self)
        data['pgp_key_remove'] = False
        return data

    @helpers.inlineCallbacks
    def test_put_each_permission(self):
        perms = ['can_edit_general_settings', 'can_delete_submission',
                 'can_postpone_expiration', 'can_grant_access_to_reports',
                 'can_redact_information', 'can_mask_information',
                 'can_transfer_access_to_reports', 'forcefully_selected',
                 'notification', 'enabled']

        data = self.get_dummy_request()
        data = yield self._test_desc['create'](1, self.session, data, 'en')
        data.update(self._test_desc['data'])

        for p in perms:
            for value in (True, False):
                data[p] = value
                handler = self.request(dict(data), role='admin')
                ret = yield handler.put(data['id'])
                self.assertEqual(ret[p], value)

    @helpers.inlineCallbacks
    def test_put_duplicate_username(self):
        data = yield self._test_desc['create'](1, self.session, self.get_dummy_request(), 'en')
        data.update(self._test_desc['data'])
        data['username'] = self.dummyAdmin['username']
        handler = self.request(dict(data), role='admin')
        yield self.assertFailure(handler.put(data['id']), errors.DuplicateUserError)

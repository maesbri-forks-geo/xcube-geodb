import json
import os
import unittest
from xml.etree.ElementTree import XML

import requests_mock
from requests import HTTPError

from xcube_geodb.core.geoserver import Geoserver, GeoserverError
from xcube_geodb.core.message import Message

WORKSPACES_XML = """
<workspaces>
<workspace>
<name>test</name>
</workspace>
</workspaces>
"""


@requests_mock.mock(real_http=True)
class TestGeoserver(unittest.TestCase):
    def setUp(self) -> None:
        self._gs_admin = Geoserver(user_name='test', user_password='ohje', admin_user_name='admin',
                                   admin_pwd='bla', dotenv_file="tests/envs/.env_test")
        self._gs_user = Geoserver(user_name='test', user_password='ohje', dotenv_file="tests/envs/.env_test")

    def test_is_admin(self, m, url, method, **argv):
        expected_response = f"403 Client Error: Forbidden for url: {url}"
        m.post(url, text=json.dumps(expected_response), status_code=403, reason="Forbidden")

        with self.assertRaises(HTTPError) as e:
            method(**argv)

        self.assertEqual(expected_response, str(e.exception))

    def test_is_authorized(self, m, url, method, **argv):
        expected_response = f"401 Client Error: Unauthorized for url: {url}"
        m.post(url, text=json.dumps(expected_response), status_code=401, reason="Unauthorized")

        with self.assertRaises(HTTPError) as e:
            method(**argv)

        self.assertEqual(expected_response, str(e.exception))

    def test_register_user(self, m):
        url = f"{self._gs_user.url}/rest/security/usergroup/users"
        self.test_is_admin(url=url, method=self._gs_user.register_user)

        expected_response = f"<h1>User {self._gs_user.user_name} successfully added</h1>"

        m.post(url, text=json.dumps({'user': 'admin'}))

        r = self._gs_admin.register_user()
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)
        self.assertIn('User test', str(r))

    def test_register_catalog(self, m):
        url = f"{self._gs_user.url}/rest/workspaces/"
        # self.test_admin_method(url=url, method=self._gs_user.register_user_catalog)

        expected_response = f"<h1>Catalog {self._gs_user.user_name} successfully added</h1>"

        m.post(url, text=json.dumps({'catalog': 'test'}))
        url = f"{self._gs_user.url}/rest/workspaces.xml"
        m.get(url, text=WORKSPACES_XML)

        r = self._gs_admin.register_user_catalog()
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)

    def test_register_user_datastore(self, m):
        url = f"{self._gs_user.url}/rest/workspaces/{self._gs_user.user_name}/datastores"

        self.test_is_admin(url=url, method=self._gs_user.register_user_datastore)

        expected_response = f"<h1>Datastore {self._gs_user.user_name} successfully added</h1>"

        m.post(url, text=json.dumps({'user': 'admin'}))

        r = self._gs_admin.register_user_datastore()
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)

    def test_user_access(self, m):
        url = f"{self._gs_user.url}/rest/security/acl/layers"

        self.test_is_admin(url=url, method=self._gs_user.register_user_access)

        expected_response = f"<h1>User access for {self._gs_user.user_name} successfully added</h1>"

        m.post(url, text=json.dumps({'user': 'admin'}))

        r = self._gs_admin.register_user_access()
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)

    def test_register_user_role(self, m):
        url = f"{self._gs_user.url}/rest/roles/role/{self._gs_user.user_name}"

        self.test_is_admin(url=url, method=self._gs_user.register_user_role)

        expected_response = f"<h1>User role for {self._gs_user.user_name} successfully added</h1>"

        m.post(url, text=json.dumps({'user': 'admin'}))

        r = self._gs_admin.register_user_role()
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)

    def test_publish_collection(self, m):
        url = f"{self._gs_user.url}/rest/rest/workspaces/{self._gs_user.user_name}/datastores/" \
              f"{self._gs_user._user_name}:{self._gs_user._user_name}_geodb/featuretypes"

        collection = "collection"

        self.test_is_authorized(url=url, method=self._gs_user.publish_collection, collection=collection,
                                bbox=(1, 2, 3, 4), bbox_latlon=(2, 3, 4, 5))

        expected_response = f"<h1>Collection {collection} published (test/wms?" \
                            f"service=WMS&version=1.1.0&request=GetMap&layers=test%3Acollection&bbox=1,2,3,4&" \
                            f"width=768&height=496&srs=EPSG%3A3794&format=application/openlayers).</h1>"

        m.post(url, text=json.dumps({'user': 'admin'}))

        r = self._gs_user.publish_collection(collection=collection, bbox=(1, 2, 3, 4), bbox_latlon=(2, 3, 4, 5))
        self.assertEqual(expected_response, str(r))
        self.assertIsInstance(r, Message)


if __name__ == '__main__':
    unittest.main()

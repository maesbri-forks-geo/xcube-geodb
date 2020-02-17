import logging
import os
from typing import Optional, Tuple

import requests
from dotenv import find_dotenv, load_dotenv
from geoserver.catalog import Catalog

from xcube_geodb.core.message import Message

LOGGER = logging.getLogger("geodb.core.geoserver")
logging.basicConfig(level=logging.INFO)


class GeoserverError(ValueError):
    pass


class Geoserver:
    def __init__(self,
                 user_name: Optional[str] = None,
                 user_password: Optional[str] = None,
                 url: Optional[str] = None,
                 admin_user_name: Optional[str] = None,
                 admin_pwd: Optional[str] = None,
                 dotenv_file: str = ".env"
                 ):
        self._dotenv_file = find_dotenv(filename=dotenv_file)
        if self._dotenv_file:
            load_dotenv(self._dotenv_file)

        self._user_name = user_name or os.environ.get("GEOSERVER_USER")
        self._user_password = user_password or os.environ.get("GEOSERVER_PASSWORD")

        self._admin_user_name = admin_user_name or os.environ.get("GEOSERVER_ADMIN_USER")
        self._admin_pwd = admin_pwd or os.environ.get("GEOSERVER_ADMIN_PASSWORD")
        self._url = url or os.environ.get("GEOSERVER_URL")

        self._session = requests.Session()
        self._session.auth = (self._user_name, self._user_password)
        if self._admin_user_name:
            self._session.auth = (self._admin_user_name, self._admin_pwd)

    def __repr__(self):
        return f"Geoserver at Url: {self.url}"

    @property
    def user_name(self):
        return self._user_name

    @property
    def user_password(self):
        return self._user_password

    @property
    def admin_user_name(self):
        return self._admin_user_name

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value: str):
        self._url = value

    def _raise_for_admin(self):
        if not self._admin_user_name:
            raise GeoserverError("You need admin privileges for this operation.")

    def get_catalog(self) -> object:
        """

        Returns:
            Catalog: A Geoserver catalog instance
        """
        return Catalog(self._url + "/rest/", username=self._user_name, password=self._user_password)

    def register_user(self) -> Message:
        """
        Registers a user in the PostGres database. Needs admin privileges.

        Returns:
            str: Success message
        """

        # self._raise_for_admin()

        geoserver_url = f"{self._url}/rest/security/usergroup/users"

        user = {
            "org.geoserver.rest.security.xml.JaxbUser": {
                "userName": self._user_name,
                "password": self._user_password,
                "enabled": True
            }
        }

        r = self._session.post(geoserver_url, json=user)
        r.raise_for_status()

        return Message(f"User {self._user_name} successfully added")

    def register_user_catalog(self) -> Message:
        cat = Catalog(self._url + "/rest/", username=self._admin_user_name, password=self._admin_pwd)
        cat.create_workspace(self._user_name)

        return Message(f"Catalog {self._user_name} successfully added")

    def register_user_datastore(self) -> Message:
        geoserver_url = f"{self._url}/rest/workspaces/{self._user_name}/datastores"

        db = {
            "dataStore": {
                "name": self._user_name + "_geodb",
                "connectionParameters": {
                    "entry": [
                        {"@key": "host", "$": "db-dcfs-geodb.cbfjgqxk302m.eu-central-1.rds.amazonaws.com"},
                        {"@key": "port", "$": "5432"},
                        {"@key": "database", "$": "geodb"},
                        {"@key": "user", "$": self._user_name},
                        {"@key": "passwd", "$": self._user_password},
                        {"@key": "dbtype", "$": "postgis"}
                    ]
                }
            }
        }

        r = self._session.post(geoserver_url, json=db)
        r.raise_for_status()

        return Message(f"Datastore {self._user_name} successfully added")

    def register_user_access(self) -> Message:
        rule = {
            "rule": {
                "@resource": f"{self._user_name}.*.a",
                "text": f"{self._user_name.upper()}_ADMIN"
            }
        }

        geoserver_url = f"{self._url}/rest/security/acl/layers"

        r = self._session.post(geoserver_url, json=rule, auth=(self._admin_user_name, self._admin_pwd))
        r.raise_for_status()

        return Message(f"User access for {self._user_name} successfully added")

    def register_user_role(self) -> Message:
        geoserver_url = f"{self._url}/rest/roles/role/{self._user_name}"

        r = self._session.post(geoserver_url, json={}, auth=(self._admin_user_name, self._admin_pwd))
        r.raise_for_status()

        return Message(f"User role for {self._user_name} successfully added")

    def publish_collection(self,
                           collection: str,
                           bbox: Tuple[float, float, float, float],
                           bbox_latlon: Tuple[float, float, float, float]):

        feature_type = {"featureType": {
            "name": collection,
            "nativName": f"{self._user_name}_{collection}",
            "namespace": {
                "name": self._user_name,
                "href": f"{self._url}/rest/namespaces/{self._user_name}.json"
            },
            "title": f"{self._user_name}_{collection}",
            "store": {
                "@class": "dataStore",
                "name": f"{self._user_name}:{self._user_name}_geodb",
                "href": f"{self._url}/rest/workspaces/helge/datastores/{self._user_name}:{self._user_name}.json"
            },
            "nativeBoundingBox": {
                "minx": bbox[0],
                "maxx": bbox[1],
                "miny": bbox[2],
                "maxy": bbox[3],
                "crs": {
                    "@class": "projected",
                    "$": "EPSG:3794"
                }
            },
            "latLonBoundingBox": {
                "minx": bbox_latlon[0],
                "maxx": bbox_latlon[1],
                "miny": bbox_latlon[2],
                "maxy": bbox_latlon[3],
                "crs": "EPSG:4326"

            }
        }
        }

        geoserver_url = f"{self._url}/rest/rest/workspaces/{self._user_name}/datastores/" \
                        f"{self._user_name}:{self._user_name}_geodb/featuretypes"

        r = self._session.post(geoserver_url, json=feature_type, auth=(self._admin_user_name, self._admin_pwd))
        r.raise_for_status()

        bbox_str = [str(item) for item in bbox]

        wms_url = f"{self._user_name}/wms?" \
                  f"service=WMS&" \
                  f"version=1.1.0&" \
                  f"request=GetMap&" \
                  f"layers={self._user_name}%3A" \
                  f"{collection}&" \
                  f"bbox={','.join(bbox_str)}&" \
                  f"width=768&" \
                  f"height=496&" \
                  f"srs=EPSG%3A3794&" \
                  f"format=application/openlayers"

        return Message(f"Collection {collection} published ({wms_url}).")
